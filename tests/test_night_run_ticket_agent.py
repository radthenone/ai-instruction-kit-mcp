"""Testy agenta night-run-ticket i procedury night-run (#316).

Procedura night-run (szablon i wszystkie wyrenderowane kopie) uruchamia subagenta
ticketu typem night-run-ticket (zamiast general-purpose). Agent jest instalowany
dla klienta claude i ma klasyfikację 'procedure'.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "shared" / "agents" / "night-run.md"
TICKET_AGENT_TEMPLATE = ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"

COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)


class NightRunTicketAgentTest(unittest.TestCase):
    def test_night_run_ticket_agent_template_exists_with_procedure_classification(self) -> None:
        self.assertTrue(TICKET_AGENT_TEMPLATE.is_file(), "templates/shared/agents/night-run-ticket.md musi istnieć")
        text = TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("name: night-run-ticket", text)
        self.assertIn("classification: procedure", text)

    def test_night_run_ticket_agent_installed_for_claude(self) -> None:
        installed = ROOT / ".claude" / "agents" / "night-run-ticket.md"
        self.assertTrue(installed.is_file(), ".claude/agents/night-run-ticket.md musi istnieć")

    def test_night_run_template_spawns_ticket_subagent_with_night_run_ticket_type(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("night-run-ticket", text)

    def test_all_rendered_client_copies_spawn_night_run_ticket(self) -> None:
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("night-run-ticket", copy)


if __name__ == "__main__":
    unittest.main()
