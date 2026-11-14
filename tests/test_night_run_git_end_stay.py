"""Testy kontraktu szablonów night-run i git-end dla flagi --stay oraz obsługi worktree (#472).

Sprawdzają:
- night-run krok 5: w linked worktree ([ -f .git ]) switch na origin/$BASE zamiast checkout $BASE && git pull,
- night-run prompt ticketu: wywołanie /git-end --stay,
- git-end sekcje pomocy i wywołań: opis flagi --stay,
- git-end krok 5: flaga --stay pomija powrót na poprzedni branch,
- git-end krok 5: PREV zajęty w innym worktree -> pozostanie na branchu ticketu bez błędu,
- git-end krok 6 i Zakazy: zakaz oddawania raportu bez końcowego stanu gh pr checks.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NIGHT_RUN_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
GIT_END_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "git-end.md"


def _section(text: str, start: str, end: str) -> str:
    """Zwraca fragment szablonu między nagłówkami z normalizacją białych znaków."""
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


class TestNightRunGitEndStay(unittest.TestCase):
    def setUp(self) -> None:
        self.night_run = NIGHT_RUN_TEMPLATE.read_text(encoding="utf-8")
        self.git_end = GIT_END_TEMPLATE.read_text(encoding="utf-8")

    def test_night_run_chain_step_5_worktree_detached_switch(self) -> None:
        """Krok 5 łańcucha w linked worktree przełącza na origin/$BASE --detach, a w głównym checkoucie robi checkout && pull."""
        chain_step_5 = _section(self.night_run, "5. Zapisz Przekazanie", "## Prompt ticketu")
        self.assertIn(".git", chain_step_5)
        self.assertRegex(chain_step_5, r"(?:\[ -f \.git \]|test -f \.git|gdy `?\.git`? jest plikiem)")
        self.assertIn("git fetch origin", chain_step_5)
        self.assertIn("git switch --detach origin/$BASE", chain_step_5)
        self.assertIn("git checkout $BASE && git pull", chain_step_5)

    def test_night_run_ticket_prompt_calls_git_end_stay(self) -> None:
        """Prompt ticketu w night-run woła /git-end --stay."""
        prompt = _section(self.night_run, "## Prompt ticketu", "## Testy")
        self.assertIn("/git-end --stay", prompt)

    def test_git_end_help_and_invocations_document_stay(self) -> None:
        """Pomoc i tabela wywołań w git-end opisują flagę --stay."""
        help_section = _section(self.git_end, "## `--help`", "## Algorytm")
        self.assertIn("--stay", help_section)
        self.assertIn("`/git-end --stay`", help_section)
        self.assertRegex(help_section, r"--stay.*(?:pomija powrót|zostaje na branchu|bez powrotu)")

    def test_git_end_step_5_stay_flag_skips_return(self) -> None:
        """Krok 5 w git-end: flaga --stay pomija powrót na poprzedni branch i zostaje na branchu ticketu."""
        step_5 = _section(self.git_end, "### 5. Powrót na branch sprzed `/git-start`", "### 6. Raport")
        self.assertIn("--stay", step_5)
        self.assertRegex(step_5, r"--stay.*(?:pomija powrót|zostawia checkout|zostaje)")

    def test_git_end_step_5_busy_prev_in_another_worktree_stays_without_error(self) -> None:
        """Krok 5 w git-end: bez flagi --stay, gdy PREV jest zajęty w innym worktree, agent zostaje na branchu ticketu bez błędu."""
        step_5 = _section(self.git_end, "### 5. Powrót na branch sprzed `/git-start`", "### 6. Raport")
        self.assertIn("worktree", step_5)
        self.assertRegex(step_5, r"(?:innym worktree|zajęty|zajety).*(?:zostań|zostan|pozostaje|zostaje|bez błędu|bez bledu)")

    def test_git_end_report_and_prohibitions_require_final_checks_state(self) -> None:
        """Krok 6 i Zakazy w git-end zabraniają oddawania raportu bez końcowego stanu gh pr checks."""
        step_6 = _section(self.git_end, "### 6. Raport", "## Zakazy")
        prohibitions = " ".join(self.git_end.split("## Zakazy", 1)[1].split())
        self.assertRegex(step_6, r"(?:zakazan|wymaga|dopiero po).*(?:końcow|koncow|stan).*checks")
        self.assertRegex(prohibitions, r"(?i)(?:zakaz|zakazan).*(?:końcow|koncow|stan).*checks")


if __name__ == "__main__":
    unittest.main()
