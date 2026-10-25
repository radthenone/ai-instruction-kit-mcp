"""Skrypt watchdoga nocy night-run (#249) — zachowanie przez wejście i wyjście procesu.

Watchdog śpi w tle i kończy się tylko wtedy, gdy trzeba obudzić orkiestratora: kod 1 przy
anomalii, kod 0 przy minięciu życia, ``krok: koniec``, pauzie (trwa / wznowienie).
Limit czytamy z transkryptu subagenta (nie z logów /headless). Bash przez ``_shell``
(ADR 0005), bez cichego skipu na CI.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from guides.bootstrap import run_bootstrap

from _shell import is_ci, posix_path, resolve_bash

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = KIT_ROOT / "templates" / "shared" / "night-run" / "watchdog.sh"
AGENT_ID = "abc123"
LIMIT_LINE = '{"type":"result","error":"API Error: 429 session limit reached"}\n'


def _bash_or_skip(test: unittest.TestCase) -> str:
    bash = resolve_bash()
    if bash is None:
        if is_ci():
            test.fail("bash niedostępny na CI")
        test.skipTest("bash niedostępny")
    return bash


def _wait_for(predicate, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestWatchdogScript(unittest.TestCase):
    def setUp(self) -> None:
        self.bash = _bash_or_skip(self)
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.dir = root / "night"
        self.dir.mkdir()
        self.home = root / "home"
        self.transcript = self.home / ".claude/projects/proj/sess/subagents" / f"agent-{AGENT_ID}.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.transcript.write_text('{"type":"user","text":"start"}\n', encoding="utf-8")
        self.ctx = self.dir / "context.md"
        self.ctx.write_text(f"# CTX\n\n## Stan\nkrok: ticket\nsubagent: {AGENT_ID}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self, tick: str = "1", recheck: str = "1") -> dict[str, str]:
        env = dict(os.environ)
        env.update(WATCHDOG_TICK_SEC=tick, WATCHDOG_RECHECK_SEC=recheck, HOME=str(self.home))
        return env

    def _start(self, *args: str, tick: str = "1", recheck: str = "1") -> subprocess.Popen:
        return subprocess.Popen(
            [self.bash, posix_path(SCRIPT), posix_path(self.ctx), *args],
            env=self._env(tick=tick, recheck=recheck),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _run(self, *args: str, tick: str = "1", recheck: str = "1") -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.bash, posix_path(SCRIPT), posix_path(self.ctx), *args],
            env=self._env(tick=tick, recheck=recheck),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _pause_lines(self) -> list[str]:
        return [ln for ln in self.ctx.read_text(encoding="utf-8").splitlines()
                if ln.startswith("pauza limitu od ")]

    def _append_transcript(self, text: str) -> None:
        with self.transcript.open("a", encoding="utf-8") as fh:
            fh.write(text)

    def test_no_progress_past_threshold_exits_1(self) -> None:
        result = self._run("0", "110")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("anomalia", result.stdout)

    def test_life_limit_exits_0(self) -> None:
        result = self._run("60", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("życie", result.stdout)

    def test_krok_koniec_exits_0(self) -> None:
        self.ctx.write_text("# CTX\n\n## Stan\nkrok: koniec\n", encoding="utf-8")
        result = self._run("60", "110")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("koniec", result.stdout)

    def test_limit_in_transcript_writes_pause_and_exits_after_recheck(self) -> None:
        proc = self._start("60", "110", recheck="1")
        time.sleep(1.5)
        self._append_transcript(LIMIT_LINE)
        stdout, stderr = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, stdout + stderr)
        self.assertIn("wznowienie po pauzie limitu", stdout)
        open_lines = [ln for ln in self._pause_lines() if " do " not in ln]
        closed_lines = [ln for ln in self._pause_lines() if " do " in ln]
        self.assertEqual(len(open_lines), 1, self.ctx.read_text(encoding="utf-8"))
        self.assertEqual(len(closed_lines), 1, self.ctx.read_text(encoding="utf-8"))

    def test_limit_in_headless_log_is_ignored(self) -> None:
        (self.dir / "headless-x.log").write_text(LIMIT_LINE, encoding="utf-8")
        result = self._run("0", "110")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self._pause_lines(), [])

    def test_fake_429_in_id_or_token_is_not_a_limit(self) -> None:
        self._append_transcript('{"id":"toolu_429abc","token":"x429y"}\n')
        result = self._run("0", "110")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self._pause_lines(), [])

    def test_reset_with_hour_sleeps_until_reset_plus_margin(self) -> None:
        target = datetime.now() + timedelta(minutes=90)
        if target.date() != datetime.now().date():
            self.skipTest("okno przez północ — godzina resetu nieporównywalna")
        clock = target.strftime("%-I:%M%p").lower()
        proc = self._start("60", "110", recheck="1")
        time.sleep(1.5)
        self._append_transcript(f'{{"error":"session limit reached, resets {clock}"}}\n')
        self.assertTrue(_wait_for(lambda: bool(self._pause_lines())))
        proc.kill()
        proc.communicate()
        epoch = int(self._pause_lines()[0].rsplit("epoch ", 1)[1].rstrip(")"))
        expected = int(target.timestamp()) + 300
        self.assertLess(abs(epoch - expected), 120, (epoch, expected))

    def test_no_hour_pause_extends_while_new_limit_lines_arrive(self) -> None:
        proc = self._start("60", "110", recheck="1")
        time.sleep(1.5)
        self._append_transcript(LIMIT_LINE)
        self.assertTrue(_wait_for(lambda: bool(self._pause_lines())))
        self._append_transcript(LIMIT_LINE)  # nowa linia przed sprawdzeniem: pauza ma trwać dalej
        stdout, stderr = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, stdout + stderr)
        open_lines = [ln for ln in self._pause_lines() if " do " not in ln]
        closed_lines = [ln for ln in self._pause_lines() if " do " in ln]
        self.assertGreaterEqual(len(open_lines), 2, self.ctx.read_text(encoding="utf-8"))
        self.assertEqual(len(closed_lines), 1)

    def test_open_pause_on_start_waits_then_exits_0(self) -> None:
        future = int(time.time()) + 2
        self.ctx.write_text(
            "# CTX\n\n## Stan\nkrok: ticket\n"
            f"pauza limitu od 2026-10-25T10:00:00; wznowienie 2026-10-25T10:05:00 (epoch {future})\n",
            encoding="utf-8",
        )
        result = self._run("0", "110")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("wznowienie po pauzie limitu", result.stdout)
        self.assertNotIn("anomalia", result.stdout)

    def test_overdue_open_pause_is_closed_and_loop_runs(self) -> None:
        self.ctx.write_text(
            "# CTX\n\n## Stan\nkrok: ticket\n"
            "pauza limitu od 2026-10-25T10:00:00; wznowienie 2026-10-25T10:05:00 (epoch 1)\n",
            encoding="utf-8",
        )
        result = self._run("0", "110")
        # Przeterminowana pauza nie kończy od razu (bez pętli byłby exit 0 w kółko): idzie do anomalii.
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("anomalia", result.stdout)
        closed = [ln for ln in self._pause_lines() if " do " in ln]
        self.assertEqual(len(closed), 1, self.ctx.read_text(encoding="utf-8"))

    def test_open_pause_longer_than_life_exits_with_renew_message(self) -> None:
        future = int(time.time()) + 3600
        self.ctx.write_text(
            "# CTX\n\n## Stan\nkrok: ticket\n"
            f"pauza limitu od 2026-10-25T10:00:00; wznowienie 2026-10-25T11:00:00 (epoch {future})\n",
            encoding="utf-8",
        )
        result = self._run("60", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pauza trwa", result.stdout)
        self.assertEqual([ln for ln in self._pause_lines() if " do " in ln], [])


class TestWatchdogInstall(unittest.TestCase):
    """Instalacja .ai/night-run-watchdog.sh tylko z klientem claude (#249)."""

    def setUp(self) -> None:
        _bash_or_skip(self)

    def test_installed_for_claude_and_removed_without_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex")
            target = workspace / ".ai/night-run-watchdog.sh"
            self.assertEqual(target.read_bytes(), SCRIPT.read_bytes())
            self.assertTrue(os.access(target, os.X_OK))
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="codex,cursor")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
