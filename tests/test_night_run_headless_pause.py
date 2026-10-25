"""Prompt ticketu night-run: pauza limitu wykonawcy (kod 75) nie liczy się do prób (#250)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NIGHT_RUN = KIT_ROOT / "templates/shared/agents/night-run.md"


class NightRunHeadlessPauseTest(unittest.TestCase):
    def test_ticket_prompt_excludes_executor_pause_from_attempts(self) -> None:
        text = NIGHT_RUN.read_text(encoding="utf-8")
        self.assertIn("Kod wyjścia wrappera `75`", text)
        self.assertIn("nie liczy się do 2 prób", text)
        self.assertIn("PAUSE=rate-limit reset=<ISO|brak>", text)
        self.assertIn("pauza limitu od <ts>; wznowienie", text)


if __name__ == "__main__":
    unittest.main()
