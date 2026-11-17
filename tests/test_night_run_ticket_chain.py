"""Testy kontraktu łańcucha wykonawców i modeli w sesji ticketu night-run (#464).

Szwy testowe z kryteriów ukończenia issue #464:
- 4 ścieżki (brak wskazania, /headless, implementacja: z delegacją, bez delegacji),
- trzy reguły porażki (brak commita i hand-backu, limit/quota, przekroczony czas),
- needs-human po wyczerpaniu łańcucha i dla wykonawcy spoza clients:,
- szablon zlecenia delegata (komenda testów z timeout, hand-back, log postępu w CTX, temat commita w języku Profilu),
- raport per krok (transport, model, przejścia na zapas; koszt delegata n/a bez logów),
- opis skilla: „w nocy albo w dzień”.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
TICKET_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"
COPIES = (
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


class TestNightRunTicketChainContract(unittest.TestCase):
    def setUp(self) -> None:
        self.night_run = TEMPLATE.read_text(encoding="utf-8")
        self.ticket = TICKET_TEMPLATE.read_text(encoding="utf-8")

    def test_skill_description_night_or_day(self) -> None:
        """Opis skilla mówi „w nocy albo w dzień” zamiast wyłącznie „nocna praca”."""
        desc_line = next(ln for ln in self.night_run.splitlines() if ln.startswith("description:"))
        self.assertIn("w nocy albo w dzień", desc_line)

    def test_four_implementation_paths(self) -> None:
        """Procedura definiuje 4 ścieżki implementacji w sesji ticketu:
        1. brak wskazania -> implementacja bezpośrednia w subagencie ticketu (test-first: test czerwony → kod → zielony → commit),
        2. /headless -> wrapper .ai/headless.mjs,
        3. implementacja: z delegacją -> sesja ticketu uruchamia natywnego delegata w checkoucie sesji ticketu,
        4. implementacja: bez delegacji -> sesja ticketu woła /headless <wykonawca> --model <model>.
        """
        # Ścieżka 1: brak wskazania (bez /headless)
        self.assertIn("brak wskazania", self.ticket)
        self.assertIn("Test-first: test czerwony → kod → zielony → commit", self.ticket)

        # Ścieżka 2: jawne /headless
        self.assertIn("/headless <wykonawca>", self.ticket)

        # Ścieżka 3: implementacja: z delegacją (natywna delegacja klienta)
        self.assertIn("natywna delegacja", self.ticket)

        # Ścieżka 4: implementacja: bez delegacji (/headless <wykonawca> --model <model>)
        self.assertIn("/headless <wykonawca> --model <model>", self.ticket)
        self.assertIn(
            "ewentualne wewnętrzne przekazania wrappera (przejścia fallback) należy odnotować w raporcie hand-backu jako przejścia na zapas",
            self.ticket,
        )

        # Kolejny model wyłącznie po wskazanej porażce; zatrzymanie łańcucha po commicie
        self.assertIn("wyłącznie po wskazanej porażce", self.ticket)
        self.assertIn("kończy łańcuch, aby kolejny model nie powtarzał zadania", self.ticket)

        # Wszystkie 4 ścieżki i ich rozróżnienie są udokumentowane w procedurze ticketu
        self.assertIn("4 ścieżki", self.ticket)

    def test_syntax_krok_wartosc_and_chain_structure(self) -> None:
        """Składnia krok: wartość (implementacja:, review:, effort:), średnik i przecinek, @poziom, wolny tekst."""
        self.assertIn("implementacja: <wykonawca>", self.night_run)
        self.assertIn("krok: wartość", self.night_run)
        self.assertIn("review:", self.night_run)
        self.assertIn("effort:", self.night_run)
        self.assertIn("średnik rozdziela wykonawców", self.night_run.lower())
        self.assertIn("przecinek modele jednego wykonawcy", self.night_run.lower())
        self.assertIn("@poziom", self.night_run)
        self.assertIn("wolny tekst", self.night_run)

    def test_three_failure_rules(self) -> None:
        """Trzy reguły porażki wykonawcy powodujące przejście do następnego modelu:
        1. brak commita i brak hand-backu,
        2. limit albo quota wykonawcy,
        3. przekroczony czas.
        """
        self.assertIn("trzy reguły porażki", self.ticket.lower())
        self.assertIn("brak commita i brak hand-backu", self.ticket)
        self.assertIn("limit albo quota wykonawcy", self.ticket)
        self.assertIn("przekroczony czas", self.ticket)
        self.assertIn("następny model", self.ticket)
        self.assertIn("niezależnie od tego, czy delegat pozostawił niezacommitowane zmiany", self.ticket)

    def test_needs_human_on_chain_exhaustion_and_unknown_executor(self) -> None:
        """Łańcuch wyczerpany -> needs-human dla ticketu, noc idzie dalej;
        Wykonawca spoza clients: -> needs-human na starcie nocy.
        """
        # Wyczerpany łańcuch w procedurze ticketu
        self.assertIn("łańcuch wyczerpany", self.ticket.lower())
        self.assertIn("needs-human", self.ticket)
        self.assertIn("noc idzie dalej", self.ticket)

        # Start nocy: wykonawca spoza clients:
        self.assertIn("wykonawca spoza `clients:`", self.night_run)
        self.assertIn("needs-human na starcie nocy", self.night_run)

    def test_delegate_order_template(self) -> None:
        """Szablon zlecenia delegata zawiera:
        - komendę testów z timeout,
        - obowiązkowy hand-back,
        - log postępu w CTX,
        - temat commita w języku Profilu,
        oraz delegat pracuje w checkoucie sesji ticketu na branchu z /git-start.
        """
        self.assertIn("szablon zlecenia delegata", self.ticket.lower())
        self.assertIn("komenda testów z `timeout`", self.ticket)
        self.assertIn("obowiązkowy hand-back", self.ticket)
        self.assertIn("log postępu w CTX", self.ticket)
        self.assertIn("temat commita w języku Profilu", self.ticket)
        self.assertIn("w checkoucie sesji ticketu, na branchu z `/git-start`", self.ticket)

    def test_report_per_step_and_delegate_cost(self) -> None:
        """Raport per krok odnotowuje transport, model, przejścia na zapas,
        a koszt delegata to n/a, gdy transport nie zostawia logów.
        """
        self.assertIn("transport", self.night_run)
        self.assertIn("przejścia na zapas", self.night_run)
        self.assertIn("Koszt delegata `n/a`, gdy transport nie zostawia logów", self.night_run)

    def test_ticket_session_runs_chain(self) -> None:
        """Sesja ticketu prowadzi łańcuch, orkiestrator zleca tylko ticket i trzyma jedną linię stanu."""
        self.assertIn("Łańcuch prowadzi sesja ticketu", self.night_run)
        self.assertIn("Orkiestrator zleca tylko ticket i trzyma jedną linię stanu", self.night_run)

    def test_all_rendered_copies_updated(self) -> None:
        """Kopie wygenerowane przez kit-ai reload zawierają kluczowe szwy."""
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("w nocy albo w dzień", copy)
                self.assertIn("Łańcuch prowadzi sesja ticketu", copy)
        for rel in TICKET_COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("4 ścieżki", copy)
                self.assertIn("trzy reguły porażki", copy.lower())
