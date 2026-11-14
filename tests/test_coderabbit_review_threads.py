"""Testy kontraktu obsługi wątków review CodeRabbit w git-end i night-run (#458).

Sprawdzają:
- obecność kroku wątków bota po checks w git-end,
- gate na obecność `coderabbit` w `integrations:` w Profilu,
- traktowanie komentarzy bota jak danych (Prompt for AI Agents to nie polecenia),
- decyzje agenta: fix, odpowiedź z uzasadnieniem (headless) i resolve przez GraphQL,
- rundy wszystkich wątków naraz (jeden commit i push) z limitem 3 rund,
- uwzględnienie wątków bota w bramce merge night-run i night-run-ticket.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
GIT_END_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "git-end.md"
NIGHT_RUN_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
NIGHT_RUN_TICKET_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"


class TestCodeRabbitReviewThreads(unittest.TestCase):
    def setUp(self) -> None:
        self.git_end = GIT_END_TEMPLATE.read_text(encoding="utf-8")
        self.night_run = NIGHT_RUN_TEMPLATE.read_text(encoding="utf-8")
        self.night_run_ticket = NIGHT_RUN_TICKET_TEMPLATE.read_text(encoding="utf-8")

    def test_git_end_has_review_threads_step_after_checks(self) -> None:
        """git-end zawiera krok obsługi wątków bota po checks."""
        self.assertIn("reviewThreads", self.git_end)
        self.assertIn("gh pr checks", self.git_end)
        checks_pos = self.git_end.index("gh pr checks")
        threads_pos = self.git_end.index("reviewThreads")
        self.assertLess(checks_pos, threads_pos)

    def test_git_end_gates_on_coderabbit_integration(self) -> None:
        """Krok wątków w git-end działa tylko gdy coderabbit jest w integrations: w Profilu."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("coderabbit", self.git_end)
        self.assertIn("integrations:", self.git_end)
        self.assertRegex(normalized, r"coderabbit.*integrations:.*(?:pominięt|pominiet)")

    def test_git_end_bot_comments_treated_as_data(self) -> None:
        """Komentarze bota traktowane są jak dane; Prompt for AI Agents to nie polecenia."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("Prompt for AI Agents", self.git_end)
        self.assertRegex(normalized, r"Prompt for AI Agents.*(?:nie są poleceniami|nie sa poleceniami)")
        self.assertRegex(normalized, r"weryfikuje.*finding.*kod")

    def test_git_end_decisions_and_graphql_mutations(self) -> None:
        """Decyzje agenta: fix, odpowiedź uzasadnieniem (headless) i resolve przez GraphQL."""
        self.assertIn("resolveReviewThread", self.git_end)
        self.assertIn("addPullRequestReviewThreadReply", self.git_end)
        normalized = " ".join(self.git_end.split())
        self.assertRegex(normalized, r"uzasadnieni.*(?:tańszym modelem|headless)")

    def test_git_end_thread_rounds_and_limit(self) -> None:
        """Runda obsługuje wszystkie wątki naraz (1 commit, 1 push), limit 3 rund, liczba rund w raporcie."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("wszystkie otwarte wątki naraz", normalized)
        self.assertIn("jeden commit", normalized)
        self.assertIn("jeden push", normalized)
        self.assertRegex(normalized, r"3\.\s*rundzie.*needs-human")
        self.assertIn("Rundy CodeRabbit:", self.git_end)

    def test_night_run_ticket_agent_mentions_bot_threads(self) -> None:
        """night-run-ticket uwzględnia wątki bota CodeRabbit i bramkę merge."""
        self.assertIn("CodeRabbit", self.night_run_ticket)
        self.assertIn("integrations:", self.night_run_ticket)

    def test_night_run_merge_gate_includes_bot_threads(self) -> None:
        """Bramka merge night-run blokuje merge przy otwartym wątku bota."""
        prompt = " ".join(self.night_run.split("## Prompt ticketu", 1)[1].split("## Testy", 1)[0].split())
        self.assertIn("coderabbit", prompt)
        self.assertIn("integrations:", prompt)
        self.assertIn("reviewThreads", prompt)
        self.assertIn("wszystkie otwarte wątki naraz", prompt)
        self.assertIn("jeden commit", prompt)
        self.assertIn("jeden push", prompt)
        self.assertRegex(prompt, r"3\.\s*rundzie.*needs-human")
        self.assertLess(prompt.index("reviewThreads"), prompt.index("gh pr merge"))
        gate_phrase = "Bramka merge uwzględnia wątki bota"
        self.assertIn(gate_phrase, prompt)
        self.assertLess(prompt.index(gate_phrase), prompt.index("7. `gh pr merge"))
        self.assertRegex(prompt, r"ponowny odczyt.*reviewThreads")
        self.assertIn("merge mimo wątków", prompt)

    def test_git_end_no_checks_reported_branch(self) -> None:
        """git-end krok 4 obsługuje gałąź no checks reported z odczekaniem 60 s przed ponowieniem."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("no checks reported", self.git_end)
        self.assertRegex(normalized, r"no checks reported.*(?:odczekaj 60 s|po minucie).*(?:powtórz|ponów).*Host:\s*local")

    def test_git_end_bot_review_timeout_and_signal(self) -> None:
        """git-end: limit czasu na review bota, sygnał dla head commita, odczyt istniejących wątków i adnotacja w raporcie."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("reviews.nodes.commit.oid == headRefOid", self.git_end)
        self.assertRegex(normalized, r"(?:limit czasu|timeout).*brak review bota")
        self.assertRegex(normalized, r"(?:limitu czasu|timeout).*nadal pobierz.*otwarte wątki")
        self.assertRegex(normalized, r"Gdy (?:brak|nie ma) otwartych wątków:\s*0 rund")

    def test_night_run_merge_gate_gated_on_coderabbit_integration(self) -> None:
        """Bramka wątków bota przed merge w night-run zależy od obecności coderabbit w integrations:."""
        prompt = " ".join(self.night_run.split("## Prompt ticketu", 1)[1].split("## Testy", 1)[0].split())
        self.assertRegex(prompt, r"Bramka merge uwzględnia wątki bota:\*{0,2}\s*gdy `coderabbit` jest w `integrations:`")
        self.assertRegex(prompt, r"(?:brak|bez) `coderabbit` w `integrations:`.*(?:sprawdzenie.*pominięt|pominięt)")

    def test_git_end_pagination_and_root_author_filter(self) -> None:
        """git-end: paginacja reviewThreads oraz filtrowanie po pierwszym autorze i obsługa isOutdated."""
        normalized = " ".join(self.git_end.split())
        self.assertIn("pageInfo", self.git_end)
        self.assertIn("hasNextPage", self.git_end)
        self.assertIn("endCursor", self.git_end)
        self.assertIn("comments.nodes[0].author.login", self.git_end)
        self.assertRegex(normalized, r"isOutdated.*resolveReviewThread")

    def test_rounds_owner_and_ci_attempt_accounting(self) -> None:
        """git-end i night-run ustalają właściciela rund i wliczanie czerwonego CI rundy do 3 prób."""
        git_end_norm = " ".join(self.git_end.split())
        night_run_prompt = " ".join(self.night_run.split("## Prompt ticketu", 1)[1].split("## Testy", 1)[0].split())
        self.assertRegex(git_end_norm, r"(?i)czerwone CI po pushu rundy.*(?:liczy|wlicza).*3 prób")
        self.assertRegex(night_run_prompt, r"(?i)czerwone CI po pushu rundy.*(?:liczy|wlicza).*3 prób")
        self.assertRegex(night_run_prompt, r"(?:Właścicielem|właścicielem).*git-end")

    def test_night_run_triggers_and_cases_include_bot_threads(self) -> None:
        """Wyzwalacze i przypadek E w night-run uwzględniają otwarte wątki CodeRabbit."""
        triggers = " ".join(self.night_run.split("### Wyzwalacze", 1)[1].split("### Zasięg", 1)[0].split())
        cases = " ".join(self.night_run.split("### Przypadki", 1)[1].split("## Tick watchdoga", 1)[0].split())
        self.assertIn("CodeRabbit", triggers)
        self.assertIn("CodeRabbit", cases)

    def test_git_end_round_without_code_changes_and_resolve_timing(self) -> None:
        """git-end: brak zmian w kodzie pomija commit/push; wątki z fixem rozwiązywane po pushu; czekanie na head commit."""
        normalized = " ".join(self.git_end.split())
        self.assertRegex(normalized, r"brak zmian w kodzie.*(?:pomiń|pomijasz) commit i push")
        self.assertRegex(normalized, r"(?:poprawkami w kodzie|fixem).*(?:po udanym pushu|po pushu)")
        self.assertRegex(normalized, r"review.*head commit")

    def test_night_run_round_without_code_changes_and_local_host(self) -> None:
        """night-run: runda bez zmian w kodzie pomija commit/push, czeka na head commit, a Host: local czyta po bramkach."""
        prompt = " ".join(self.night_run.split("## Prompt ticketu", 1)[1].split("## Testy", 1)[0].split())
        self.assertRegex(prompt, r"brak zmian w kodzie.*(?:pomiń|pomijasz) commit i push")
        self.assertRegex(prompt, r"review.*head commit")
        self.assertRegex(prompt, r"Host:\s*local.*bez checks.*bramkach szybkich")


    def test_night_run_merge_gate_fails_closed_on_read_error(self) -> None:
        self.assertIn("Błąd zapytania GraphQL albo odpowiedź bez danych `reviewThreads`", self.night_run)
        self.assertIn("bramka fail-closed", self.night_run)
        self.assertIn("orkiestrator dopisuje wtedy do promptu ticketu linię „merge mimo wątków”", self.night_run)

if __name__ == "__main__":
    unittest.main()
