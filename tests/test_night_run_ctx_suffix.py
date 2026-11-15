"""Testy kontraktu sufiksu CTX dla równoległych sesji procedury night-run (#462).

Weryfikuje zakres z issue #462:
- cel `ctx: <sufiks>` -> `night-run-<repo>-<data>-<sufiks>`,
- bez `ctx:`: katalog dnia istnieje, a jego `## Stan` ma krok ≠ `koniec` -> automatyczny sufiks `-b`, `-c`… z linią w raporcie,
- ticket z listy, który inny CTX tego dnia ma w `## Stan` jako trwający -> pominięty, `skipped: w innej nocy <katalog>`,
- CronCreate i watchdog nie kolidują między równoległymi nocami,
- kopie szablonu night-run u klientów zachowują ten sam kontrakt.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_NIGHT_RUN = ROOT / "templates" / "shared" / "agents" / "night-run.md"

NIGHT_RUN_COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)


class TestNightRunCtxSuffixContract(unittest.TestCase):
    """Weryfikacja kontraktu sufiksu CTX dla równoległych nocy (#462)."""

    def setUp(self) -> None:
        self.text = TEMPLATE_NIGHT_RUN.read_text(encoding="utf-8")

    @property
    def queue_section(self) -> str:
        return self.text.split("### 4. Kolejka", 1)[1].split("### 5. Kolejność", 1)[0]

    @property
    def ctx_section(self) -> str:
        return self.text.split("### 6. Plik kontekstu nocy", 1)[1].split("### 7. Watchdog i cron", 1)[0]

    @property
    def report_section(self) -> str:
        return self.text.split("## NIGHT-RUN REPORT", 1)[1]

    def test_goal_ctx_suffix_specified_in_priorities_or_args(self) -> None:
        """Cel z `ctx: <sufiks>` jest wymieniony jako polecenie z tekstu celu / argumentów."""
        self.assertIn("`ctx: <sufiks>`", self.text)

    def test_ctx_directory_with_suffix_format(self) -> None:
        """Krok 6 określa format katalogu z sufiksem z celu: night-run-<repo>-<data>-<sufiks>."""
        ctx_sec = self.ctx_section
        self.assertIn("`CTX_DIR=~/.cache/night-run-<repo>-<data>-<sufiks>/`", ctx_sec)
        self.assertIn("`ctx: <sufiks>`", ctx_sec)

    def test_auto_suffix_when_active_night_exists(self) -> None:
        """Bez ctx:, gdy katalog dnia ma krok != koniec, przydzielany jest automatyczny sufiks -b, -c... z linią w raporcie."""
        ctx_sec = self.ctx_section
        self.assertIn("Bez `ctx:`", ctx_sec)
        self.assertIn("krok ≠ `koniec`", ctx_sec)
        self.assertIn("-b", ctx_sec)
        self.assertIn("-c", ctx_sec)
        self.assertIn("Sufiks CTX:", ctx_sec)

    def test_skip_ticket_in_progress_in_another_night(self) -> None:
        """Ticket, który inny CTX tego dnia ma w ## Stan jako trwający, zostaje pominięty z skipped: w innej nocy <katalog>."""
        queue_sec = self.queue_section
        self.assertIn("skipped: w innej nocy <katalog>", queue_sec)
        self.assertIn("krok ≠ `koniec`", queue_sec)

    def test_report_includes_ctx_suffix_and_skipped_in_other_night(self) -> None:
        """NIGHT-RUN REPORT ma linię Sufiks CTX oraz stan skipped: w innej nocy w tabeli."""
        rep = self.report_section
        self.assertIn("Sufiks CTX:", rep)
        self.assertIn("skipped: w innej nocy <katalog>", rep)

    def test_cron_isolated_per_ctx(self) -> None:
        """CronCreate w kroku 7 sprawdza istnienie crona dla tego CTX / tej nocy, nie blokując równoległej nocy."""
        watchdog_sec = self.text.split("### 7. Watchdog i cron", 1)[1].split("## Łańcuch na ticket", 1)[0]
        self.assertIn("CronList", watchdog_sec)
        self.assertIn("CronCreate", watchdog_sec)
        self.assertIn("<CTX>", watchdog_sec)

    def test_all_client_copies_contain_ctx_suffix_contract(self) -> None:
        """Wszystkie wyrenderowane kopie u klientów zawierają kontrakt sufiksu CTX i pomijania ticketu z innej nocy."""
        for rel in NIGHT_RUN_COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("`ctx: <sufiks>`", copy)
                self.assertIn("`CTX_DIR=~/.cache/night-run-<repo>-<data>-<sufiks>/`", copy)
                self.assertIn("skipped: w innej nocy <katalog>", copy)
                self.assertIn("Sufiks CTX:", copy)


if __name__ == "__main__":
    unittest.main()
