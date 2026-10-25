"""Przejęcie ticketu przy limicie wykonawcy (kod 75) w prompcie night-run (#257)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NIGHT_RUN = KIT_ROOT / "templates/shared/agents/night-run.md"


class NightRunTakeoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.night = NIGHT_RUN.read_text(encoding="utf-8")

    def test_exit_75_starts_takeover_subagent_with_verbatim_headless_prompt(self) -> None:
        self.assertIn("subagenta przejęcia", self.night)
        self.assertIn("DOSŁOWNIE tą samą treścią", self.night)

    def test_limit_mode_switch_defaults_to_takeover(self) -> None:
        self.assertIn("`limit: przejmij`", self.night)
        self.assertIn("`limit: czekaj`", self.night)
        self.assertIn("domyślny", self.night)

    def test_takeover_alias_goal_override_is_documented(self) -> None:
        self.assertIn("`przejęcie: <alias>`", self.night)

    def test_takeover_model_source_order(self) -> None:
        self.assertIn("models.claude.takeover", self.night)
        source_order = self.night.index("tekst celu") < self.night.index("models.claude.takeover")
        self.assertTrue(source_order)
        self.assertIn("model sesji", self.night)

    def test_takeover_inherits_session_effort(self) -> None:
        self.assertIn("dziedziczy effort sesji", self.night)

    def test_takeover_commits_locally_and_keeps_nesting_limit(self) -> None:
        self.assertIn("limit zagnieżdżenia 3", self.night)


if __name__ == "__main__":
    unittest.main()
