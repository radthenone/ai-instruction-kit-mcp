"""Przejęcie ticketu przy limicie wykonawcy (kod 75) w prompcie night-run (#257)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NIGHT_RUN = KIT_ROOT / "templates/shared/agents/night-run.md"
TICKET_TEMPLATE = KIT_ROOT / "templates/shared/agents/night-run-ticket.md"


class NightRunTakeoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.night = NIGHT_RUN.read_text(encoding="utf-8")
        self.ticket = TICKET_TEMPLATE.read_text(encoding="utf-8")

    def test_exit_75_starts_takeover_subagent_with_verbatim_headless_prompt(self) -> None:
        self.assertIn("subagenta przejęcia", self.ticket)
        self.assertIn("DOSŁOWNIE tą samą treścią", self.ticket)

    def test_limit_mode_switch_defaults_to_takeover(self) -> None:
        self.assertIn("`LIMIT: przejmij` (domyślny)", self.ticket)
        self.assertIn("`LIMIT: czekaj`", self.ticket)
        self.assertIn("zostaje powyższa pauza do resetu", self.ticket)

    def test_takeover_alias_goal_override_is_documented(self) -> None:
        self.assertIn("`przejęcie: <alias>`", self.night)

    def test_orchestrator_resolves_limit_and_takeover_for_ticket_subagent(self) -> None:
        # Subagent ticketu nie widzi tekstu celu — wartości rozstrzyga orkiestrator w łańcuchu.
        chain = self.night.index("## Łańcuch na ticket")
        self.assertIn("`LIMIT`", self.night[chain:])
        self.assertIn("`PRZEJĘCIE`", self.night[chain:])

    def test_takeover_model_source_order(self) -> None:
        chain = self.night.index("## Łańcuch na ticket")
        goal = self.night.index("tekst celu", chain)
        profile = self.night.index("targets.claude.takeover", chain)
        session = self.night.index("`sesja`", chain)
        self.assertLess(goal, profile)
        self.assertLess(profile, session)

    def test_unknown_goal_alias_falls_back_to_session_with_report_note(self) -> None:
        self.assertIn("nieznany alias przejęcia", self.night)

    def test_takeover_inherits_session_effort(self) -> None:
        self.assertIn("dziedziczy effort sesji", self.ticket)

    def test_takeover_commits_locally_and_keeps_nesting_limit(self) -> None:
        self.assertIn("przy limicie zagnieżdżenia 3", self.ticket)
        self.assertNotIn("przy limit zagnieżdżenia", self.ticket)

    def test_failed_takeover_is_needs_human_not_a_wrapper_attempt(self) -> None:
        self.assertIn("Przejęcie, które pada", self.ticket)
        self.assertIn("needs-human", self.ticket)
        self.assertIn("nie liczy się jako druga próba wrappera", self.ticket)

    def test_report_has_takeover_executor_variant(self) -> None:
        self.assertIn("opencode → przejęte (<model>, limit)", self.night)
        self.assertIn("przejęcie: <model> (<źródło>)", self.night)

    def test_wrapper_failure_is_one_full_chain_path_not_two_attempts(self) -> None:
        # Wrapper sam przechodzi łańcuch 1:1 (#397), więc ponowienie tym samym wykonawcą to zbędna próba.
        self.assertIn("nie ponawiasz go tym samym wykonawcą", self.ticket)
        self.assertIn("jedna pełna ścieżka", self.ticket)
        self.assertNotIn("maks. 2 próby, potem needs-human", self.night)

    def test_ticket_points_opencode_model_to_targets(self) -> None:
        self.assertNotIn("models.opencode", self.ticket)
        self.assertIn("`targets.opencode`", self.ticket)

    def test_exhausted_chain_without_limit_goes_to_takeover(self) -> None:
        self.assertIn("Wyczerpany łańcuch bez limitu", self.ticket)
        self.assertIn("klasa `HANG` albo `ERROR`", self.ticket)


class KitProjectEditTakeoverTest(unittest.TestCase):
    def test_kit_project_edit_describes_takeover_key(self) -> None:
        text = (KIT_ROOT / "templates/shared/agents/kit-project-edit.md").read_text(encoding="utf-8")
        self.assertIn("`targets.<klient>.takeover`", text)
        self.assertIn("`haiku` \\| `sonnet` \\| `opus` \\| `fable`", text)


if __name__ == "__main__":
    unittest.main()
