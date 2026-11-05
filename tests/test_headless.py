"""Wrapper `/headless` (#169): budowa komendy wykonawcy, reguły host/klienci, sprzątanie drzewa."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = KIT_ROOT / "templates/shared/headless/headless.mjs"
NODE = shutil.which("node") or "node"

# Narzędzia, których w izolowanym PATH potrzebuje wrapper i fałszywy wykonawca
# (`basename`/`cat`/`sleep`/`git` w FAKE, `git` w raporcie wrappera) — bez katalogów
# systemowych, żeby test „brak wykonawcy" nie znalazł prawdziwego `claude` (#205).
TOOL_SYMLINKS = ("node", "git", "basename", "cat", "sleep", "ps")

# Udaje CLI wykonawcy: zapisuje argv i stdin, zostawia „LSP” w tle i kończy się kodem
# z FAKE_CODE (albo czeka FAKE_SLEEP sekund — do testu timeoutu). FAKE_COMMIT / FAKE_STASH
# robią w repo commit / `git stash` jak wykonawca w trakcie pracy (#183).
# `-p /quota` (agy) odpowiada FAKE_QUOTA z kodem FAKE_QUOTA_CODE; FAKE_LIMIT_FOR / FAKE_FAIL_FOR —
# podane binarki kończą się kodem 1 z tekstem limitu / zwykłego błędu (#293).
FAKE = """#!/bin/sh
if [ "$1" = -p ] && [ "$2" = /quota ]; then
  echo "$(basename "$0") /quota" >> "$HEADLESS_TEST_DIR/calls"; printf '%b' "$FAKE_QUOTA"; exit "${FAKE_QUOTA_CODE:-0}"
fi
if [ -n "$FAKE_TRAP" ]; then trap 'echo term > "$HEADLESS_TEST_DIR/term"; exit 0' TERM; fi
if [ -n "$FAKE_IGNORE_TERM" ]; then trap '' TERM; fi
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
if [ -n "$FAKE_DIRTY" ]; then echo mod >> tracked.txt; fi
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


def _clock_ahead(*, hours: int, minutes: bool) -> str:
    """Godzina zegarowa (12h, am/pm) w czasie lokalnym, `hours` od teraz.

    Stała godzina („3pm”) po jej minięciu wypada za ~24 h, poza oknem 6 h
    wrappera, i test zależałby od pory uruchomienia.
    """
    at = datetime.now() + timedelta(hours=hours)
    hour = at.hour % 12 or 12
    suffix = "pm" if at.hour >= 12 else "am"
    return f"{hour}:{at.minute:02d}{suffix}" if minutes else f"{hour}{suffix}"


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

    def profile(self, clients: str, language: str | None = None) -> None:
        lang = f"language: {language}\n" if language else ""
        (self.root / ".ai/project.profile.yaml").write_text(
            f"name: app\n{lang}clients: {clients}\nbackend: none\n", encoding="utf-8"
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

    def test_agy_invalid_model_failure_is_config_error_with_exit_code_2_without_fallback(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        fake_output = (
            'error: invalid model selection (--model "bad-model" --effort ""): model bad-model is not recognized\n'
            'Available models:\n'
            '  Gemini 3.8 Flash (High)\n'
            '  Gemini 3.8 Flash (Medium)\n'
        )
        result = self.run_wrapper(
            "--host", "claude", "antigravity", "--model", "bad-model", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT=fake_output,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), ["agy"])
        self.assertIn("nieznany model", result.stdout)
        self.assertIn(
            "model bad-model nieznany wykonawcy agy; dostępne: Gemini 3.8 Flash (High), Gemini 3.8 Flash (Medium)",
            result.stdout,
        )
        report = result.stdout.split("[headless] raport końcowy", 1)[1]
        self.assertIn("## nieznany model: model bad-model nieznany wykonawcy agy", report)

    def test_agy_invalid_model_minimal_available_models_output(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        result = self.run_wrapper(
            "--host", "claude", "antigravity", "--model", "unknown-m", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT="error: model unknown-m is not recognized\nAvailable models:\n",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), ["agy"])
        self.assertIn("model unknown-m nieznany wykonawcy agy", result.stdout)

    def test_gemini_alias_invalid_model_failure_is_config_error_with_exit_code_2(self) -> None:
        self.profile("claude,opencode,antigravity")
        self.fake("agy")
        fake_output = (
            'error: model bad-gem is not recognized\n'
            'Available models:\n'
            '  model-a\n'
        )
        result = self.run_wrapper(
            "--host", "claude", "gemini", "--model", "bad-gem", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT=fake_output,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), ["agy"])
        self.assertIn("model bad-gem nieznany wykonawcy agy; dostępne: model-a", result.stdout)
        report = result.stdout.split("[headless] raport końcowy", 1)[1]
        self.assertIn("## nieznany model: model bad-gem nieznany wykonawcy agy", report)

    def test_agy_invalid_model_from_config_file(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        (self.root / ".agents").mkdir(exist_ok=True)
        (self.root / ".agents/agy.json").write_text('{"model": "bad-cfg-model"}', encoding="utf-8")
        fake_output = "error: invalid model selection\nAvailable models:\n  Gemini 3.8 Flash (High)\n"
        result = self.run_wrapper(
            "--host", "claude", "antigravity", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT=fake_output,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("model bad-cfg-model nieznany wykonawcy agy; dostępne: Gemini 3.8 Flash (High)", result.stdout)

    def test_available_models_phrase_from_other_executor_is_plain_failure(self) -> None:
        fake_output = "error: model bad is not recognized\nAvailable models:\n  model-a\n"
        for executor in ("opencode", "claude"):
            with self.subTest(executor=executor):
                result = self.run_wrapper(
                    "--host", "codex", executor, "zadanie",
                    FAKE_CODE="1", FAKE_LIMIT=fake_output,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn("nieznany model", result.stdout)

    def test_agy_rate_limit_beats_available_models_list(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        fake_output = (
            "error: model bad is not recognized\n"
            "Available models:\n"
            "  model-a\n"
            "Error: rate limit exceeded\n"
        )
        result = self.run_wrapper(
            "--host", "claude", "antigravity", "--model", "bad", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT=fake_output,
        )
        self.assertEqual(result.returncode, 75)
        self.assertIn("PAUSE=rate-limit", result.stdout)
        self.assertNotIn("nieznany model", result.stdout)

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
        log = self.headless_log()
        self.assertIn("[headless] sygnał SIGTERM", log)
        snapshot = log.split("[headless] sygnał SIGTERM", 1)[1]
        self.assertIn("node", snapshot)
        self.assertNotIn(" x\n", snapshot)

    def test_signal_exit_code_wins_over_executor_that_handles_sigterm(self) -> None:
        proc = subprocess.Popen(
            [NODE, str(WRAPPER), "--host", "claude", "opencode", "x"],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={"PATH": self.path(), "HEADLESS_TEST_DIR": str(self.root), "FAKE_SLEEP": "30", "FAKE_TRAP": "1"},
        )
        deadline = time.time() + 10
        while not (self.root / "child").is_file() and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        proc.terminate()
        out, _ = proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 143)
        self.assertTrue((self.root / "term").is_file())
        self.assertEqual(out.count("[headless] raport końcowy"), 1)
        self.assertNotIn("[headless] kod wyjścia", out)

    def test_executor_gets_sigterm_before_sigkill(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "0.02", "x", FAKE_SLEEP="30", FAKE_TRAP="1")
        self.assertEqual(result.returncode, 124)
        self.assertTrue((self.root / "term").is_file(), "wykonawca nie dostał SIGTERM przed SIGKILL")
        self.assert_tree_killed()

    def test_executor_ignoring_sigterm_is_still_killed(self) -> None:
        started = time.time()
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "0.02", "x", FAKE_SLEEP="30", FAKE_IGNORE_TERM="1")
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.time() - started, 15)
        self.assert_tree_killed()

    # --- wiersz wywołania: klasa i ostatnia linia wyjścia (#396) ----------------

    def last_row(self, result: subprocess.CompletedProcess) -> dict:
        """Ostatnia linia stdout — wiersz JSON wywołania (#396)."""
        return json.loads(result.stdout.splitlines()[-1])

    def test_call_ends_with_row_and_writes_no_buffer_without_ctx(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.last_row(result)
        self.assertEqual(
            {key: row[key] for key in ("ticket", "wykonawca", "lancuch", "model", "kod", "klasa", "sprawdz", "dzialanie")},
            {"ticket": "-", "wykonawca": "opencode", "lancuch": "opencode", "model": None,
             "kod": 0, "klasa": "OK", "sprawdz": "-", "dzialanie": "-"},
        )
        self.assertEqual(row["log"], str(self.log_path(result)))
        self.assertIn("start", row)
        self.assertIn("koniec", row)
        self.assertEqual(list(self.root.rglob("headless-rows.jsonl")), [])

    def test_row_takes_ticket_from_branch(self) -> None:
        self.git_repo()
        subprocess.run(["git", "checkout", "-qb", "feat/396-headless-row-night-buffer"], cwd=self.root, check=True, capture_output=True)
        result = self.run_wrapper("--host", "opencode", "claude", "x", **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.last_row(result)["ticket"], "396")

    def test_timeout_row_is_hang_with_code_124(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--timeout", "0.02", "x", FAKE_SLEEP="30")
        self.assertEqual(result.returncode, 124)
        row = self.last_row(result)
        self.assertEqual((row["klasa"], row["kod"]), ("HANG", 124))
        self.assertIn("zabito drzewo procesów", row["dzialanie"])

    def test_limit_row_is_limit_with_code_75(self) -> None:
        result = self.run_wrapper(
            "--host", "claude", "opencode", "x", FAKE_CODE="1", FAKE_LIMIT="Error: Free usage limit reached",
        )
        self.assertEqual(result.returncode, 75)
        row = self.last_row(result)
        self.assertEqual((row["klasa"], row["kod"]), ("LIMIT", 75))
        self.assertIn("PAUSE", row["sprawdz"])

    def test_failure_row_is_error_with_executor_code(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_CODE="3")
        self.assertEqual(result.returncode, 3)
        row = self.last_row(result)
        self.assertEqual((row["klasa"], row["kod"]), ("ERROR", 3))

    def test_exit_zero_without_changes_row_is_suspect(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.last_row(result)["klasa"], "SUSPECT")

    def test_new_stash_entry_row_is_policy(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_STASH="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.last_row(result)["klasa"], "POLITYKA")

    def test_agy_invalid_model_row_is_model_with_code_2(self) -> None:
        self.profile("claude,antigravity")
        self.fake("agy")
        fake_output = "error: invalid model selection\nAvailable models:\n  Gemini 3.8 Flash (High)\n"
        result = self.run_wrapper(
            "--host", "claude", "antigravity", "--model", "bad-model", "zadanie",
            FAKE_CODE="1", FAKE_LIMIT=fake_output,
        )
        self.assertEqual(result.returncode, 2)
        row = self.last_row(result)
        self.assertEqual((row["klasa"], row["kod"], row["model"]), ("MODEL", 2, "bad-model"))

    def test_terminated_call_ends_with_hang_row(self) -> None:
        proc = subprocess.Popen(
            [NODE, str(WRAPPER), "--host", "claude", "opencode", "x"],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={"PATH": self.path(), "HEADLESS_TEST_DIR": str(self.root), "FAKE_SLEEP": "30"},
        )
        deadline = time.time() + 10
        while not (self.root / "child").is_file() and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        proc.terminate()
        out, _ = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 143)
        self.assert_tree_killed()
        row = json.loads(out.splitlines()[-1])
        self.assertEqual((row["klasa"], row["kod"], row["wykonawca"]), ("HANG", 143, "opencode"))
        self.assertIn("sygnał SIGTERM", row["dzialanie"])

    def test_refused_executor_row_is_policy_without_run(self) -> None:
        result = self.run_wrapper("--host", "claude", "claude", "x")
        self.assertEqual(result.returncode, 2)
        row = self.last_row(result)
        self.assertEqual((row["klasa"], row["kod"], row["wykonawca"], row["log"]), ("POLITYKA", 2, "-", None))
        self.assertIn("nie wywołuje sam siebie", row["sprawdz"])
        self.assertFalse((self.root / ".ai/headless-runs").exists())

    # --- bufor nocy i wycinek logu (#396) -----------------------------------------

    def ctx_dir(self) -> Path:
        """Katalog CTX nocy poza repo (w produkcji `~/.cache/night-run-…`)."""
        path = Path(tempfile.mkdtemp(prefix="night-ctx-"))
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def buffer_rows(self, ctx: Path) -> list[dict]:
        text = (ctx / "headless-rows.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def terminate_wrapper(self, *args: str) -> tuple[int, str]:
        """Start wrappera z wiszącym wykonawcą, SIGTERM po starcie; zwraca kod i stdout."""
        proc = subprocess.Popen(
            [NODE, str(WRAPPER), *args],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={"PATH": self.path(), "HEADLESS_TEST_DIR": str(self.root), "FAKE_SLEEP": "30"},
        )
        deadline = time.time() + 10
        while not (self.root / "child").is_file() and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        proc.terminate()
        out, _ = proc.communicate(timeout=10)
        self.assert_tree_killed()
        return proc.returncode, out

    def test_call_with_ctx_appends_its_row_to_buffer(self) -> None:
        ctx = self.ctx_dir()
        first = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        second = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "y")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.buffer_rows(ctx), [self.last_row(first), self.last_row(second)])

    def test_failed_call_with_ctx_copies_excerpt_next_to_buffer(self) -> None:
        ctx = self.ctx_dir()
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x", FAKE_CODE="3")
        self.assertEqual(result.returncode, 3, result.stderr)
        row = self.last_row(result)
        self.assertEqual(self.buffer_rows(ctx), [row])
        excerpt = ctx / f"headless-excerpt-{Path(row['log']).parent.name}.txt"
        text = excerpt.read_text(encoding="utf-8")
        self.assertIn("wynik wykonawcy", text)
        self.assertIn("[headless] raport końcowy", text)

    def test_ok_call_with_ctx_writes_no_excerpt(self) -> None:
        ctx = self.ctx_dir()
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["klasa"] for row in self.buffer_rows(ctx)], ["OK"])
        self.assertEqual(list(ctx.glob("headless-excerpt-*.txt")), [])

    def test_terminated_call_with_ctx_buffers_hang_row_and_excerpt(self) -> None:
        ctx = self.ctx_dir()
        code, out = self.terminate_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        self.assertEqual(code, 143)
        (row,) = self.buffer_rows(ctx)
        self.assertEqual((row["klasa"], row["kod"]), ("HANG", 143))
        self.assertEqual(row, json.loads(out.splitlines()[-1]))
        self.assertTrue((ctx / f"headless-excerpt-{Path(row['log']).parent.name}.txt").is_file())

    def test_refused_call_with_ctx_is_buffered_as_policy(self) -> None:
        ctx = self.ctx_dir()
        result = self.run_wrapper("--host", "claude", "claude", "--ctx", str(ctx), "x")
        self.assertEqual(result.returncode, 2)
        rows = self.buffer_rows(ctx)
        self.assertEqual(rows, [self.last_row(result)])
        self.assertEqual(rows[0]["klasa"], "POLITYKA")

    def test_unwritable_ctx_does_not_fail_the_call(self) -> None:
        blocker = self.root / "ctx-jest-plikiem"
        blocker.write_text("nie katalog\n", encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(blocker), "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bufor nocy", result.stderr)
        self.assertEqual(self.last_row(result)["klasa"], "OK")

    # --- składanie raportu nocy z bufora (#396) -----------------------------------

    def report_row(self, ticket: str, start: str, klasa: str = "OK") -> dict:
        return {
            "ticket": ticket,
            "wykonawca": "opencode",
            "lancuch": "opencode",
            "model": None,
            "kod": 0 if klasa == "OK" else 1,
            "klasa": klasa,
            "start": start,
            "koniec": start,
            "log": str(self.root / ".ai/headless-runs" / f"{start}-opencode" / "headless.log"),
            "sprawdz": "-" if klasa == "OK" else "sprawdzić wycinek logu (kod i ostatnie linie)",
            "dzialanie": "-",
        }

    def write_buffer(self, ctx: Path, rows: list[dict]) -> None:
        (ctx / "headless-rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_report_groups_rows_by_ticket_and_lists_calls_in_order(self) -> None:
        ctx = self.ctx_dir()
        rows = [
            self.report_row("396", "2026-11-05T01:00:00.000Z"),
            self.report_row("398", "2026-11-05T01:10:00.000Z", "ERROR"),
            self.report_row("396", "2026-11-05T01:20:00.000Z"),
            self.report_row("-", "2026-11-05T01:30:00.000Z", "HANG"),
        ]
        self.write_buffer(ctx, rows)
        result = self.run_wrapper("--report", "--ctx", str(ctx))
        self.assertEqual(result.returncode, 0, result.stderr)
        head, _, listing = result.stdout.partition("## Raport listy")
        self.assertIn("## HEADLESS REPORT", head)
        groups = {section.split("\n", 1)[0]: section for section in head.split("\n### ")[1:]}
        self.assertEqual(list(groups), ["#396", "#398", "bez ticketu"])
        self.assertIn(rows[0]["start"], groups["#396"])
        self.assertIn(rows[2]["start"], groups["#396"])
        self.assertNotIn(rows[1]["start"], groups["#396"])
        self.assertIn(rows[1]["start"], groups["#398"])
        self.assertIn(rows[3]["start"], groups["bez ticketu"])
        positions = [listing.index(row["start"]) for row in rows]
        self.assertEqual(positions, sorted(positions))

    def test_report_deletes_buffer_after_printing(self) -> None:
        ctx = self.ctx_dir()
        self.write_buffer(ctx, [self.report_row("396", "2026-11-05T01:00:00.000Z")])
        result = self.run_wrapper("--report", "--ctx", str(ctx))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("#396", result.stdout)
        self.assertFalse((ctx / "headless-rows.jsonl").exists())

    def test_report_points_to_excerpt_and_accepts_flag_after_ctx(self) -> None:
        ctx = self.ctx_dir()
        start = "2026-11-05T01:00:00.000Z"
        self.write_buffer(ctx, [self.report_row("396", start, "ERROR")])
        excerpt = ctx / f"headless-excerpt-{start}-opencode.txt"
        excerpt.write_text("ostatnie linie\n", encoding="utf-8")
        result = self.run_wrapper("--ctx", str(ctx), "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"wycinek: {excerpt}", result.stdout)

    def test_report_terminated_while_printing_keeps_buffer(self) -> None:
        ctx = self.ctx_dir()
        # Wypis większy niż bufor potoku (64 KB) i nikt go nie czyta: zapis wisi, aż przyjdzie sygnał.
        self.write_buffer(ctx, [self.report_row(str(n), f"2026-11-05T01:{n % 60:02d}:00.000Z") for n in range(1, 2001)])
        proc = subprocess.Popen(
            [NODE, str(WRAPPER), "--report", "--ctx", str(ctx)],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={"PATH": self.path()},
        )
        time.sleep(1)
        self.assertIsNone(proc.poll(), "raport skończył się przed sygnałem — test nie testuje przerwania")
        proc.terminate()
        proc.communicate(timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue((ctx / "headless-rows.jsonl").is_file())

    def test_report_without_buffer_says_there_were_no_calls(self) -> None:
        ctx = self.ctx_dir()
        result = self.run_wrapper("--report", "--ctx", str(ctx))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("brak wywołań headless", result.stdout)

    def test_report_without_ctx_is_error(self) -> None:
        result = self.run_wrapper("--report")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--report wymaga --ctx", result.stderr)

    # --- sprzątanie runów a wycinki w CTX (#396) ----------------------------------

    def run_row(self, run: str, klasa: str) -> dict:
        """Wiersz bufora dla konkretnego runu w `.ai/headless-runs` (log w katalogu tego runu)."""
        row = self.report_row("396", "2020-01-01T00:00:00.000Z", klasa)
        return {**row, "log": str(self.root / ".ai/headless-runs" / run / "headless.log")}

    def prune_fixture(self, ctx: Path, klasa: str) -> list[str]:
        """Siedem starych runów; najstarszy ma wiersz bufora z podaną klasą."""
        runs = self.root / ".ai/headless-runs"
        old = [f"2020-01-0{day}T00-00-00-000Z-opencode" for day in range(1, 8)]
        for name in old:
            (runs / name).mkdir(parents=True)
        self.write_buffer(ctx, [self.run_row(old[0], klasa)])
        return old

    def test_prune_keeps_failed_run_without_excerpt_in_ctx(self) -> None:
        ctx = self.ctx_dir()
        old = self.prune_fixture(ctx, "ERROR")
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        runs = self.root / ".ai/headless-runs"
        self.assertTrue((runs / old[0]).is_dir(), "nieudany run bez wycinka w CTX został skasowany")
        self.assertFalse((runs / old[1]).exists())

    def test_prune_removes_failed_run_once_its_excerpt_is_in_ctx(self) -> None:
        ctx = self.ctx_dir()
        old = self.prune_fixture(ctx, "ERROR")
        (ctx / f"headless-excerpt-{old[0]}.txt").write_text("wycinek\n", encoding="utf-8")
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".ai/headless-runs" / old[0]).exists())

    def test_prune_removes_ok_run_without_excerpt(self) -> None:
        ctx = self.ctx_dir()
        old = self.prune_fixture(ctx, "OK")
        result = self.run_wrapper("--host", "claude", "opencode", "--ctx", str(ctx), "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".ai/headless-runs" / old[0]).exists())

    # --- flagi i reguły -----------------------------------------------------

    def test_unknown_flag_lists_known_flags(self) -> None:
        result = self.run_wrapper("--host", "claude", "opencode", "--fast", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--fast", result.stderr)
        self.assertIn("--model", result.stderr)
        self.assertIn("--timeout", result.stderr)
        row = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(row["klasa"], "ERROR")
        self.assertEqual(row["kod"], 2)

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

    def clean_git_repo(self) -> None:
        """Repo jak `git_repo`, ale pliki fixture (wrapper, fałszywe CLI) w `.git/info/exclude` — czysty start."""
        self.git_repo()
        (self.root / ".git" / "info" / "exclude").write_text(".ai/\nbin/\ntools/\n", encoding="utf-8")

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

    def test_exit_zero_without_changes_or_commits_flags_suspect_no_changes(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertIn("## SUSPECT=no-changes", result.stdout)
        self.assertIn("## SUSPECT=no-changes", log)

    def test_exit_zero_with_commit_does_not_flag_suspect(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_COMMIT="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertNotIn("SUSPECT=no-changes", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", log)

    def test_exit_zero_with_working_tree_changes_does_not_flag_suspect(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_DIRTY="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertNotIn("SUSPECT=no-changes", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", log)

    def test_dirty_start_with_more_edits_to_same_file_does_not_flag_suspect(self) -> None:
        self.clean_git_repo()
        (self.root / "tracked.txt").write_text("brudny start\n", encoding="utf-8")
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_DIRTY="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertNotIn("SUSPECT=no-changes", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", log)

    def test_exit_zero_with_new_stash_entry_does_not_flag_suspect(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_STASH="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertIn("nowe wpisy stasha", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", log)

    def test_exit_nonzero_without_changes_does_not_flag_suspect(self) -> None:
        self.clean_git_repo()
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        result = self.run_wrapper("--host", "claude", "opencode", "x", FAKE_CODE="1", HEADLESS_TEST_DIR=state, **self.GIT_ENV)
        self.assertEqual(result.returncode, 1, result.stderr)
        log = self.log_path(result).read_text(encoding="utf-8")
        self.assertNotIn("SUSPECT=no-changes", result.stdout)
        self.assertNotIn("SUSPECT=no-changes", log)

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

    def test_footer_requires_polish_topic_and_coauthor_trailer(self) -> None:
        prompt, _ = self.footer_on_branch("feat/398-x")
        self.assertIn("Commity: temat po polsku (język `pl` z Profilu)", prompt)
        self.assertIn("trailer `Co-Authored-By: Claude <noreply@anthropic.com>`", prompt)

    def test_footer_topic_language_follows_profile(self) -> None:
        self.profile("claude,opencode,codex", language="en")
        prompt, _ = self.footer_on_branch("feat/398-x")
        self.assertIn("Commity: temat po angielsku (język `en` z Profilu)", prompt)
        self.assertNotIn("temat po polsku", prompt)

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

    def test_parse_available_models_and_detect_unknown_model(self) -> None:
        lines = [
            'error: invalid model selection (--model "custom-xyz" --effort ""): model custom-xyz is not recognized',
            'Available models:',
            '  Gemini 3.8 Flash (High)',
            '  Gemini 3.8 Flash (Medium)',
            '  Claude Sonnet 4.6 (Thinking)',
        ]
        script = (
            "const m = await import(process.env.WRAPPER_URL); "
            "const text = JSON.parse(process.env.INPUT_TEXT); "
            "const models = m.parseAvailableModels(text); "
            "const detected = m.detectUnknownModel(text); "
            "console.log(JSON.stringify({ models, detected }));"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env={**os.environ, "WRAPPER_URL": WRAPPER.as_uri(), "INPUT_TEXT": json.dumps("\n".join(lines))},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["detected"], "custom-xyz")
        self.assertEqual(
            data["models"],
            ["Gemini 3.8 Flash (High)", "Gemini 3.8 Flash (Medium)", "Claude Sonnet 4.6 (Thinking)"],
        )

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
