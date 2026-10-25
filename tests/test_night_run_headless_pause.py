"""Pauza limitu wykonawcy (kod 75) w prompcie night-run i zgodność formatu z watchdogiem (#250)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NIGHT_RUN = KIT_ROOT / "templates/shared/agents/night-run.md"
HEADLESS_MD = KIT_ROOT / "templates/shared/agents/headless.md"
WATCHDOG = KIT_ROOT / "templates/shared/night-run/watchdog.sh"


class NightRunHeadlessPauseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.night = NIGHT_RUN.read_text(encoding="utf-8")

    def test_ticket_prompt_excludes_executor_pause_from_attempts(self) -> None:
        self.assertIn("Kod wyjścia wrappera `75`", self.night)
        self.assertIn("nie liczy się do 2 prób", self.night)
        self.assertIn("PAUSE=rate-limit reset=<ISO|brak>", self.night)

    def test_pause_entry_format_is_the_watchdog_printf_format(self) -> None:
        watchdog = WATCHDOG.read_text(encoding="utf-8")
        self.assertIn("printf 'pauza limitu od %s; wznowienie %s (epoch %s)\\n'", watchdog)
        self.assertIn("pauza limitu od <ts>; wznowienie <ts> (epoch N)", self.night)

    def test_reset_brak_writes_recheck_epoch_and_who_closes(self) -> None:
        self.assertIn("gdy `reset=brak`, wpisz «nieznana»", self.night)
        self.assertIn("`wznowienie <teraz+30 min> (epoch N)`", self.night)
        self.assertIn("watchdog dopisuje `do`", self.night)
        self.assertNotIn("bez `brak`", self.night)

    def test_executor_pause_is_handled_in_watchdog_tick_and_case_d(self) -> None:
        self.assertGreaterEqual(self.night.count("pauza wykonawcy do"), 3)
        self.assertIn("nie liczy się do wznowień ticketu", self.night)

    def test_headless_doc_describes_pause_exit_code(self) -> None:
        text = HEADLESS_MD.read_text(encoding="utf-8")
        self.assertIn("PAUSE=rate-limit", text)
        self.assertIn("`75`", text)


if __name__ == "__main__":
    unittest.main()
