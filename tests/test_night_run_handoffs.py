"""Testy kontraktu szablonów procedury night-run dla przekazań (handoffs) (#461).

Weryfikuje zakres z issue #461:
- Przekazanie zapisywane do $CTX_DIR/handoff-<N>.md (≤ 30 linii),
- W context.md zostaje tylko indeks #N → handoff-<N>.md,
- Prompt ticketu wskazuje tylko handoffy blokujących przechodnio z listy nocy (brak blokujących -> brak handoffów),
- Orkiestrator trzyma w rozmowie tylko jedną linię stanu na ticket (#N: <stan> <PR> <koszt>),
- night-run-ticket.md czyta tylko wskazane handoffy,
- NIGHT-RUN REPORT czyta wszystkie handoff-*.md (sekcja per issue),
- Kopie szablonów u klientów zachowują ten sam kontrakt.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_NIGHT_RUN = ROOT / "templates" / "shared" / "agents" / "night-run.md"
TEMPLATE_TICKET = ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"

NIGHT_RUN_COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)

TICKET_COPIES = (
    ".claude/agents/night-run-ticket.md",
    ".claude/commands/night-run-ticket.md",
    ".codex/skills/night-run-ticket/SKILL.md",
    ".github/prompts/night-run-ticket.prompt.md",
    ".opencode/command/night-run-ticket.md",
)


class TestNightRunHandoffContract(unittest.TestCase):
    def setUp(self) -> None:
        self.night_run = TEMPLATE_NIGHT_RUN.read_text(encoding="utf-8")
        self.ticket = TEMPLATE_TICKET.read_text(encoding="utf-8")

    def test_context_md_keeps_only_index_and_handoff_is_separate_file(self) -> None:
        """Krok 6: Przekazanie do osobnego pliku handoff-<N>.md, w context.md tylko indeks."""
        self.assertIn("handoff-<N>.md", self.night_run)
        self.assertIn("#N → handoff-<N>.md", self.night_run)
        self.assertIn("≤ 30 linii", self.night_run)
        # Upewnij się, że w context.md jest tylko indeks, a nie całe Przekazanie
        self.assertIn("w `context.md` zostaje tylko indeks", self.night_run)

    def test_orchestrator_state_line_in_conversation(self) -> None:
        """Krok 5 łańcucha: hand-back do pliku, w rozmowie orkiestratora jedna linia stanu."""
        self.assertIn("#N: <stan> <PR> <koszt>", self.night_run)

    def test_ticket_prompt_scopes_handoffs_to_transitive_blockers(self) -> None:
        """Prompt ticketu podaje listę handoff-<B>.md blokujących przechodnio z listy nocy."""
        self.assertIn("handoff-<B>.md", self.night_run)
        self.assertIn("blokujących", self.night_run)
        self.assertIn("brak blokujących", self.night_run)

    def test_night_run_ticket_agent_reads_only_indicated_handoffs(self) -> None:
        """night-run-ticket.md czyta tylko wskazane handoffy blokujących."""
        self.assertIn("wskazane", self.ticket)
        self.assertIn("handoff", self.ticket)

    def test_night_run_report_reads_all_handoff_files(self) -> None:
        """NIGHT-RUN REPORT czyta wszystkie handoff-*.md (sekcja per issue)."""
        self.assertIn("handoff-*.md", self.night_run)
        self.assertIn("## Przekazania", self.night_run)

    def test_all_rendered_copies_contain_handoff_contract(self) -> None:
        """Wszystkie kopie szablonów u klientów zachowują kontrakt handoffów."""
        for rel in NIGHT_RUN_COPIES:
            with self.subTest(copy=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("handoff-<N>.md", text)
                self.assertIn("#N → handoff-<N>.md", text)
                self.assertIn("handoff-<B>.md", text)
                self.assertIn("## Przekazania", text)

        for rel in TICKET_COPIES:
            with self.subTest(ticket_copy=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("wskazane", text)
                self.assertIn("handoff", text)


if __name__ == "__main__":
    unittest.main()
