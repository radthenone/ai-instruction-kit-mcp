"""Testy kontraktu dobierania domyślnego review nocy po typach plików w diffie (#466).

Weryfikuje zakres z issue #466:
- szablon opisuje wyzwalacze po typach plików w domyślnym łańcuchu review:
  * zawsze /review-bugbot;
  * diff dotyka plików wykonywalnych (*.py, *.mjs, *.js, *.ts, *.sh) -> + jedno review, w kolejności:
    /review-security (auth, sekrety, guardy) > review stacku (Tier ≠ none) > /review-edge;
  * sam tekst (*.md, docs, szablony procedur) -> tylko bugbot;
  * maks. 2 review na ticket;
  * bez /code-review w domyślnym łańcuchu i bez --fix (Spec sprawdza bramka przed merge);
  * findingi -> wykonawca implementacji, poprawka razem z testem;
  * skille review z argumentów nadal zastępują domyślny łańcuch;
  * prompt subagenta review zawiera pełną kolejność i warunki wyboru drugiego review;
  * krok 6 w night-run-ticket kieruje potwierdzone findingi do wykonawcy implementacji z testem;
- kopie szablonów u klientów zachowują ten sam kontrakt.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_NIGHT_RUN = ROOT / "templates" / "shared" / "agents" / "night-run.md"
TEMPLATE_NIGHT_RUN_TICKET = ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"

NIGHT_RUN_COPIES = (
    ".claude/agents/night-run.md",
    ".claude/skills/kit-ai/skills/night-run/SKILL.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)

NIGHT_RUN_TICKET_COPIES = (
    ".claude/agents/night-run-ticket.md",
    ".claude/skills/kit-ai/skills/night-run-ticket/SKILL.md",
    ".codex/skills/night-run-ticket/SKILL.md",
    ".github/prompts/night-run-ticket.prompt.md",
    ".opencode/command/night-run-ticket.md",
)


class TestNightRunDefaultReview(unittest.TestCase):
    """Weryfikacja kontraktu domyślnego review night-run po typach plików (#466)."""

    def setUp(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from command_prefix import resolve

        self.text = resolve(TEMPLATE_NIGHT_RUN.read_text(encoding="utf-8"))
        self.ticket_text = resolve(TEMPLATE_NIGHT_RUN_TICKET.read_text(encoding="utf-8"))

    @property
    def step_two_section(self) -> str:
        chain_sec = self.text.split("## Łańcuch na ticket", 1)[1].split("## Zlecenie ticketu", 1)[0]
        return chain_sec.split("2. **Review.**", 1)[1].split("3. **Wznów subagenta", 1)[0]

    @property
    def step_three_section(self) -> str:
        chain_sec = self.text.split("## Łańcuch na ticket", 1)[1].split("## Zlecenie ticketu", 1)[0]
        return chain_sec.split("3. **Wznów subagenta", 1)[1].split("4. Sprawdź dowód", 1)[0]

    @property
    def review_args_section(self) -> str:
        args_sec = self.text.split("## Argumenty", 1)[1].split("## Start nocy", 1)[0]
        return args_sec.split("- **Skille review z argumentów**", 1)[1]

    def test_default_review_always_runs_bugbot(self) -> None:
        """Domyślny łańcuch review zawsze uruchamia /review-bugbot (#466)."""
        step_two = self.step_two_section
        self.assertIn("zawsze `/review-bugbot`", step_two)

    def test_default_review_file_type_triggers(self) -> None:
        """Diff z plikami wykonywalnymi dobiera drugie review, a sam tekst tylko bugbota (#466)."""
        step_two = self.step_two_section
        self.assertIn("diff dotyka plików wykonywalnych", step_two)
        self.assertIn("`*.py`", step_two)
        self.assertIn("`*.mjs`", step_two)
        self.assertIn("`*.js`", step_two)
        self.assertIn("`*.ts`", step_two)
        self.assertIn("`*.sh`", step_two)
        self.assertIn("sam tekst", step_two)
        self.assertIn("`*.md`", step_two)
        self.assertIn("szablony procedur", step_two)
        self.assertIn("tylko bugbot", step_two)

    def test_second_review_priority_order(self) -> None:
        """Kolejność drugiego review: /review-security > review stacku > /review-edge (#466)."""
        step_two = self.step_two_section
        self.assertIn(
            "`/review-security` (auth, sekrety, guardy) > review stacku (Tier ≠ `none`) > `/review-edge`",
            step_two,
        )

    def test_review_subagent_prompt_ordering_contract(self) -> None:
        """Prompt subagenta review zawiera pełną regułę kolejności review (#466)."""
        step_two = self.step_two_section
        self.assertIn(
            "Review w tej kolejności: `/review-bugbot`; gdy diff dotyka plików wykonywalnych (`*.py`, `*.mjs`, `*.js`, `*.ts`, `*.sh`), jedno dodatkowe review: `/review-security` > review stacku (Tier ≠ `none`) > `/review-edge`. Maks. 2 review; bez `/code-review` i `--fix`. Czytaj tylko diff",
            step_two,
        )

    def test_max_two_reviews_per_ticket(self) -> None:
        """Maksymalnie 2 review na ticket w domyślnym łańcuchu (#466)."""
        step_two = self.step_two_section
        self.assertIn("maks. 2 review na ticket", step_two)

    def test_default_review_excludes_code_review_and_fix(self) -> None:
        """Domyślny łańcuch review nie zawiera /code-review ani --fix (#466)."""
        step_two = self.step_two_section
        self.assertIn("bez `/code-review` w domyślnym łańcuchu", step_two)
        self.assertIn("Spec sprawdza bramka przed merge", step_two)
        self.assertIn("bez `--fix`", step_two)

    def test_findings_routed_to_implementation_executor_with_test(self) -> None:
        """Findingi z review trafiają do wykonawcy implementacji, poprawka razem z testem (#466)."""
        step_three = self.step_three_section
        self.assertIn("wykonawca implementacji", step_three)
        self.assertIn("poprawka razem z testem", step_three)

    def test_ticket_step_six_confirmed_findings_routing(self) -> None:
        """Krok 6 w night-run-ticket kieruje potwierdzone findingi do wykonawcy implementacji (#466)."""
        step_six = self.ticket_text.split("6. Poprawki z review", 1)[1].split("7. `gh pr merge", 1)[0]
        self.assertIn("Potwierdzone findingi poprawia wykonawca implementacji z kroków 2–3", step_six)
        self.assertIn("ścieżki 2–4: ten sam wykonawca i model, poprawka razem z testem", step_six)
        self.assertIn("Ścieżka 1: poprawiasz sam, razem z testem", step_six)
        self.assertIn(
            "Bez `--fix` zapisz poprawki przez `/git-commit` w osobnym commicie przed `/git-end`, bo `/git-end` przy niecommitowanych zmianach zatrzymuje się.",
            step_six,
        )
        self.assertIn("Potem `/git-end --stay`", step_six)

    def test_args_review_skills_override_default_chain(self) -> None:
        """Skille review z argumentów nadal zastępują domyślny łańcuch (#466)."""
        self.assertIn("zastępują domyślny łańcuch", self.review_args_section)

    def test_all_client_copies_contain_default_review_contract(self) -> None:
        """Wszystkie śledzone kopie szablonu night-run u klientów zachowują kontrakt #466."""
        for rel in NIGHT_RUN_COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8").replace("/kit-ai:", "/")
                args_sec = copy.split("## Argumenty", 1)[1].split("## Start nocy", 1)[0]
                review_args = args_sec.split("- **Skille review z argumentów**", 1)[1]
                chain_sec = copy.split("## Łańcuch na ticket", 1)[1].split("## Zlecenie ticketu", 1)[0]
                step_two = chain_sec.split("2. **Review.**", 1)[1].split("3. **Wznów subagenta", 1)[0]
                step_three = chain_sec.split("3. **Wznów subagenta", 1)[1].split("4. Sprawdź dowód", 1)[0]

                self.assertIn("zawsze `/review-bugbot`", step_two)
                self.assertIn("diff dotyka plików wykonywalnych", step_two)
                self.assertIn("`*.py`", step_two)
                self.assertIn("`*.mjs`", step_two)
                self.assertIn("`*.js`", step_two)
                self.assertIn("`*.ts`", step_two)
                self.assertIn("`*.sh`", step_two)
                self.assertIn("sam tekst", step_two)
                self.assertIn("`*.md`", step_two)
                self.assertIn("szablony procedur", step_two)
                self.assertIn("tylko bugbot", step_two)
                self.assertIn(
                    "`/review-security` (auth, sekrety, guardy) > review stacku (Tier ≠ `none`) > `/review-edge`",
                    step_two,
                )
                self.assertIn(
                    "Review w tej kolejności: `/review-bugbot`; gdy diff dotyka plików wykonywalnych (`*.py`, `*.mjs`, `*.js`, `*.ts`, `*.sh`), jedno dodatkowe review: `/review-security` > review stacku (Tier ≠ `none`) > `/review-edge`. Maks. 2 review; bez `/code-review` i `--fix`. Czytaj tylko diff",
                    step_two,
                )
                self.assertIn("maks. 2 review na ticket", step_two)
                self.assertIn("bez `/code-review` w domyślnym łańcuchu", step_two)
                self.assertIn("Spec sprawdza bramka przed merge", step_two)
                self.assertIn("bez `--fix`", step_two)
                self.assertIn("wykonawca implementacji", step_three)
                self.assertIn("poprawka razem z testem", step_three)
                self.assertIn("zastępują domyślny łańcuch", review_args)

    def test_all_ticket_client_copies_contain_findings_routing(self) -> None:
        """Wszystkie śledzone kopie szablonu night-run-ticket u klientów zawierają routing poprawek (#466)."""
        for rel in NIGHT_RUN_TICKET_COPIES:
            with self.subTest(copy=rel):
                copy = (ROOT / rel).read_text(encoding="utf-8").replace("/kit-ai:", "/")
                step_six = copy.split("6. Poprawki z review", 1)[1].split("7. `gh pr merge", 1)[0]
                self.assertIn("Potwierdzone findingi poprawia wykonawca implementacji z kroków 2–3", step_six)
                self.assertIn("ścieżki 2–4: ten sam wykonawca i model, poprawka razem z testem", step_six)
                self.assertIn("Ścieżka 1: poprawiasz sam, razem z testem", step_six)
                self.assertIn(
                    "Bez `--fix` zapisz poprawki przez `/git-commit` w osobnym commicie przed `/git-end`, bo `/git-end` przy niecommitowanych zmianach zatrzymuje się.",
                    step_six,
                )
                self.assertIn("Potem `/git-end --stay`", step_six)


if __name__ == "__main__":
    unittest.main()
