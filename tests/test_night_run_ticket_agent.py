"""Testy agenta night-run-ticket i procedury night-run (#316).

Procedura night-run (szablon i wszystkie wyrenderowane kopie) uruchamia subagenta
ticketu typem night-run-ticket (zamiast general-purpose). Agent jest instalowany
dla klienta claude i ma klasyfikację 'procedure'.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from command_prefix import resolve

TEMPLATE = ROOT / "templates" / "shared" / "agents" / "night-run.md"
TICKET_AGENT_TEMPLATE = ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"
T3_CARD_TEMPLATE = ROOT / "templates" / "shared" / "night-run" / "t3.md"

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
        text = resolve(TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8"))
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

    def test_separation_of_ticket_prompt_and_order_fields(self) -> None:
        """Kroki ticketu mieszkają w night-run-ticket.md, a night-run.md zawiera tylko pola zlecenia (#473)."""
        night_run = resolve(TEMPLATE.read_text(encoding="utf-8"))
        ticket = resolve(TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8"))

        markers = (
            "`/git-start #<N>`",
            "--- po wznowieniu ---",
            "**Sprawdzenie przed merge",
            "Hand-back (bez streszczania pracy)",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, ticket, f"Marker '{marker}' powinien znajdować się w night-run-ticket.md")
                self.assertNotIn(marker, night_run, f"Marker '{marker}' NIE powinien znajdować się w night-run.md")

        order_fields = (
            "Ticket #N",
            "BASE",
            "CTX",
            "Handoffy blokujących:",
            "Wykonawca:",
            "LIMIT",
            "PRZEJĘCIE:",
            "Nadpisania:",
            "Polecenia z celu dla ticketu:",
            "Język wyjścia:",
        )
        for field in order_fields:
            with self.subTest(order_field=field):
                self.assertIn(field, night_run, f"Pole zlecenia '{field}' powinno znajdować się w night-run.md")

    def test_pr_forwards_issue_labels_and_clean_title(self) -> None:
        """Krok 6: etykiety issue bez procesowych idą flagami --label; tytuł PR bez (night-run) (#499)."""
        ticket = TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("gh issue view <N> --json labels", ticket)
        for label in ("ready-for-agent", "ready-for-human", "needs-info", "needs-triage", "wontfix"):
            with self.subTest(label=label):
                self.assertIn(f"`{label}`", ticket)
        self.assertIn('--label "<etykieta>"', ticket)
        self.assertIn("wszystkie etykiety issue", ticket)
        self.assertNotIn("sekcji „Etykiety” w `git-end`", ticket)
        self.assertNotIn("`type: *`, kategoria, `scope: *`", ticket)
        self.assertIn("gh label list --limit 1000 --json name", ticket)
        self.assertIn("potwierdzono brak", ticket)
        self.assertIn("""--label '"backend,api"'""", ticket)
        self.assertIn("podwajasz", ticket)
        self.assertIn("`gh pr create`", ticket)
        self.assertIn("bez prefiksu `(night-run)`", ticket)

    def test_repair_push_reviews_entire_section_with_problem_classes(self) -> None:
        """Przed pushem poprawki agent przegląda całą zmienianą sekcję pod kątem listy klas (#512)."""
        ticket = TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8")
        paragraph = ticket.split("**Wątki review bota (CodeRabbit):**", 1)[1].split("**Sufit napraw", 1)[0]
        self.assertIn("przed pushem poprawki", paragraph.lower())
        self.assertIn("przegląda całą zmienianą sekcję", paragraph)
        classes = (
            "idempotencja i wznowienie po przerwaniu",
            "kolejność zapisu stanu",
            "polecenia o zakresie globalnym (np. `git worktree prune`)",
            "nadpisywanie plików ignorowanych",
            "brak katalogu, rekordu lub pusty wynik",
            "spójność z `git-end`",
        )
        for cls_name in classes:
            with self.subTest(cls_name=cls_name):
                self.assertIn(cls_name, paragraph)

    def test_problem_class_list_matches_t3_card(self) -> None:
        """Lista klas problemów w procedurze ticketu i w karcie T3 jest identyczna (#512)."""

        def class_list(text: str) -> str:
            start = text.index("idempotencja i wznowienie po przerwaniu")
            end = text.index("spójność z `git-end`", start)
            return text[start:end]

        ticket = TICKET_AGENT_TEMPLATE.read_text(encoding="utf-8")
        card = T3_CARD_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(class_list(ticket), class_list(card))


if __name__ == "__main__":
    unittest.main()
