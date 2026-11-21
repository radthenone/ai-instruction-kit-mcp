"""Bramka merge night-run przy finding blokującym (#412).

Seamy ustalone w grillu: tekst szablonu `templates/shared/agents/night-run.md`
(warunek merge, ponowne sprawdzenie Spec, stan po blokadzie, język commitów,
brak odczytu SKILL.md ukrytego skilla, pola NIGHT-RUN REPORT). Parytet kopii
pilnuje `test_generated_artifacts.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
TICKET_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"

REQUIRED_REPORT_FIELDS = (
    "Baza:",
    "Host:",
    "Bramki szybkie:",
    "Model ticketu:",
    "Wykonawca:",
    "Modele kroków:",
    "Fallback modelu:",
    "Pauzy limitu:",
    "Odnowienia watchdoga:",
    "Wybudzenia orkiestratora:",
    "Wznowienia per ticket:",
    "Orkiestrator (tylko Claude Code):",
    "Retro:",
    "Założenia:",
    "Pomiar per agent:",
)


def _section(text: str, start: str, end: str) -> str:
    """Zwraca fragment szablonu między znacznikami, z normalizacją białych znaków."""
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


class TestNightRunMergeGate(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")
        self.ticket = TICKET_TEMPLATE.read_text(encoding="utf-8")
        self.chain = _section(self.text, "## Łańcuch na ticket", "## Zlecenie ticketu")
        self.prompt = " ".join(self.ticket.split("## Prompt ticketu", 1)[1].split())
        self.case_rules = _section(self.text, "### Przypadki", "## Tick watchdoga")
        self.report = self.text.split("## NIGHT-RUN REPORT", 1)[1]

    def test_merge_gate_defined_before_merge_step(self) -> None:
        self.assertIn("finding blokujący", self.prompt)
        self.assertIn("zielone CI", self.prompt)
        self.assertIn("nie znosi", self.prompt)
        self.assertLess(self.prompt.index("finding blokujący"), self.prompt.index("gh pr merge"))

    def test_spec_rows_come_from_every_acceptance_criterion(self) -> None:
        self.assertIn("każde kryterium z sekcji `Kryterium ukończenia`", self.chain)
        self.assertIn("wiersz Spec", self.chain)
        self.assertIn("niespełnione = High", self.chain)

    def test_recheck_after_fixes_by_fresh_subagent(self) -> None:
        self.assertIn("świeży subagent", self.prompt)
        self.assertIn("tylko wiersze Spec", self.prompt)

    def test_blocked_ticket_stays_open_with_needs_human(self) -> None:
        self.assertIn("finding blokujący", self.case_rules)
        self.assertIn("PR zostaje otwarty", self.case_rules)
        self.assertIn("ready-for-agent` → `ready-for-human`", self.case_rules)
        self.assertIn("needs-human:", self.case_rules)
        self.assertIn("link do PR", self.case_rules)

    def test_missing_acceptance_criteria_is_needs_human_before_code(self) -> None:
        self.assertRegex(self.prompt, r"bez sekcji `Kryterium ukończenia` ani `Kryteria akceptacji`[^.]*needs-human[^.]*bez kodu")

    def test_commit_language_rule_in_ticket_prompt(self) -> None:
        self.assertIn("prefiks Conventional", self.prompt)
        self.assertIn("opis i body", self.prompt)
        self.assertIn("get_language", self.prompt)

    def test_hidden_skill_is_never_read_from_skill_md(self) -> None:
        self.assertNotIn("przez odczyt jego `SKILL.md`", self.text)
        self.assertIn("nie czytasz jego `SKILL.md`", self.prompt)
        self.assertEqual(self.prompt.count("`SKILL.md`"), self.prompt.count("nie czytasz jego `SKILL.md`"))
        self.assertIn("disable-model-invocation", self.prompt)
        self.assertRegex(self.prompt, r"disable-model-invocation[^.]*needs-human")

    def test_report_lists_every_required_field(self) -> None:
        for field in REQUIRED_REPORT_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, self.report)

    def test_criteria_heading_without_diacritics_and_manual_lines_do_not_block(self) -> None:
        self.assertIn("Kryterium ukonczenia", self.prompt)
        self.assertIn("Recznie:", self.prompt)
        self.assertIn("`niesprawdzalne` nie blokuje", self.prompt)
        self.assertIn("niespełnione = High", self.prompt)
        self.assertIn("merge mimo spec", self.prompt)

    def test_report_contract_rule_for_missing_fields(self) -> None:
        self.assertIn("brak danych:", self.report)
        self.assertIn("n/d —", self.report)

    def test_repair_rounds_share_ceiling_of_three(self) -> None:
        self.assertIn("sufit 3 rund naprawczych", self.prompt)
        self.assertIn("prób CI i reviewów wysyłanych przez orkiestrator", self.prompt)
        self.assertNotIn("łącznie dla CI i CodeRabbit", self.prompt)
        self.assertNotIn("limitu 3 prób CI", self.prompt)
        self.assertIn("CodeRabbit ma osobny licznik do 6 rund", self.prompt)
        self.assertIn("rundy CodeRabbit nie wchodzą do sufitu 3", self.prompt)

    def test_coderabbit_ceiling_six_rounds_triggers_case_e(self) -> None:
        """Otwarte wątki CodeRabbit po 6 rundach wyzwalają przypadek E needs-human (#542)."""
        self.assertIn("otwarte wątki CodeRabbit po 6. rundzie", self.case_rules)
        self.assertNotIn("wspólny sufit 3 rund naprawczych CI i CodeRabbit", self.text)
        self.assertIn("wspólny sufit 3 rund naprawczych dla CI i reviewów orkiestratora", self.text)

    def test_circuit_breaker_conditions_stop_repair_loop(self) -> None:
        problems = _section(self.text, "## Gdy ticket napotka problem", "## Tick watchdoga")
        for text in (self.prompt, problems):
            self.assertIn("circuit breaker", text)
            self.assertIn("identyczny błąd", text)
            self.assertIn("flip-flop", text)
            self.assertIn("eksplozja diffa", text)
        self.assertIn("więcej niż 10 plików przy zadaniu punktowym", self.prompt)
        self.assertIn("przed 3. rundą", self.prompt)

    def test_identical_error_compares_error_content_not_test_name(self) -> None:
        self.assertIn("ta sama treść i rodzaj błędu", self.prompt)
        self.assertIn("nie sama nazwa testu", self.prompt)
        self.assertIn("różne błędy tego samego testu nie są identyczne", self.prompt)
        self.assertNotIn("ten sam test albo traceback", self.prompt)

    def test_handback_after_ceiling_or_breaker_carries_card_data(self) -> None:
        self.assertRegex(
            self.prompt,
            r"wspólny sufit 3 albo zadziałał circuit breaker[^.]*hand-back[^.]*dokładny błąd albo test"
            r"[^.]*hipotezę przyczyny[^.]*zmiany i commity na branchu",
        )
        self.assertIn("hand-back z Q1/Q2", self.prompt)

    def test_stan_schema_carries_coderabbit_counter(self) -> None:
        """Licznik `coderabbit-rundy` jest w schemacie `## Stan`; git-end zapisuje go przed pushem rundy (#542)."""
        text = " ".join(self.text.split())
        self.assertIn(
            "`coderabbit-rundy: #<N> <R>` (licznik rund CodeRabbit ticketu #N; zapisuje go git-end przed pushem każdej rundy, R+1; linia innego ticketu nie dotyczy bieżącego ticketu, wtedy R = 0; przetrwa wznowienie i Clean Slate; nadpisując `## Stan`, zachowaj tę linię)",
            text,
        )

    def test_ticket_hands_coderabbit_counter_to_git_end(self) -> None:
        """Subagent ticketu przyjmuje licznik z parametrów, przekazuje go do /git-end i zwraca w hand-backu (#542)."""
        self.assertIn("linia `coderabbit-rundy: #<N> <R>` w parametrach zlecenia", self.prompt)
        self.assertIn("w prompcie do `/git-end` przekazujesz numer ticketu, R, ścieżkę `<CTX>`", self.prompt)
        self.assertIn("zwracasz w hand-backu jako `rundy CodeRabbit`", self.prompt)

    def test_zlecenie_ticketu_carries_coderabbit_counter(self) -> None:
        """Zlecenie ticketu niesie licznik CodeRabbit, więc wznowienie go nie gubi (#542)."""
        text = " ".join(self.text.split())
        self.assertIn("Licznik CodeRabbit: coderabbit-rundy: #<N> <R> | brak", text)

    def test_fallback_carries_coderabbit_counter(self) -> None:
        """Fallback po porażce subagenta niesie licznik CodeRabbit z `## Stan` (#542)."""
        text = " ".join(self.text.split())
        self.assertIn("z linią `coderabbit-rundy: #<N> <R>` z `## Stan`", text)

    def test_escalation_card_sections(self) -> None:
        card = _section(self.text, "### Karta eskalacji", "## Tick watchdoga")
        for field in ("Co zaimplementowano:", "Na czym utknął:", "Hipoteza:", "Wątek T3:"):
            self.assertIn(field, card)
        self.assertRegex(card, r"(?:^| )PR: <[^>]*pull request[^>]*>")

    def test_queue_continues_after_needs_human(self) -> None:
        card = _section(self.text, "### Karta eskalacji", "## Tick watchdoga")
        self.assertIn("od razu bierze kolejne niezależne issue", card)
        self.assertIn("blokuje tylko relacja `blocked_by`", card)

    def test_escalation_after_ceiling_separates_shared_and_coderabbit_limits(self) -> None:
        """Wyczerpany wspólny sufit eskaluje CI i potwierdzone uwagi review; wątki CodeRabbit mają osobny limit (#542)."""
        self.assertIn("potwierdzona, nierozwiązana uwaga review orkiestratora", self.prompt)
        self.assertIn("przypadek E", self.prompt)
        self.assertIn("Wątki CodeRabbit nie są eskalowane po wyczerpaniu wspólnego sufitu", self.prompt)
        self.assertIn("czerwone CI po wyczerpaniu sufitu → needs-human, nawet bez otwartych wątków", self.prompt)
        self.assertNotIn("gdy wątki CodeRabbit nadal są otwarte", self.prompt)
        self.assertNotIn("zero otwartych wątków przy zielonym CI kończy rundy bez eskalacji", self.prompt)

    def test_round_definition_is_unified_in_ticket_and_git_end(self) -> None:
        """Runda CodeRabbit to każdy cykl review z otwartymi wątkami, także bez pusha, w obu szablonach (#542)."""
        git_end = " ".join((KIT_ROOT / "templates" / "shared" / "agents" / "git-end.md").read_text(encoding="utf-8").split())
        phrase = "runda = każdy cykl review CodeRabbit z otwartymi wątkami, także bez pusha"
        self.assertIn(phrase, self.prompt)
        self.assertIn(phrase, git_end)
        self.assertNotIn("runda = push z naprawą", self.prompt)

    def test_coderabbit_counter_lives_in_stan_and_survives_resume(self) -> None:
        """Licznik rund CodeRabbit jest w `## Stan` CTX i przechodzi do /git-end (#542)."""
        git_end = " ".join((KIT_ROOT / "templates" / "shared" / "agents" / "git-end.md").read_text(encoding="utf-8").split())
        self.assertIn("`coderabbit-rundy: #<N> <R>` w `## Stan` CTX nocy", git_end)
        self.assertIn("przetrwa wznowienie", git_end)
        self.assertIn("prompt do `/git-end` niesie numer ticketu, R i `<CTX>`", git_end)
        self.assertIn("tylko w procedurze night-run", git_end)

    def test_coderabbit_counter_written_before_push(self) -> None:
        """Licznik `coderabbit-rundy` zapisuje się przed pushem rundy, żeby przerwana runda go nie zgubiła (#542)."""
        git_end = " ".join((KIT_ROOT / "templates" / "shared" / "agents" / "git-end.md").read_text(encoding="utf-8").split())
        rounds = git_end[git_end.index("**Rundy wątków (maks. 6 rund):**") : git_end.index("### 5. Powrót na branch")]
        self.assertIn("Przed każdą rundą", rounds)
        self.assertIn("odczytaj `coderabbit-rundy: #<N> <R>` z `## Stan`", rounds)
        write = rounds.index("zapisz `coderabbit-rundy: #<N> <R+1>`")
        self.assertLess(write, rounds.index("jeden push"))
        self.assertLess(write, rounds.index("resolveReviewThread"))

    def test_scope_counts_only_explicit_blocked_by(self) -> None:
        scope = _section(self.text, "### Zasięg — zanim cokolwiek zrobisz", "### Przypadki")
        self.assertIn("wyłącznie jawnie", scope)
        self.assertIn("`blocked_by`", scope)
        self.assertNotIn("niejawnie", scope)

    def test_scope_includes_transitive_blocked_by(self) -> None:
        scope = _section(self.text, "### Zasięg — zanim cokolwiek zrobisz", "### Przypadki")
        self.assertIn("przechodnio", scope)
        self.assertIn("tickety B i C są w zasięgu", scope)


if __name__ == "__main__":
    unittest.main()
