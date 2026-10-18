"""Night-run bez wymogu `/goal`, z wykonawcą `/headless` i skillami review z argumentów (#214)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)


class TestNightRunArgs(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")
        self.description = next(ln for ln in self.text.splitlines() if ln.startswith("description:"))

    def test_goal_not_required(self) -> None:
        self.assertNotIn("pod /goal", self.description)
        self.assertIn("`/goal` opcjonalny", self.text)
        self.assertIn("Wznawianie nocy = heartbeat `CronCreate`", self.text)

    def test_args_syntax(self) -> None:
        self.assertIn(
            '/night-run #N1 #N2 [/headless <wykonawca> [--model …] [--timeout …] [--heartbeat …] "<treść>"] [/review-* …]',
            self.text,
        )
        self.assertIn("flagi wrappera przekazujesz bez zmian", self.text)

    def test_exec_validated_at_start(self) -> None:
        self.assertIn("`EXEC` sprawdzasz raz na starcie nocy", self.text)
        self.assertIn("nieznany wykonawca → needs-human na starcie nocy", self.text)

    def test_headless_replaces_steps_2_3(self) -> None:
        self.assertIn('2–3. (z `/headless`) `/headless <wykonawca> [flagi] "<treść>"` z flagami i treścią bez zmian', self.text)
        self.assertIn("Sam nie piszesz kodu", self.text)
        self.assertIn("Dalej kroki 4–5", self.text)
        self.assertIn("dosłownie, poza wyborem wariantu kroków 2–3", self.text)
        self.assertIn("klient bez `/headless`", self.text)

    def test_review_skills_from_args(self) -> None:
        self.assertIn("Skille review z argumentów", self.text)
        self.assertIn("przez Skill", self.text)
        self.assertIn("nieznany skill review → needs-human na starcie nocy", self.text)
        self.assertIn("Bez argumentów — **subagent review**", self.text)
        self.assertIn("Przed review — w obu wariantach — nadpisz `## Stan` (krok `review`", self.text)
        chain = self.text.split("## Łańcuch na ticket", 1)[1]
        self.assertLess(chain.index("2. **Review.**"), chain.index("Dalej kroki 6–8 promptu"))

    def test_cost_note_for_headless_and_inline_review(self) -> None:
        self.assertIn("koszt bez wykonawcy headless i review w sesji głównej", self.text)

    def test_report_lists_executor_and_review(self) -> None:
        self.assertIn("| Ticket | Stan | Wykonawca | Review | Dowód |", self.text)

    def test_reload_refreshed_client_copies(self) -> None:
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("Skille review z argumentów", copy)
                self.assertIn("`/goal` opcjonalny", copy)


if __name__ == "__main__":
    unittest.main()
