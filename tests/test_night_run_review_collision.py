"""Testy kontraktu rozróżnienia /code-review i wbudowanego /review w procedurze night-run (#465).

Weryfikuje zakres z issue #465:
- /code-review = skill Matta (gdy istnieje), dostaje numer issue (oś Spec);
- /review [effort] [--fix] = wbudowane review Claude Code; przed PR dostaje <BASE>...HEAD, po /git-end numer PR;
- /code-review z --fix albo --comment przy osobistym skillu code-review -> orkiestrator tłumaczy na /review ... (decyzja odwracalna) i zapisuje to w raporcie;
- po --fix: /git-commit i ponowne CI;
- /review poza Claude Code (brak wbudowanego) -> istniejąca reguła "nieznany skill review" (needs-human na starcie);
- przykład w sekcji Argumenty: /review --fix zamiast /code-review --fix;
- kopie szablonów u klientów zachowują ten sam kontrakt.
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


class TestNightRunReviewCollision(unittest.TestCase):
    """Weryfikacja kontraktu rozróżnienia /code-review i /review w night-run (#465)."""

    def setUp(self) -> None:
        self.text = TEMPLATE_NIGHT_RUN.read_text(encoding="utf-8")

    def test_args_example_uses_review_fix_instead_of_code_review_fix(self) -> None:
        """Przykład w sekcji Argumenty zawiera `/review --fix`, a nie `/code-review --fix` (#465)."""
        args_sec = self.text.split("## Argumenty", 1)[1].split("## Start nocy", 1)[0]
        self.assertNotIn("`/code-review --fix`", args_sec)
        self.assertIn("`/review --fix`", args_sec)

    def test_code_review_gets_issue_number_for_spec(self) -> None:
        """/code-review (skill Matta) dostaje numer issue N, bo jego oś Spec czyta issue (#465)."""
        self.assertIn("`/code-review <N>`", self.text)
        self.assertIn("oś Spec czyta issue", self.text)

    def test_bundled_review_target_before_and_after_pr(self) -> None:
        """Wbudowane review Claude Code dostaje <BASE>...HEAD przed PR, a po /git-end numer PR (#465)."""
        self.assertIn("`/review [effort] [--fix]`", self.text)
        self.assertIn("<BASE>...HEAD", self.text)
        self.assertIn("po `/git-end` numer PR", self.text)

    def test_orchestrator_translates_code_review_flags_and_records_in_report(self) -> None:
        """/code-review z --fix albo --comment przy osobistym skillu jest tłumaczony na /review i notowany w raporcie (#465)."""
        self.assertIn("--fix", self.text)
        self.assertIn("--comment", self.text)
        self.assertIn("osobistym skillu `code-review`", self.text)
        self.assertIn("tłumaczy na `/review", self.text)
        self.assertIn("zapisuje to w raporcie", self.text)

    def test_commit_and_ci_after_fix(self) -> None:
        """Po --fix następuje /git-commit poprawek i ponowne CI (#465)."""
        self.assertIn("po `--fix`", self.text)
        self.assertIn("`/git-commit`", self.text)
        self.assertIn("ponowne CI", self.text)

    def test_review_outside_claude_code_triggers_unknown_skill(self) -> None:
        """/review poza Claude Code (brak wbudowanego) traktowane jak nieznany skill review (#465)."""
        self.assertIn("`/review` poza Claude Code", self.text)
        self.assertIn("nieznany skill review", self.text)

    def test_all_client_copies_contain_review_contract(self) -> None:
        """Wszystkie śledzone kopie szablonu night-run u klientów zachowują kontrakt #465."""
        for rel in NIGHT_RUN_COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("`/code-review --fix`", copy)
                self.assertIn("`/review --fix`", copy)
                self.assertIn("`/code-review <N>`", copy)
                self.assertIn("`/review [effort] [--fix]`", copy)
                self.assertIn("<BASE>...HEAD", copy)
                self.assertIn("po `/git-end` numer PR", copy)
                self.assertIn("tłumaczy na `/review", copy)
                self.assertIn("ponowne CI", copy)


if __name__ == "__main__":
    unittest.main()
