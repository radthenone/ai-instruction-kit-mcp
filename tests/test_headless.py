"""Wrapper `/headless` (#169): budowa komendy wykonawcy, reguły host/klienci, sprzątanie drzewa."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = KIT_ROOT / "templates/shared/headless/headless.mjs"
NODE = shutil.which("node") or "node"

# Narzędzia, których w izolowanym PATH potrzebuje wrapper i fałszywy wykonawca
# (`basename`/`cat`/`sleep`/`git` w FAKE, `git` w raporcie wrappera) — bez katalogów
# systemowych, żeby test „brak wykonawcy" nie znalazł prawdziwego `claude` (#205).
TOOL_SYMLINKS = ("node", "git", "basename", "cat", "sleep")

# Udaje CLI wykonawcy: zapisuje argv i stdin, zostawia „LSP” w tle i kończy się kodem
# z FAKE_CODE (albo czeka FAKE_SLEEP sekund — do testu timeoutu). FAKE_COMMIT / FAKE_STASH
# robią w repo commit / `git stash` jak wykonawca w trakcie pracy (#183).
# `-p /quota` (agy) odpowiada FAKE_QUOTA z kodem FAKE_QUOTA_CODE; FAKE_LIMIT_FOR / FAKE_FAIL_FOR —
# podane binarki kończą się kodem 1 z tekstem limitu / zwykłego błędu (#293).
FAKE = """#!/bin/sh
if [ "$1" = -p ] && [ "$2" = /quota ]; then
  echo "$(basename "$0") /quota" >> "$HEADLESS_TEST_DIR/calls"; printf '%b' "$FAKE_QUOTA"; exit "${FAKE_QUOTA_CODE:-0}"
fi
printf '%s\\n' "$(basename "$0")" "$@" > "$HEADLESS_TEST_DIR/argv"
printf '%s' "${OPENCODE_CONFIG-}" > "$HEADLESS_TEST_DIR/opencode-config"
basename "$0" >> "$HEADLESS_TEST_DIR/calls"
case " $FAKE_LIMIT_FOR " in *" $(basename "$0") "*) echo "Error: rate limit reached"; exit 1;; esac
case " $FAKE_FAIL_FOR " in *" $(basename "$0") "*) echo "Error: request failed"; exit 1;; esac
if [ "$(basename "$0")" = claude ]; then cat > "$HEADLESS_TEST_DIR/stdin"; fi
sleep 300 >/dev/null 2>&1 &
echo $! > "$HEADLESS_TEST_DIR/child"
echo "wynik wykonawcy"
if [ -n "$FAKE_COMMIT" ]; then echo c > commit.txt; git add commit.txt; git commit -qm "praca wykonawcy"; fi
if [ -n "$FAKE_DROP" ]; then git stash drop -q; fi
if [ -n "$FAKE_STASH" ]; then echo zmiana >> tracked.txt; git stash -q; fi
if [ -n "$FAKE_PARTIAL" ]; then printf 'bez nowej linii'; fi
if [ -n "$FAKE_LIMIT" ]; then echo "$FAKE_LIMIT"; fi
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

def _clock_ahead(*, hours: int, minutes: bool) -> str:
    """Godzina zegarowa (12h, am/pm) w czasie lokalnym, `hours` od teraz.

    Stała godzina („3pm”) po jej minięciu wypada za ~24 h, poza oknem 6 h
    wrappera, i test zależałby od pory uruchomienia.
    """
    at = datetime.now() + timedelta(hours=hours)
    hour = at.hour % 12 or 12
    suffix = "pm" if at.hour >= 12 else "am"
    return f"{hour}:{at.minute:02d}{suffix}" if minutes else f"{hour}{suffix}"

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
        # Izolowany PATH (#205): tylko fałszywi wykonawcy i symlinki narzędzi, bez
        # `/usr/bin` i `/bin`. Inaczej test „brak wykonawcy" znajduje prawdziwego
        # `claude` z systemu i oczekiwany kod 2 nigdy nie wypada (0 != 2).
        self.tools = self.root / "tools"
        self.tools.mkdir()
        for name in TOOL_SYMLINKS:
            source = shutil.which(name)
            if source:
                (self.tools / name).symlink_to(source)

    def path(self) -> str:
        """PATH bez katalogów systemowych — fałszywi wykonawcy + symlinki narzędzi."""
        return os.pathsep.join([str(self.bin), str(self.tools)])

    def profile(self, clients: str) -> None:
        (self.root / ".ai/project.profile.yaml").write_text(
            f"name: app\nclients: {clients}\nbackend: none\n", encoding="utf-8"
        )

    def fake(self, name: str) -> None:
        path = self.bin / name
        path.write_text(FAKE, encoding="utf-8")
        path.chmod(0o755)

    def run_wrapper(
        self, *args: str, stdin: str = "", cwd: Path | str | None = None, **env: str
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [NODE, str(WRAPPER), *args],
            cwd=Path(cwd) if cwd else self.root,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env={
                "PATH": self.path(),
                "HEADLESS_TEST_DIR": str(self.root),
                # Ta sama strefa co w teście — godziny resetu liczone są w czasie lokalnym.
                **({"TZ": os.environ["TZ"]} if "TZ" in os.environ else {}),
                **env,
            },
        )

    def argv(self) -> list[str]:
        return (self.root / "argv").read_text(encoding="utf-8").splitlines()

    def headless_log(self, cwd: Path | str | None = None) -> str:
        (log,) = Path(cwd or self.root).joinpath(".ai/headless-runs").glob("*/headless.log")
        return log.read_text(encoding="utf-8")

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
        self.assertIn("Nie pushuj", prompt)
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

    def test_new_run_prunes_all_but_five_newest_runs(self) -> None:
        runs = self.root / ".ai/headless-runs"
        old = [f"2020-01-0{day}T00-00-00-000Z-opencode" for day in range(1, 8)]
        for name in old:
            (runs / name).mkdir(parents=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        left = sorted(entry.name for entry in runs.iterdir() if entry.is_dir())
        self.assertEqual(len(left), 5)
        self.assertEqual(left[:4], old[-4:])
        self.assertNotIn(left[-1], old)

    def test_prune_keeps_new_run_when_older_names_sort_later(self) -> None:
        runs = self.root / ".ai/headless-runs"
        future = [f"2999-01-0{day}T00-00-00-000Z-opencode" for day in range(1, 8)]
        for name in future:
            (runs / name).mkdir(parents=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        left = {entry.name for entry in runs.iterdir() if entry.is_dir()}
        self.assertEqual(len(left), 5)
        self.assertEqual(len(left - set(future)), 1)

    def test_antigravity_runs_headless_print_with_prompt_argument(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "antigravity", "--model", "flash", "treść zadania")
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv()
        self.assertEqual(argv[1], "-p")
        self.assertTrue("\n".join(argv[2:]).startswith("treść zadania"))
        self.assertEqual(argv[-3:], ["--dangerously-skip-permissions", "--model", "flash"])
        self.assertNotIn("treść zadania", self.headless_log())

    def test_default_timeout_is_60_minutes(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("(timeout 60 min)", self.headless_log())

    def test_opencode_host_calls_gemini_with_model_timeout_and_heartbeat(self) -> None:
        self.profile("opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper(
            "--host", "opencode", "gemini", "--model", "gemini-3.8-flash-high",
            "--timeout", "90", "--heartbeat", "5", "x",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.argv()[0]).name, "agy")
        self.assertEqual(
            self.argv()[-3:],
            ["--dangerously-skip-permissions", "--model", "gemini-3.8-flash-high"],
        )
        self.assertIn("opencode → antigravity", self.headless_log())
        self.assertIn("(timeout 90 min)", self.headless_log())

    def test_antigravity_host_calls_opencode_with_model_and_timeout(self) -> None:
        self.profile("opencode,antigravity")
        result = self.run_wrapper(
            "--host", "antigravity", "opencode", "--model", "openrouter/qwen", "--timeout", "90", "x",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[1:6], ["run", "--standalone", "--auto", "--model", "openrouter/qwen"])
        self.assertIn("antigravity → opencode", self.headless_log())
        self.assertIn("(timeout 90 min)", self.headless_log())

    def test_claude_host_calls_gemini_with_timeout(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "gemini", "--timeout", "45", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claude → antigravity", self.headless_log())
        self.assertIn("(timeout 45 min)", self.headless_log())

    def test_antigravity_host_cannot_call_gemini_itself(self) -> None:
        self.profile("opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "antigravity", "gemini", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("nie wywołuje sam siebie", result.stderr)

    def calls(self) -> list[str]:
        return (self.root / "calls").read_text(encoding="utf-8").splitlines()

    def test_opencode_limit_hands_same_prompt_to_gemini(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "opencode", "echo witaj", FAKE_LIMIT_FOR="opencode2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["opencode2", "agy"])
        self.assertTrue(self.argv()[2].startswith("echo witaj"))
        self.assertIn("opencode → antigravity", self.headless_log())

    def test_missing_opencode_hands_prompt_to_gemini(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        (self.bin / "opencode2").unlink()
        (self.bin / "opencode").unlink()
        result = self.run_wrapper("--host", "claude", "opencode", "echo witaj")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["agy"])
        self.assertIn("opencode → antigravity", self.headless_log())

    def test_limit_on_opencode_and_gemini_leaves_task_to_host(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT_FOR="opencode2 agy")
        self.assertEqual(result.returncode, 75)
        self.assertEqual(self.calls(), ["opencode2", "agy"])
        self.assertIn("PAUSE=rate-limit", result.stdout)

    def test_gemini_limit_hands_same_prompt_to_opencode(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "gemini", "echo witaj", FAKE_LIMIT_FOR="agy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["agy", "opencode2"])
        self.assertIn("antigravity → opencode", self.headless_log())

    def test_fallback_skips_executor_outside_profile(self) -> None:
        self.profile("claude,opencode")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT_FOR="opencode2")
        self.assertEqual(result.returncode, 75)
        self.assertEqual(self.calls(), ["opencode2"])

    def test_bad_agy_config_fails_before_any_executor_runs(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        (self.root / ".agents").mkdir()
        (self.root / ".agents/agy.json").write_text("{zepsuty", encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT_FOR="opencode2")
        self.assertEqual(result.returncode, 2)
        self.assertIn("agy.json", result.stderr)
        self.assertFalse((self.root / "calls").exists())

    def test_handed_off_limit_is_not_reported_as_pause(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT_FOR="opencode2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PAUSE=", result.stdout)

    def test_limit_then_missing_fallback_binary_is_pause_and_logged(self) -> None:
        self.profile("claude,opencode,antigravity")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT_FOR="opencode2")
        self.assertEqual(result.returncode, 75)
        self.assertEqual(self.calls(), ["opencode2"])
        self.assertIn("nie znaleziono agy", self.headless_log())

    def test_model_flag_is_not_passed_to_fallback_executor(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper(
            "--host", "claude", "opencode", "--model", "openrouter/qwen", "x", FAKE_LIMIT_FOR="opencode2",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[-3:], ["--dangerously-skip-permissions", "--model", "gemini-3.8-flash-medium"])

    def test_gemini_is_alias_for_antigravity(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "gemini", "treść zadania")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["agy"])
        self.assertEqual(self.argv()[1], "-p")

    # Wyjście `agy -p /quota` (escape'y dla `printf %b` w FAKE): dwa wyczerpane limity Gemini.
    QUOTA_EMPTY = (
        "Gemini Models\\tFive Hour Limit Remaining\\t0%\\t2099-01-01T12:00:00Z\\n"
        "Gemini Models\\tWeekly Limit Remaining\\t0%\\t2099-01-01T10:00:00Z\\n"
        "Claude and GPT models\\tFive Hour Limit Remaining\\t100%\\t2099-01-01T09:00:00Z\\n"
    )

    def test_agy_failure_with_exhausted_quota_is_rate_limit_pause(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "gemini", "x", FAKE_FAIL_FOR="agy", FAKE_QUOTA=self.QUOTA_EMPTY)
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("PAUSE=rate-limit reset=2099-01-01T10:00:00.000Z", result.stdout)
        self.assertEqual(self.calls(), ["agy", "agy /quota"])

    def test_opencode_limit_then_agy_quota_exhausted_is_pause(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x",
            FAKE_LIMIT_FOR="opencode2", FAKE_FAIL_FOR="agy", FAKE_QUOTA=self.QUOTA_EMPTY,
        )
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("PAUSE=rate-limit", result.stdout)

    def test_gemini_quota_exhausted_hands_task_to_opencode(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "gemini", "x", FAKE_FAIL_FOR="agy", FAKE_QUOTA=self.QUOTA_EMPTY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["agy", "agy /quota", "opencode2"])

    def test_agy_failure_with_quota_left_is_plain_error(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        quota = "Gemini Models\\tFive Hour Limit Remaining\\t100%\\t2099-01-01T12:00:00Z\\n"
        result = self.run_wrapper("--host", "claude", "gemini", "x", FAKE_FAIL_FOR="agy", FAKE_QUOTA=quota)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("PAUSE=", result.stdout)

    def test_agy_failure_with_broken_quota_is_plain_error(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        for quota, code in (("śmieci bez tabulatorów\\n", "0"), ("", "1")):
            with self.subTest(quota=quota, code=code):
                result = self.run_wrapper(
                    "--host", "claude", "gemini", "x", FAKE_FAIL_FOR="agy", FAKE_QUOTA=quota, FAKE_QUOTA_CODE=code,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("PAUSE=", result.stdout)

    def test_resource_exhausted_text_is_rate_limit_pause(self) -> None:
        self.profile("claude,opencode")
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_LIMIT="Error: RESOURCE_EXHAUSTED", FAKE_CODE="1")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("PAUSE=rate-limit", result.stdout)

    def test_antigravity_uses_default_model_when_none_given(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "antigravity", "treść zadania")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.argv()[-3:],
            ["--dangerously-skip-permissions", "--model", "gemini-3.8-flash-medium"],
        )

    def test_antigravity_reads_model_and_effort_from_project_config(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        (self.root / ".agents").mkdir()
        (self.root / ".agents/agy.json").write_text('{"model": "gemini-x", "effort": "high"}', encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "gemini", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[-4:], ["--model", "gemini-x", "--effort", "high"])

    def test_model_flag_beats_antigravity_project_config(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        (self.root / ".agents").mkdir()
        (self.root / ".agents/agy.json").write_text('{"model": "gemini-x"}', encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "gemini", "--model", "gemini-y", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[-3:], ["--dangerously-skip-permissions", "--model", "gemini-y"])

    def test_effort_from_antigravity_config_is_kept_with_model_flag(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        (self.root / ".agents").mkdir()
        (self.root / ".agents/agy.json").write_text('{"effort": "high"}', encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "gemini", "--model", "gemini-3.8-flash", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[-4:], ["--model", "gemini-3.8-flash", "--effort", "high"])

    def test_antigravity_prompt_starting_with_dash_is_not_read_as_flag(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        result = self.run_wrapper("--host", "claude", "antigravity", "-zadanie")
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv()
        self.assertEqual(argv[1:4], ["-p", "", "-zadanie"])

    def test_missing_executor_binary_is_error(self) -> None:
        (self.bin / "claude").unlink()
        result = self.run_wrapper("--host", "opencode", "claude", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("claude", result.stderr)
        self.assertIn("Dozwoleni wykonawcy", result.stderr)
        self.assertFalse((self.root / ".ai/headless-runs").exists())

    # --- sprzątanie drzewa procesów -----------------------------------------

    def test_tree_is_killed_after_success(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_tree_killed()

    def test_tree_is_killed_after_failure_and_code_is_passed(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_CODE="3")
        self.assertEqual(result.returncode, 3)
        self.assert_tree_killed()

    def test_rate_limit_is_pause_with_reset_not_failure(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x",
            FAKE_CODE="1", FAKE_LIMIT="Error: rate limit exceeded, resets at 2099-01-01T10:00:00Z",
        )
        self.assertEqual(result.returncode, 75)
        self.assertIn("PAUSE=rate-limit reset=2099-01-01T10:00:00.000Z", result.stdout)
        self.assert_tree_killed()

    def test_plain_failure_without_limit_text_stays_failure(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1", FAKE_LIMIT="boom: config broken",
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PAUSE=", result.stdout)

    def test_limit_text_on_success_is_not_pause(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="0", FAKE_LIMIT="docs mention rate limit",
        )
        self.assertEqual(result.returncode, 0)

    def test_code_numbers_and_identifiers_are_not_limit(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1",
            FAKE_LIMIT="diff a/src/429.py:429 rateLimit = 429; PR #429 too-many-requests-free",
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PAUSE=", result.stdout)

    def test_opencode_free_limit_is_pause_without_reset(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1", FAKE_LIMIT="Error: Free usage limit reached",
        )
        self.assertEqual(result.returncode, 75)
        self.assertIn("PAUSE=rate-limit reset=brak", result.stdout)

    def test_codex_limit_with_clock_reset_is_pause(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1",
            FAKE_LIMIT=f"You've hit your usage limit. Try again at {_clock_ahead(hours=1, minutes=True)}.",
        )
        self.assertEqual(result.returncode, 75)
        self.assertRegex(result.stdout, r"PAUSE=rate-limit reset=\d{4}-\d{2}-\d{2}T")

    def test_reset_clock_without_minutes_is_parsed(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1", FAKE_LIMIT=f"rate limit reached, resets {_clock_ahead(hours=2, minutes=False)}",
        )
        self.assertEqual(result.returncode, 75)
        self.assertRegex(result.stdout, r"PAUSE=rate-limit reset=\d{4}-\d{2}-\d{2}T")

    def test_reset_iso_after_try_again_is_parsed(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1",
            FAKE_LIMIT="usage limit reached, try again at 2099-01-01T10:00:00Z",
        )
        self.assertIn("PAUSE=rate-limit reset=2099-01-01T10:00:00.000Z", result.stdout)

    def test_limit_on_timeout_is_pause(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "--timeout", "0.02", "x",
            FAKE_SLEEP="30", FAKE_LIMIT="Error: Free usage limit reached",
        )
        self.assertEqual(result.returncode, 75)
        self.assertIn("PAUSE=rate-limit reset=brak", result.stdout)

    def test_pause_line_is_also_in_final_report(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1", FAKE_LIMIT="Error: Free usage limit reached",
        )
        self.assertIn("PAUSE=rate-limit", result.stdout.split("raport końcowy", 1)[1])

    def test_tree_is_killed_after_timeout(self) -> None:
        started = time.time()
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "0.02", "x", FAKE_SLEEP="30")
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.time() - started, 15)
        self.assertIn("timeout", result.stdout + result.stderr)
        self.assert_tree_killed()

    def test_tree_is_killed_when_wrapper_is_terminated(self) -> None:
        proc = subprocess.Popen(
            [NODE, str(WRAPPER), "--host", "claude", "opencode", "x"],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={
                "PATH": self.path(),
                "HEADLESS_TEST_DIR": str(self.root),
                "FAKE_SLEEP": "30",
                "FAKE_PARTIAL": "1",
            },
        )
        deadline = time.time() + 10
        while not (self.root / "child").is_file() and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        proc.terminate()
        out, _ = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 143)
        self.assert_tree_killed()
        # Raport końcowy także po SIGTERM, z niedokończoną linią wykonawcy (#183).
        report = out.split("[headless] raport końcowy", 1)[1]
        self.assertIn("bez nowej linii", report)

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

    # --- log, heartbeat i raport końcowy (#183) -----------------------------

    GIT_ENV = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }

    def git_repo(self, stash: bool = False) -> None:
        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, env={**os.environ, **self.GIT_ENV})

        git("init", "-q")
        (self.root / "tracked.txt").write_text("a\n", encoding="utf-8")
        git("add", "tracked.txt")
        git("commit", "-qm", "start")
        if stash:
            (self.root / "tracked.txt").write_text("b\n", encoding="utf-8")
            git("stash", "push", "-qm", "stary wpis")

    def worktree(self) -> Path:
        """Główny checkout z commitem i linked worktree obok (bez `opencode.json`)."""
        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, env={**os.environ, **self.GIT_ENV})

        (self.root / ".gitignore").write_text("opencode.json\n", encoding="utf-8")
        git("init", "-q")
        git("add", ".ai", ".gitignore")
        git("commit", "-qm", "start")
        path = Path(tempfile.mkdtemp(prefix="headless-worktree-"))
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        git("worktree", "add", "-q", str(path), "-b", "worktree")
        return path

    def executor_config(self) -> str:
        """`OPENCODE_CONFIG`, które dostał fałszywy wykonawca (pusty = brak)."""
        return (self.root / "opencode-config").read_text(encoding="utf-8")

    def log_path(self, result: subprocess.CompletedProcess) -> Path:
        first = result.stdout.splitlines()[0]
        self.assertTrue(first.startswith("[headless] log: "), first)
        return Path(first.removeprefix("[headless] log: "))

    def test_log_holds_executor_output_and_run_dir_is_git_ignored(self) -> None:
        self.git_repo()
        result = self.run_wrapper("--host", "claude", "opencode", "x", **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result)
        self.assertIn("wynik wykonawcy", log.read_text(encoding="utf-8"))
        self.assertIn("wynik wykonawcy", result.stdout)
        status = subprocess.run(["git", "status", "--short"], cwd=self.root, capture_output=True, text=True).stdout
        self.assertNotIn("headless", status)

    def test_heartbeat_and_stall_warning_in_output_and_log(self) -> None:
        self.git_repo()
        result = self.run_wrapper(
            "--host", "claude", "opencode", "--heartbeat", "0.01", "x", FAKE_SLEEP="3", FAKE_COMMIT="1", **self.GIT_ENV
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        for text in (result.stdout, log):
            beats = [line for line in text.splitlines() if line.startswith("[headless] ♥")]
            self.assertTrue(
                any("min |" in b and "pliki:" in b and "commity: 1" in b and "wynik wykonawcy" in b for b in beats),
                beats,
            )
            self.assertIn("[headless] możliwe zacięcie: brak wyjścia od", text)

    def test_timeout_report_shows_commits_status_and_stash_warning(self) -> None:
        self.git_repo()
        result = self.run_wrapper(
            "--host", "claude", "opencode", "--timeout", "0.03", "x",
            FAKE_SLEEP="30", FAKE_COMMIT="1", FAKE_STASH="1", **self.GIT_ENV,
        )
        self.assertEqual(result.returncode, 124)
        log = self.log_path(result).read_text(encoding="utf-8")
        for text in (result.stdout, log):
            self.assertIn("[headless] raport końcowy", text)
            self.assertIn("praca wykonawcy", text)
            self.assertIn("?? argv", text)
            self.assertIn("stash@{0}", text)
            self.assertIn("UWAGA", text)
            self.assertIn("wynik wykonawcy", text.split("[headless] raport końcowy", 1)[1])

    def test_stash_warning_lists_new_entries_by_hash_not_count(self) -> None:
        # Wykonawca zdejmuje stary wpis i dodaje nowy — liczba wpisów bez zmian.
        self.git_repo(stash=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_DROP="1", FAKE_STASH="1", **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        warning = result.stdout.split("UWAGA", 1)[1].split("## ostatnie", 1)[0]
        self.assertIn("stash@{0}", warning)
        self.assertNotIn("stary wpis", warning)

    def test_report_without_git_repo_does_not_fail(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x", GIT_CEILING_DIRECTORIES=str(self.root.parent))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[headless] raport końcowy", result.stdout)
        self.assertNotIn("stash@", result.stdout)

    def test_footer_names_run_dir_and_git_rules(self) -> None:
        result = self.run_wrapper("--host", "opencode", "claude", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = (self.root / "stdin").read_text(encoding="utf-8")
        self.assertIn(str(self.log_path(result).parent), prompt)
        for rule in ("git stash", "git checkout", "git reset", "git worktree add --detach", "git worktree remove", "commit", "Nie pushuj"):
            self.assertIn(rule, prompt)

    def footer_on_branch(self, branch: str) -> tuple[str, str]:
        """Prompt wykonawcy i log runu na danym branchu."""
        self.git_repo()
        subprocess.run(["git", "checkout", "-qb", branch], cwd=self.root, check=True, capture_output=True)
        result = self.run_wrapper("--host", "opencode", "claude", "x", **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        return (self.root / "stdin").read_text(encoding="utf-8"), log

    def test_footer_names_ticket_from_branch_and_work_rules(self) -> None:
        prompt, log = self.footer_on_branch("feat/212-x")
        self.assertIn(
            "Zasady tej sesji (headless, bez użytkownika):\n- Ticket #212: przeczytaj `gh issue view 212 --comments`",
            prompt,
        )
        self.assertIn("[headless] ticket #212", log)
        for rule in ("plan 5–10 kroków", "test-first", "pełny zestaw zrobi CI", "--no-sync", "2 próby", "Nie pushuj"):
            self.assertIn(rule, prompt)
        self.assertNotIn("pełna suita raz", prompt)

    def test_footer_without_ticket_number_skips_ticket_line(self) -> None:
        prompt, log = self.footer_on_branch("dev")
        self.assertNotIn("Ticket #", prompt)
        self.assertNotIn("ticket #", log)
        self.assertIn("test-first", prompt)

    # --- config wykonawcy w linked worktree (#300) ---------------------------

    def test_worktree_uses_main_checkout_config_and_sets_executor_env(self) -> None:
        main_config = self.root / "opencode.json"
        main_config.write_text('{"model": "openrouter/qwen"}', encoding="utf-8")
        wt = self.worktree()
        result = self.run_wrapper("--host", "claude", "opencode", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.executor_config(), str(main_config))
        self.assertIn(f"CONFIG=main-checkout {main_config}", self.headless_log(wt))

    def test_worktree_reads_model_from_main_checkout_config(self) -> None:
        (self.root / "opencode.json").write_text('{"model": "openrouter/qwen"}', encoding="utf-8")
        wt = self.worktree()
        result = self.run_wrapper("--host", "claude", "opencode", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[4:6], ["--model", "openrouter/qwen"])

    def test_model_flag_beats_main_checkout_config(self) -> None:
        (self.root / "opencode.json").write_text('{"model": "openrouter/qwen"}', encoding="utf-8")
        wt = self.worktree()
        result = self.run_wrapper("--host", "claude", "opencode", "--model", "explicit/x", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[4:6], ["--model", "explicit/x"])

    def test_worktree_without_config_everywhere_reports_missing(self) -> None:
        wt = self.worktree()
        result = self.run_wrapper("--host", "claude", "opencode", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG=missing — executor default model", self.headless_log(wt))
        self.assertEqual(self.executor_config(), "")

    def test_worktree_with_own_config_gets_no_fallback_line(self) -> None:
        wt = self.worktree()
        (wt / "opencode.json").write_text('{"model": "local/x"}', encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "opencode", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("CONFIG=", self.headless_log(wt))
        self.assertEqual(self.executor_config(), "")
        self.assertNotIn("--model", self.argv())

    def test_main_checkout_without_config_has_no_config_line(self) -> None:
        self.git_repo()
        result = self.run_wrapper("--host", "claude", "opencode", "x", **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("CONFIG=", self.headless_log())

    def test_worktree_executor_without_config_mechanism_gets_warning_only(self) -> None:
        self.profile("claude,opencode")
        wt = self.worktree()
        result = self.run_wrapper("--host", "opencode", "claude", "x", cwd=wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CONFIG=missing — executor default model", self.headless_log(wt))

    def test_bad_heartbeat_is_error(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--heartbeat", "0", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--heartbeat", result.stderr)

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

    def test_legacy_shim_with_tilde_dp0_resolves_to_real_exe(self) -> None:
        exe = self.root / "node_modules/@opencode/cli/bin/opencode.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        self.assertEqual(self.resolve_shim(NPM_EXE_SHIM.replace("%dp0%", "%~dp0")), str(exe))

    def test_wrapper_runs_via_symlink_with_preserve_symlinks_main(self) -> None:
        link = self.root / "headless.mjs"
        link.symlink_to(WRAPPER)
        result = subprocess.run(
            [NODE, "--preserve-symlinks-main", str(link), "--host", "claude", "opencode", "x"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env={
                "PATH": self.path(),
                "HEADLESS_TEST_DIR": str(self.root),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("kod wyjścia: 0", result.stdout)
        self.assertEqual(self.argv()[0], "opencode2")


if __name__ == "__main__":
    unittest.main()
