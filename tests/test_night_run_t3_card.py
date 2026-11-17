"""Testy kontraktu karty transportu T3 Code dla night-run (#474).

Kryteria ukończenia:
- Karta templates/shared/night-run/t3.md instalowana jako .ai/night-run-t3.md.
- Jedno zdanie bramki w templates/shared/agents/night-run.md: sesja ma delegate_task
  i plik karty istnieje -> karta zastępuje transport, nie kroki procedury.
- Treść karty w t3.md:
  * sesja ticketu: delegate_task z isolation: worktree, mode: async, clientRequestId
    złożonym z nazwy katalogu CTX i numeru ticketu; task wskazuje procedurę
    night-run-ticket, podaje parametry zlecenia i wprost zezwala na dalszą delegację;
  * wykonawca implementacji: delegate_task z sesji ticketu, isolation: shared, mode: async;
  * taskId zapisany w ## Stan; po przerwaniu sesji wznowienie przez task_status,
    a ponowienie z tym samym clientRequestId nie tworzy drugiego dziecka;
  * watchdog i cron pominięte;
  * po MERGED orkiestrator woła link_pull_request, node .ai/worktree.mjs remove <katalog>
    i git branch -d na branchu nadanym przez T3; odmowa -d -> wpis w raporcie, bez -D;
  * raport: czas z wątków, tokeny delegatów „n/d”, model „niepotwierdzony”,
    gdy executedModel jest null.
- Testy instalacji i usuwania przez bootstrap.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _shell import resolve_bash
from guides.bootstrap import run_bootstrap

KIT_ROOT = Path(__file__).resolve().parents[1]
CARD_TEMPLATE = KIT_ROOT / "templates" / "shared" / "night-run" / "t3.md"
AGENT_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
TICKET_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run-ticket.md"


class TestNightRunT3CardContract(unittest.TestCase):
    def setUp(self) -> None:
        self.agent_text = AGENT_TEMPLATE.read_text(encoding="utf-8")
        if CARD_TEMPLATE.is_file():
            self.card_text = CARD_TEMPLATE.read_text(encoding="utf-8")
        else:
            self.card_text = ""

    def test_card_template_file_exists(self) -> None:
        self.assertTrue(CARD_TEMPLATE.is_file(), f"Brak pliku {CARD_TEMPLATE}")
        self.assertGreater(len(self.card_text.strip()), 0)

    def test_gate_in_night_run_agent(self) -> None:
        """Jedno zdanie bramki w night-run.md."""
        self.assertIn("delegate_task", self.agent_text)
        self.assertIn(".ai/night-run-t3.md", self.agent_text)
        self.assertIn("karta zastępuje transport, nie kroki procedury", self.agent_text)

    def test_ticket_session_delegation_in_card(self) -> None:
        """Sesja ticketu: delegate_task, worktree, async, clientRequestId, task."""
        self.assertIn("delegate_task", self.card_text)
        self.assertIn("isolation: worktree", self.card_text)
        self.assertIn("mode: async", self.card_text)
        self.assertIn("clientRequestId", self.card_text)
        # clientRequestId złożony z nazwy katalogu CTX i numeru ticketu
        self.assertIn("CTX", self.card_text)
        self.assertIn("ticket", self.card_text)
        # task wskazuje procedurę night-run-ticket, parametry zlecenia, zezwala na dalszą delegację
        self.assertIn("night-run-ticket", self.card_text)
        self.assertIn("parametry zlecenia", self.card_text)
        self.assertTrue(
            "zezwala na dalszą delegację" in self.card_text
            or "zezwolenie na dalszą delegację" in self.card_text
        )

    def test_implementation_executor_delegation_in_card(self) -> None:
        """Wykonawca implementacji: delegate_task z sesji ticketu, isolation: shared, mode: async."""
        self.assertIn("isolation: shared", self.card_text)
        # wykonawca z sesji ticketu
        self.assertTrue(
            "sesji ticketu" in self.card_text
            or "sesja ticketu" in self.card_text
        )

    def test_state_and_resumption_in_card(self) -> None:
        """taskId w ## Stan; wznowienie przez task_status, ponowienie z tym samym clientRequestId."""
        self.assertIn("taskId", self.card_text)
        self.assertIn("## Stan", self.card_text)
        self.assertIn("task_status", self.card_text)
        self.assertTrue(
            "nie tworzy drugiego dziecka" in self.card_text
            or "nie tworzy nowego dziecka" in self.card_text
        )

    def test_watchdog_and_cron_skipped_in_card(self) -> None:
        """Watchdog i cron pominięte."""
        self.assertTrue(
            "watchdog i cron pominięte" in self.card_text.lower()
            or "watchdog i cron: pominięte" in self.card_text.lower()
            or "pominięcie watchdoga i crona" in self.card_text.lower()
        )

    def test_merged_cleanup_in_card(self) -> None:
        """Po MERGED: link_pull_request, worktree.mjs remove, git branch -d bez -D."""
        self.assertIn("link_pull_request", self.card_text)
        self.assertIn(".ai/worktree.mjs remove", self.card_text)
        self.assertIn("git branch -d", self.card_text)
        self.assertTrue(
            "odmowa -d" in self.card_text.lower()
            or "odmowa `-d`" in self.card_text.lower()
        )
        self.assertTrue(
            "bez -D" in self.card_text
            or "bez `-D`" in self.card_text
        )

    def test_branch_naming_contract_in_card(self) -> None:
        """#498: title zadania i branch w konwencji <typ>/<N>-<slug>, rename przy rozbieżności."""
        self.assertIn('title: "<typ>/<N>-<slug>"', self.card_text)
        self.assertIn("git branch --show-current", self.card_text)
        self.assertIn("git branch -m <typ>/<N>-<slug>", self.card_text)
        self.assertIn("przed pierwszym commitem i push", self.card_text)
        self.assertIn("git switch -c <typ>/<N>-<slug>", self.card_text)

    def test_branch_base_checked_before_rename(self) -> None:
        """PR #505: przed rename/ponownym użyciem brancha T3 sprawdzana jest baza; brak → needs-human."""
        ticket_text = TICKET_TEMPLATE.read_text(encoding="utf-8")
        for text in (self.card_text, ticket_text):
            self.assertIn("git fetch origin", text)
            self.assertIn("git merge-base --is-ancestor origin/<BASE> HEAD", text)
            self.assertIn("baza się nie zgadza → needs-human", text)

    def test_clean_worktree_fast_forwarded_before_base_check(self) -> None:
        """PR #505: czyste worktree za origin/<BASE> idzie fast-forward; rozbieżna historia → needs-human."""
        ticket_text = TICKET_TEMPLATE.read_text(encoding="utf-8")
        for text in (self.card_text, ticket_text):
            ff = text.index("git merge --ff-only origin/<BASE>")
            self.assertLess(text.index("git merge-base --is-ancestor HEAD origin/<BASE>"), ff)
            self.assertLess(text.index("git status --porcelain"), ff)
            self.assertLess(ff, text.index("git merge-base --is-ancestor origin/<BASE> HEAD"))
            self.assertIn("rozbieżna historia albo brudne worktree", text)

    def test_merged_cleanup_deletes_convention_branch(self) -> None:
        """#498: po MERGED orkiestrator usuwa lokalny branch <typ>/<N>-<slug>."""
        self.assertIn("git branch -d <typ>/<N>-<slug>", self.card_text)

    def test_ticket_agent_verifies_branch_in_t3(self) -> None:
        """#498: krok 1 night-run-ticket weryfikuje nazwę brancha w T3 Code."""
        ticket_text = TICKET_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("W T3 Code (worktree z `delegate_task`", ticket_text)
        self.assertIn("git branch -m <typ>/<N>-<slug>", ticket_text)
        self.assertIn("nigdy `-M`", ticket_text)

    def test_task_carries_exact_branch_name(self) -> None:
        """PR #505: task podaje nazwę brancha równą title; sesja jej nie wyprowadza."""
        self.assertIn("nazwa brancha `<typ>/<N>-<slug>` (ta sama wartość co `title`", self.card_text)
        ticket_text = TICKET_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("nazwę brancha z `task` bez zmian", ticket_text)

    def test_git_start_reuses_active_issue_branch(self) -> None:
        """PR #505: /git-start nie tworzy nowego brancha, gdy aktywny to już <typ>/<N>-… issue."""
        git_start = (KIT_ROOT / "templates" / "shared" / "agents" / "git-start.md").read_text(encoding="utf-8")
        self.assertIn("Aktywny branch issue", git_start)
        self.assertIn("bez `startedFrom`", git_start)
        self.assertIn("`/git-start` użyje aktywnego brancha", self.card_text)
        ticket_text = TICKET_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("przed `/git-start #<N>`", ticket_text)

    def test_pr_labels_and_clean_title_in_card(self) -> None:
        """#499: karta odnotowuje przekazanie etykiet issue do PR i tytuł bez (night-run)."""
        self.assertIn("--label", self.card_text)
        self.assertIn("etykiety procesowe", self.card_text)
        self.assertIn("wszystkie etykiety issue", self.card_text)
        self.assertNotIn("sekcji „Etykiety” w `git-end`", self.card_text)
        self.assertIn("bez prefiksu `(night-run)`", self.card_text)

    def test_model_target_matrix_in_card(self) -> None:
        """#500: sekcja 2 mapuje `<wykonawca> <model>` na obiekt target T3 Code."""
        section = self.card_text.split("## 2.", 1)[1].split("## 3.", 1)[0]
        self.assertIn("target", section)
        for key in ("providerInstanceId", "model", "options"):
            self.assertIn(key, section)
        for executor, provider in (("claude", "claudeAgent"), ("antigravity", "antigravity"), ("opencode", "opencode")):
            self.assertIn(f"| `{executor}` | `{provider}` |", section)
        self.assertIn("thought_level", section)
        self.assertIn("effort", section)
        self.assertIn("review", section)
        example = next(line for line in section.splitlines() if line.startswith("Przykład: `review:"))
        self.assertNotIn("options", example)

    def test_disabled_default_provider_instance_is_needs_human(self) -> None:
        """#500: wyłączona lub brakująca domyślna instancja → needs-human, bez zamiany na inną instancję."""
        section = self.card_text.split("## 2.", 1)[1].split("## 3.", 1)[0]
        self.assertIn("wyłączona albo jej nie ma → needs-human", section)
        self.assertIn("nie wybieraj innej instancji tego samego `driverKind`", section)
        self.assertNotIn("użyj jej i wpisz wybraną instancję do raportu", section)

    def test_reactive_pr_watch_in_card(self) -> None:
        """#500: nasłuch PR przez link/watch/unwatch_pull_request zamiast pętli gh pr checks --watch."""
        for tool in ("link_pull_request", "watch_pull_request", "unwatch_pull_request"):
            self.assertIn(tool, self.card_text)
        self.assertIn("zamiast pętli `gh pr checks --watch`", self.card_text)

    def test_coderabbit_graphql_threads_in_card(self) -> None:
        """#500: sekcja 5 ma zapytanie reviewThreads, mutację resolveReviewThread i treść review dla head."""
        section = self.card_text.split("## 5.", 1)[1].split("## 6.", 1)[0]
        self.assertIn("reviewThreads", section)
        self.assertIn("resolveReviewThread(input:{threadId:$id})", section)
        self.assertIn("CodeRabbit", section)
        # PR #507: treść review CodeRabbit dla bieżącego head commita (uwagi poza diffem)
        # PR #507 (CodeRabbit): wszystkie strony review, wybór ostatniego wpisu ze wszystkich stron
        self.assertIn("gh api --paginate --slurp repos/<owner>/<repo>/pulls/<N>/reviews", section)
        self.assertIn(
            'flatten | map(select(.user.login == "coderabbitai[bot]" and .commit_id == "<head>")) | last',
            section,
        )
        self.assertIn("Outside diff range", section)
        self.assertIn("skrócony podgląd", section)
        # PR #507 (CodeRabbit): błąd gh api albo pusty wynik to needs-human, null to oczekiwanie na review head
        self.assertIn("set -o pipefail", section)
        self.assertIn("błąd odczytu review", section)
        self.assertIn("`null`", section)
        self.assertIn("poczekaj na review bieżącego head", section)
        # PR #507 (CodeRabbit): odczyt wcześniejszych review bez commit_id oraz limit czasu null z git-end
        self.assertIn('map(select(.user.login == "coderabbitai[bot]"))', section)
        self.assertIn("limit czasu (maks. 10–15 min)", section)
        self.assertIn("git-end", section)

    def test_report_fields_in_card(self) -> None:
        """Raport: czas z wątków, tokeny delegatów n/d, model niepotwierdzony gdy executedModel jest null."""
        self.assertIn("czas z wątków", self.card_text)
        self.assertTrue(
            "tokeny delegatów „n/d”" in self.card_text
            or 'tokeny delegatów "n/d"' in self.card_text
            or "tokeny delegatów: „n/d”" in self.card_text
            or "tokeny delegatów: n/d" in self.card_text
        )
        self.assertIn("executedModel", self.card_text)
        self.assertIn("niepotwierdzony", self.card_text)


class TestNightRunT3CardInstall(unittest.TestCase):
    def setUp(self) -> None:
        if not resolve_bash():
            self.skipTest("brak bash")

    def test_installed_and_removed_by_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex")
            target = workspace / ".ai" / "night-run-t3.md"
            self.assertTrue(target.is_file(), f"Brak pliku {target} po instalacji")
            if CARD_TEMPLATE.is_file():
                self.assertEqual(target.read_bytes(), CARD_TEMPLATE.read_bytes())

            # Usunięcie przy --skip-agents
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex", skip_agents=True)
            self.assertFalse(target.exists(), f"Plik {target} nie został usunięty przy skip-agents")

            # Przywrócenie i usunięcie przez --remove
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex")
            self.assertTrue(target.is_file())
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex", remove=True)
            self.assertFalse(target.exists(), f"Plik {target} nie został usunięty przy remove")


if __name__ == "__main__":
    unittest.main()
