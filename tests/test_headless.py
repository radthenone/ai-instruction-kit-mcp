"""Wrapper `/headless` (#169): budowa komendy wykonawcy, reguły host/klienci, sprzątanie drzewa."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = KIT_ROOT / "templates/shared/headless/headless.mjs"

# Udaje CLI wykonawcy: zapisuje argv i stdin, zostawia „LSP” w tle i kończy się kodem
# z FAKE_CODE (albo czeka FAKE_SLEEP sekund — do testu timeoutu).
FAKE = """#!/bin/sh
printf '%s\\n' "$(basename "$0")" "$@" > "$HEADLESS_TEST_DIR/argv"
if [ "$(basename "$0")" = claude ]; then cat > "$HEADLESS_TEST_DIR/stdin"; fi
sleep 300 >/dev/null 2>&1 &
echo $! > "$HEADLESS_TEST_DIR/child"
echo "wynik wykonawcy"
if [ -n "$FAKE_SLEEP" ]; then sleep "$FAKE_SLEEP"; fi
exit "${FAKE_CODE:-0}"
"""


# Shimy generowane przez npm (cmd-shim) dla binarki natywnej i dla skryptu JS.
NPM_EXE_SHIM = """@ECHO off\r
GOTO start\r
:find_dp0\r
SET dp0=%~dp0\r
EXIT /b\r
:start\r
SETLOCAL\r
CALL :find_dp0\r
"%dp0%\\node_modules\\@opencode\\cli\\bin\\opencode.exe"   %*\r
"""
NPM_JS_SHIM = """@ECHO off\r
GOTO start\r
:find_dp0\r
SET dp0=%~dp0\r
EXIT /b\r
:start\r
SETLOCAL\r
CALL :find_dp0\r
IF EXIST "%dp0%\\node.exe" (\r
  SET "_prog=%dp0%\\node.exe"\r
) ELSE (\r
  SET "_prog=node"\r
  SET PATHEXT=%PATHEXT:;.JS;=;%\r
)\r
endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\opencode-ai\\bin\\opencode" %*\r
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Zombie po zabiciu, zanim init go zbierze, też liczy się jako martwy.
    status = Path(f"/proc/{pid}/status")
    return not (status.is_file() and "\nState:\tZ" in status.read_text())


@unittest.skipUnless(shutil.which("node") and os.name != "nt", "brak node albo Windows")
class HeadlessWrapperTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / ".ai").mkdir()
        self.profile("claude,opencode,codex")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("claude", "opencode2", "opencode"):
            self.fake(name)

    def profile(self, clients: str) -> None:
        (self.root / ".ai/project.profile.yaml").write_text(
            f"name: app\nclients: {clients}\nbackend: none\n", encoding="utf-8"
        )

    def fake(self, name: str) -> None:
        path = self.bin / name
        path.write_text(FAKE, encoding="utf-8")
        path.chmod(0o755)

    def run_wrapper(self, *args: str, stdin: str = "", **env: str) -> subprocess.CompletedProcess:
        node_dir = str(Path(shutil.which("node") or "node").parent)
        return subprocess.run(
            ["node", str(WRAPPER), *args],
            cwd=self.root,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env={
                "PATH": os.pathsep.join([str(self.bin), node_dir, "/usr/bin", "/bin"]),
                "HEADLESS_TEST_DIR": str(self.root),
                **env,
            },
        )

    def argv(self) -> list[str]:
        return (self.root / "argv").read_text(encoding="utf-8").splitlines()

    def assert_tree_killed(self) -> None:
        pid = int((self.root / "child").read_text())
        deadline = time.time() + 3
        while _alive(pid) and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(_alive(pid), "proces w tle wykonawcy przeżył wrapper")

    # --- komenda per wiersz tabeli wykonawców ---------------------------------

    def test_claude_gets_prompt_on_stdin_with_footer_and_model(self) -> None:
        result = self.run_wrapper("--host", "opencode", "claude", "--model", "haiku", "dopisz test do X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv(), ["claude", "-p", "--permission-mode", "bypassPermissions", "--model", "haiku"])
        prompt = (self.root / "stdin").read_text(encoding="utf-8")
        self.assertTrue(prompt.startswith("dopisz test do X\n"))
        self.assertIn("Nie commituj", prompt)
        self.assertIn("wynik wykonawcy", result.stdout)

    def test_opencode_runs_standalone_with_prompt_argument(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", stdin="treść\nz \"cudzysłowem\"\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv()
        self.assertEqual(argv[:4], ["opencode2", "run", "--standalone", "--auto"])
        self.assertNotIn("--model", argv)
        self.assertTrue("\n".join(argv[4:]).startswith('treść\nz "cudzysłowem"'))

    def test_opencode_falls_back_to_v1_binary(self) -> None:
        (self.bin / "opencode2").unlink()
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[0], "opencode")

    def test_missing_executor_binary_is_error(self) -> None:
        (self.bin / "claude").unlink()
        result = self.run_wrapper("--host", "opencode", "claude", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("claude", result.stderr)
        self.assertIn("Dozwoleni wykonawcy", result.stderr)

    # --- sprzątanie drzewa procesów -----------------------------------------

    def test_tree_is_killed_after_success(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_tree_killed()

    def test_tree_is_killed_after_failure_and_code_is_passed(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_CODE="3")
        self.assertEqual(result.returncode, 3)
        self.assert_tree_killed()

    def test_tree_is_killed_after_timeout(self) -> None:
        started = time.time()
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "0.02", "x", FAKE_SLEEP="30")
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.time() - started, 15)
        self.assertIn("timeout", result.stdout + result.stderr)
        self.assert_tree_killed()

    def test_tree_is_killed_when_wrapper_is_terminated(self) -> None:
        node_dir = str(Path(shutil.which("node") or "node").parent)
        proc = subprocess.Popen(
            ["node", str(WRAPPER), "--host", "claude", "opencode", "x"],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={
                "PATH": os.pathsep.join([str(self.bin), node_dir, "/usr/bin", "/bin"]),
                "HEADLESS_TEST_DIR": str(self.root),
                "FAKE_SLEEP": "30",
            },
        )
        deadline = time.time() + 10
        while not (self.root / "child").is_file() and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        proc.terminate()
        self.assertEqual(proc.wait(timeout=10), 143)
        self.assert_tree_killed()

    # --- flagi i reguły -----------------------------------------------------

    def test_unknown_flag_lists_known_flags(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--fast", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--fast", result.stderr)
        self.assertIn("--model", result.stderr)
        self.assertIn("--timeout", result.stderr)

    def test_bad_timeout_is_error(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "zero", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--timeout", result.stderr)

    def test_executor_equal_to_host_is_refused_with_allowed_list(self) -> None:
        result = self.run_wrapper("--host", "claude", "claude", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("opencode", result.stderr)
        self.assertFalse((self.root / "argv").exists())

    def test_executor_outside_clients_is_refused(self) -> None:
        self.profile("claude,codex")
        result = self.run_wrapper("--host", "codex", "opencode", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("claude", result.stderr)
        self.assertFalse((self.root / "argv").exists())

    def test_client_without_headless_mode_is_refused(self) -> None:
        result = self.run_wrapper("--host", "claude", "codex", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("opencode", result.stderr)

    def test_clients_all_allows_every_executor_but_host(self) -> None:
        self.profile("all")
        result = self.run_wrapper("--host", "codex", "claude", "x")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_flag_without_value_does_not_swallow_next_flag(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--model", "--timeout", "5", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--model", result.stderr)
        self.assertFalse((self.root / "argv").exists())

    def test_clients_as_yaml_list_are_read(self) -> None:
        for clients in ("[claude, opencode]", "\n  - claude\n  - opencode"):
            with self.subTest(clients=clients):
                self.profile(clients)
                result = self.run_wrapper("--host", "claude", "opencode", "x")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_opencode_prompt_starting_with_dash_is_not_a_flag(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", stdin="- popraw test\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv()
        # Argument zaczyna się od nowej linii, więc parser opencode nie widzi w nim flagi.
        self.assertEqual(argv[4], "")
        self.assertEqual(argv[5], "- popraw test")

    def test_missing_prompt_is_error(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode")
        self.assertEqual(result.returncode, 2)

    def test_binary_name_is_alias_of_executor(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode2", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[0], "opencode2")

    # --- shim npm `.cmd` na Windows (#182) ----------------------------------

    def resolve_shim(self, body: str) -> str:
        shim = self.root / "opencode2.cmd"
        shim.write_text(body, encoding="utf-8")
        script = "const m = await import(process.env.WRAPPER_URL); console.log(m.resolveShim(process.env.SHIM))"
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env={**os.environ, "WRAPPER_URL": WRAPPER.as_uri(), "SHIM": str(shim)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_npm_shim_resolves_to_real_exe(self) -> None:
        exe = self.root / "node_modules/@opencode/cli/bin/opencode.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        self.assertEqual(self.resolve_shim(NPM_EXE_SHIM), str(exe))

    def test_npm_shim_without_exe_resolves_to_nothing(self) -> None:
        # Shim skryptu JS: jedyny exe to sonda `%dp0%\node.exe`, nie wykonawca.
        (self.root / "node.exe").write_bytes(b"")
        self.assertEqual(self.resolve_shim(NPM_JS_SHIM), "null")

    def test_npm_shim_with_missing_exe_resolves_to_nothing(self) -> None:
        self.assertEqual(self.resolve_shim(NPM_EXE_SHIM), "null")


if __name__ == "__main__":
    unittest.main()
