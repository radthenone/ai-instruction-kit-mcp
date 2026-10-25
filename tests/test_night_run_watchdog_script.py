"""Skrypt watchdoga nocy night-run (#249) — zachowanie przez wejście i wyjście procesu.

Watchdog śpi w tle i kończy się tylko wtedy, gdy trzeba obudzić orkiestratora:
exit 1 przy anomalii, exit 0 przy minięciu życia, ``krok: koniec`` albo wznowieniu po pauzie.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = KIT_ROOT / "templates" / "shared" / "night-run" / "watchdog.sh"


class TestWatchdogScript(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "night"
        self.dir.mkdir()
        self.ctx = self.dir / "context.md"
        self.ctx.write_text("# CTX\n\n## Stan\nkrok: ticket\n", encoding="utf-8")
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self, tick: str = "1", recheck: str = "1") -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            WATCHDOG_TICK_SEC=tick,
            WATCHDOG_RECHECK_SEC=recheck,
            HOME=str(self.home),
        )
        return env

    def _run(self, *args: str, timeout: float = 30, **kw: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.ctx), *args],
            env=self._env(**kw),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_no_progress_past_threshold_exits_1(self) -> None:
        # Próg 0 min: pierwszy krok bez postępu to anomalia.
        result = self._run("0", "110")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("anomalia", result.stdout)

    def test_life_limit_exits_0(self) -> None:
        # Życie 0 min: po pierwszym kroku watchdog kończy się, orkiestrator go odnawia.
        result = self._run("60", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("życie", result.stdout)

    def test_krok_koniec_exits_0(self) -> None:
        self.ctx.write_text("# CTX\n\n## Stan\nkrok: koniec\n", encoding="utf-8")
        result = self._run("60", "110")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("koniec", result.stdout)

    def test_limit_message_writes_pause_and_exits_0_after_resume(self) -> None:
        # Komunikat limitu pojawia się po starcie (w logu headless), więc nie jest ignorowany.
        log = self.dir / "headless.log"
        log.write_text("start\n", encoding="utf-8")
        proc = subprocess.Popen(
            ["bash", str(SCRIPT), str(self.ctx), "60", "110"],
            env=self._env(tick="1", recheck="1"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(1.5)
        with log.open("a", encoding="utf-8") as fh:
            fh.write("Error: rate limit reached\n")
        stdout, stderr = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 0, stdout + stderr)
        stan = self.ctx.read_text(encoding="utf-8")
        pause = [ln for ln in stan.splitlines() if ln.startswith("pauza limitu od ")]
        self.assertEqual(len(pause), 1, stan)
        self.assertNotIn(" do ", pause[0])
        self.assertIn("(epoch ", pause[0])

    def test_open_pause_on_start_waits_then_exits_0(self) -> None:
        # Otwarta pauza (bez „do”) z epoch w przeszłości: watchdog nie sprawdza anomalii, kończy się.
        self.ctx.write_text(
            "# CTX\n\n## Stan\nkrok: ticket\n"
            "pauza limitu od 2026-10-25T10:00:00; wznowienie 2026-10-25T10:05:00 (epoch 1)\n",
            encoding="utf-8",
        )
        result = self._run("0", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("anomalia", result.stdout)


if __name__ == "__main__":
    unittest.main()
