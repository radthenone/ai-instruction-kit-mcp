"""Testy kontraktu rozróżnienia /code-review i wbudowanego /review w procedurze night-run (#465).

Weryfikuje zakres z issue #465 oraz poprawki po review:
- /code-review = osobisty skill (gdy istnieje), dostaje numer issue (oś Spec);
- /review [effort] [--fix] = wbudowane review Claude Code; przed PR dostaje <BASE>...HEAD (bez martwej gałęzi po /git-end);
- /code-review z --fix albo --comment: najpierw sprawdzenie klienta (Claude Code), kryterium osobistego skilla
  (brak deklaracji flag --fix/--comment), tłumaczenie na /review z odnotowaniem w raporcie;
- po --fix: /git-commit i ponowne CI;
- /review poza Claude Code (brak wbudowanego) -> traktowane jak nieznany skill review (needs-human na starcie);
- krok 2 odsyła do sekcji Argumenty oraz normalizuje wynik wbudowanego /review do tabeli Severity | Location | Finding | Fix;
- przykład w sekcji Argumenty: /review --fix zamiast /code-review --fix;
- --comment tylko przy istniejącym PR (po /git-end), przed /git-end wynik zostaje w raporcie nocy;
- skille review uruchamiane w katalogu brancha ticketu, z kontrolą `git branch --show-current` i rozjazdem jako needs-human;
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

    @property
    def review_args_section(self) -> str:
        args_sec = self.text.split("## Argumenty", 1)[1].split("## Start nocy", 1)[0]
        return args_sec.split("- **Skille review z argumentów**", 1)[1]

    @property
    def step_two_section(self) -> str:
        chain_sec = self.text.split("## Łańcuch na ticket", 1)[1].split("## Prompt ticketu", 1)[0]
        return chain_sec.split("2. **Review.**", 1)[1].split("3. **Wznów subagenta", 1)[0]

    def test_args_example_uses_review_fix_instead_of_code_review_fix(self) -> None:
        """Przykład w sekcji Argumenty zawiera `/review --fix`, a nie `/code-review --fix` (#465)."""
        self.assertNotIn("`/code-review --fix`", self.review_args_section)
        self.assertIn("`/review --fix`", self.review_args_section)

    def test_code_review_gets_issue_number_for_spec(self) -> None:
        """/code-review dostaje numer issue N, bo jego oś Spec czyta issue (#465)."""
        self.assertIn("`/code-review <N>`", self.review_args_section)
        self.assertIn("oś Spec czyta issue", self.review_args_section)

    def test_bundled_review_target_before_pr_without_dead_branch(self) -> None:
        """Wbudowane review Claude Code dostaje <BASE>...HEAD przed PR, bez martwego wariantu po /git-end (#465)."""
        self.assertIn("`/review [effort] [--fix]` = wbudowane review Claude Code", self.review_args_section)
        self.assertIn("dostaje zakres `<BASE>...HEAD`", self.review_args_section)
        self.assertNotIn("po `/git-end` numer PR", self.review_args_section)

    def test_orchestrator_translates_code_review_flags_and_records_in_report(self) -> None:
        """Tłumaczenie flag /code-review na /review najpierw sprawdza klienta, wymaga osobistego skilla i notuje w raporcie (#465)."""
        section = self.review_args_section
        self.assertIn("najpierw sprawdza, czy klient ma wbudowane `/review` (Claude Code)", section)
        self.assertIn("kryterium wykrycia osobistego skilla `code-review`: skill nie deklaruje flag `--fix`/`--comment`", section)
        self.assertIn("tłumaczy na `/review` z tymi flagami (decyzja odwracalna)", section)
        self.assertIn("zapisuje to w raporcie (w linii Założenia)", section)
        self.assertNotIn("skill Matta, który tych flag nie obsługuje", section)

    def test_commit_and_ci_after_fix(self) -> None:
        """Po --fix następuje zebranie poprawek przez /git-commit i ponowne CI (#465)."""
        self.assertIn(
            "po `--fix`: zebranie poprawek przez `/git-commit` w osobnym commicie na branchu ticketu i ponowne CI",
            self.review_args_section,
        )

    def test_review_outside_claude_code_triggers_unknown_skill(self) -> None:
        """/review poza Claude Code traktowane jak nieznany skill review (needs-human na starcie) (#465)."""
        self.assertIn(
            "`/review` poza Claude Code (brak wbudowanego review) → traktowane jak nieznany skill review",
            self.review_args_section,
        )
        self.assertIn("needs-human na starcie nocy", self.review_args_section)

    def test_step_two_refers_to_args_and_normalizes_review_output(self) -> None:
        """Krok 2 odsyła do sekcji Argumenty i normalizuje wynik wbudowanego /review do tabeli (#465)."""
        step_two = self.step_two_section
        self.assertIn("wg reguły z sekcji Argumenty", step_two)
        self.assertIn(
            "dla wbudowanego `/review`: orkiestrator przepisuje findingi do tabeli `Severity | Location | Finding | Fix` — nagłówek bez zmian — i oznacza każdy wiersz jako potwierdzony albo niepewny",
            step_two,
        )
        self.assertNotIn("po `/git-end` numer PR", step_two)

    def test_comment_flag_only_with_existing_pr(self) -> None:
        """`--comment` działa tylko przy istniejącym PR; przed /git-end wynik zostaje w raporcie nocy (#465)."""
        section = self.review_args_section
        self.assertIn("`--comment` działa tylko wtedy, gdy PR już istnieje (po `/git-end`)", section)
        self.assertIn("nie przekazujesz `--comment`", section)
        self.assertIn("wynik zostaje w raporcie nocy", section)

    def test_review_skills_run_in_ticket_branch_directory(self) -> None:
        """Skille review idą w katalogu brancha ticketu, z kontrolą `git branch --show-current` (#465)."""
        step_two = self.step_two_section
        self.assertIn("w katalogu brancha ticketu", step_two)
        self.assertIn("`git -C <katalog brancha>`", step_two)
        self.assertIn("git -C <katalog brancha> branch --show-current", step_two)
        self.assertIn("nie odpalasz review na złym diffie", step_two)
        self.assertIn("katalog (worktree ticketu albo katalog główny)", self.text)

    def test_all_client_copies_contain_review_contract(self) -> None:
        """Wszystkie śledzone kopie szablonu night-run u klientów zachowują kontrakt #465."""
        for rel in NIGHT_RUN_COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8")
                args_sec = copy.split("## Argumenty", 1)[1].split("## Start nocy", 1)[0]
                review_args = args_sec.split("- **Skille review z argumentów**", 1)[1]
                chain_sec = copy.split("## Łańcuch na ticket", 1)[1].split("## Prompt ticketu", 1)[0]
                step_two = chain_sec.split("2. **Review.**", 1)[1].split("3. **Wznów subagenta", 1)[0]

                self.assertNotIn("`/code-review --fix`", review_args)
                self.assertIn("`/review --fix`", review_args)
                self.assertIn("`/code-review <N>`", review_args)
                self.assertIn("`/review [effort] [--fix]`", review_args)
                self.assertIn("<BASE>...HEAD", review_args)
                self.assertNotIn("po `/git-end` numer PR", copy)
                self.assertIn("najpierw sprawdza, czy klient ma wbudowane `/review` (Claude Code)", review_args)
                self.assertIn("kryterium wykrycia osobistego skilla `code-review`: skill nie deklaruje flag `--fix`/`--comment`", review_args)
                self.assertNotIn("skill Matta, który tych flag nie obsługuje", review_args)
                self.assertIn("tłumaczy na `/review` z tymi flagami", review_args)
                self.assertIn(
                    "po `--fix`: zebranie poprawek przez `/git-commit` w osobnym commicie na branchu ticketu i ponowne CI",
                    review_args,
                )
                self.assertIn(
                    "`/review` poza Claude Code (brak wbudowanego review) → traktowane jak nieznany skill review",
                    review_args,
                )
                self.assertIn("`--comment` działa tylko wtedy, gdy PR już istnieje (po `/git-end`)", review_args)
                self.assertIn("wynik zostaje w raporcie nocy", review_args)
                self.assertIn("wg reguły z sekcji Argumenty", step_two)
                self.assertIn("w katalogu brancha ticketu", step_two)
                self.assertIn("git -C <katalog brancha> branch --show-current", step_two)
                self.assertIn("katalog (worktree ticketu albo katalog główny)", copy)
                self.assertIn(
                    "dla wbudowanego `/review`: orkiestrator przepisuje findingi do tabeli `Severity | Location | Finding | Fix`",
                    step_two,
                )


if __name__ == "__main__":
    unittest.main()
