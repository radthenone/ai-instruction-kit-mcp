"""Testy jednostkowe ``kit-ai pr stats``.

Syntetyczne dane zamiast prawdziwych wywołań ``gh``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guides.pr_stats import (
    PR_SECTION_HEADERS,
    CheckRun,
    PRInfo,
    Review,
    fetch_prs,
    generate_pr_stats_report,
    pr_stats_command,
    render_pr_report,
    run_pr_stats,
)


def _make_gh_run(
    prs_data: list[dict] | None = None,
    checks_data: dict[int, list[dict]] | None = None,
    reviews_data: dict[int, list[dict]] | None = None,
):
    """Fabryka fałszywego ``gh_run`` zwracającego syntetyczne dane."""
    prs_data = prs_data or []
    checks_data = checks_data or {}
    reviews_data = reviews_data or {}

    def gh_run(argv: list[str], cwd: Path) -> str:
        cmd = " ".join(argv)
        if "pr list" in cmd:
            return json.dumps(prs_data)
        if "pr checks" in cmd:
            # Odrzuć nieobsługiwane pola JSON
            if "status" in cmd or "conclusion" in cmd:
                raise RuntimeError("gh: unknown JSON fields: status, conclusion")
            for arg in argv:
                try:
                    num = int(arg)
                    if num in checks_data:
                        return json.dumps(checks_data[num])
                except (ValueError, IndexError):
                    pass
            return "[]"
        if "pr view" in cmd:
            for arg in argv:
                try:
                    num = int(arg)
                    if num in reviews_data:
                        return json.dumps({"latestReviews": reviews_data[num]})
                except (ValueError, IndexError):
                    pass
            return json.dumps({"latestReviews": []})
        return ""

    return gh_run


def _sample_pr(
    number: int = 1,
    title: str = "Test PR",
    base: str = "dev",
    head: str = "feat/test",
    author: str = "developer",
    is_draft: bool = False,
    mergeable: str = "MERGEABLE",
) -> dict:
    return {
        "number": number,
        "title": title,
        "baseRefName": base,
        "headRefName": head,
        "author": {"login": author},
        "state": "open",
        "isDraft": is_draft,
        "mergeable": mergeable,
    }


def _check(name: str, state: str = "SUCCESS", bucket: str = "pass") -> dict:
    return {"name": name, "state": state, "bucket": bucket}


def _review(login: str, state: str = "APPROVED") -> dict:
    return {"author": {"login": login}, "state": state}


class TestFetchPRs(unittest.TestCase):
    """Testy parsowania odpowiedzi ``gh pr list``."""

    def _fetch(self, data: list[dict]) -> list[PRInfo]:
        gh = _make_gh_run(data)
        prs, _ = fetch_prs(Path("."), gh)
        return prs

    def test_empty_response_returns_empty_list(self) -> None:
        self.assertEqual(self._fetch([]), [])

    def test_parses_basic_pr(self) -> None:
        prs = self._fetch([_sample_pr(42, "My PR")])
        self.assertEqual(len(prs), 1)
        self.assertEqual(prs[0].number, 42)
        self.assertEqual(prs[0].title, "My PR")

    def test_parses_draft_flag(self) -> None:
        prs = self._fetch([_sample_pr(1, is_draft=True)])
        self.assertTrue(prs[0].is_draft)

    def test_parses_author_login(self) -> None:
        prs = self._fetch([_sample_pr(1, author="alice")])
        self.assertEqual(prs[0].author, "alice")

    def test_invalid_json_returns_empty(self) -> None:
        def bad_gh(argv, cwd):
            return "not json"
        prs, _ = fetch_prs(Path("."), bad_gh)
        self.assertEqual(prs, [])

    def test_missing_number_skipped(self) -> None:
        data = [{"title": "No number", "baseRefName": "dev", "state": "open"}]
        prs = self._fetch(data)
        self.assertEqual(prs, [])


class TestPRInfoProperties(unittest.TestCase):
    """Testy właściwości PRInfo."""

    def _pr(self, checks: list[CheckRun] | None = None, reviews: list[Review] | None = None, **kw) -> PRInfo:
        pr = PRInfo(
            number=kw.get("number", 1),
            title=kw.get("title", "X"),
            base_ref=kw.get("base_ref", "dev"),
            head_ref=kw.get("head_ref", "feat/x"),
            author=kw.get("author", "user"),
            state=kw.get("state", "open"),
            is_draft=kw.get("is_draft", False),
            mergeable=kw.get("mergeable", "MERGEABLE"),
        )
        pr.checks = checks or []
        pr.reviews = reviews or []
        return pr

    def test_checks_summary_empty(self) -> None:
        pr = self._pr()
        self.assertEqual(pr.checks_summary, "brak")

    def test_checks_summary_all_success(self) -> None:
        pr = self._pr(checks=[
            CheckRun("ci", "SUCCESS", "pass"),
            CheckRun("lint", "SUCCESS", "pass"),
        ])
        self.assertIn("✓2", pr.checks_summary)

    def test_checks_summary_has_failure(self) -> None:
        pr = self._pr(checks=[
            CheckRun("ci", "FAILURE", "fail"),
        ])
        self.assertIn("✗1", pr.checks_summary)

    def test_has_failing_checks(self) -> None:
        pr = self._pr(checks=[CheckRun("ci", "FAILURE", "fail")])
        self.assertTrue(pr.has_failing_checks)

    def test_no_failing_checks(self) -> None:
        pr = self._pr(checks=[CheckRun("ci", "SUCCESS", "pass")])
        self.assertFalse(pr.has_failing_checks)

    def test_risk_high_on_failing_checks(self) -> None:
        pr = self._pr(checks=[CheckRun("ci", "FAILURE", "fail")])
        self.assertEqual(pr.risk_level, "HIGH")

    def test_risk_high_on_changes_requested(self) -> None:
        pr = self._pr(reviews=[Review("alice", "CHANGES_REQUESTED")])
        self.assertEqual(pr.risk_level, "HIGH")

    def test_risk_high_on_conflict(self) -> None:
        pr = self._pr(mergeable="CONFLICTING")
        self.assertEqual(pr.risk_level, "HIGH")

    def test_risk_medium_pending_checks(self) -> None:
        pr = self._pr(checks=[CheckRun("ci", "PENDING", "pending")])
        self.assertEqual(pr.risk_level, "MEDIUM")

    def test_risk_medium_no_human_approval(self) -> None:
        pr = self._pr()  # brak reviews
        self.assertEqual(pr.risk_level, "MEDIUM")

    def test_risk_medium_empty_checks(self) -> None:
        """PR bez checków nie może dostać LOW nawet z akceptacją."""
        pr = self._pr(checks=[], reviews=[Review("alice", "APPROVED")])
        self.assertEqual(pr.risk_level, "MEDIUM")

    def test_risk_low_approved_all_pass(self) -> None:
        pr = self._pr(
            checks=[CheckRun("ci", "SUCCESS", "pass")],
            reviews=[Review("alice", "APPROVED")],
        )
        self.assertEqual(pr.risk_level, "LOW")

    def test_bot_review_detected(self) -> None:
        pr = self._pr(reviews=[Review("coderabbit[bot]", "APPROVED", is_bot=True)])
        self.assertTrue(pr.is_bot_reviewed)

    def test_human_approval(self) -> None:
        pr = self._pr(reviews=[Review("alice", "APPROVED", is_bot=False)])
        self.assertTrue(pr.has_human_approval)

    def test_no_human_approval_when_only_bot(self) -> None:
        pr = self._pr(reviews=[Review("coderabbit[bot]", "APPROVED", is_bot=True)])
        self.assertFalse(pr.has_human_approval)

    def test_clean_title_escapes_pipe(self) -> None:
        pr = self._pr(title="Fix A | B")
        self.assertEqual(pr.clean_title, "Fix A / B")


class TestRenderPRReport(unittest.TestCase):
    """Testy renderowania raportu PR."""

    def test_report_has_exactly_three_sections(self) -> None:
        """Raport musi zawierać dokładnie 3 sekcje z ustalonymi nagłówkami."""
        pr = PRInfo(1, "My PR", "dev", "feat/x", "alice", "open")
        pr.checks = [CheckRun("ci", "SUCCESS", "pass")]
        pr.reviews = [Review("alice", "APPROVED")]
        report = render_pr_report([pr])
        for header in PR_SECTION_HEADERS:
            self.assertIn(header, report, f"Brak nagłówka: {header!r}")

    def test_section_1_header_exact(self) -> None:
        report = render_pr_report([])
        self.assertIn("## 1. Tabela PR", report)

    def test_section_2_header_exact(self) -> None:
        report = render_pr_report([])
        self.assertIn("## 2. Analiza ryzyk", report)

    def test_section_3_header_exact(self) -> None:
        report = render_pr_report([])
        self.assertIn("## 3. Rekomendowane akcje", report)

    def test_empty_prs_still_has_three_sections(self) -> None:
        report = render_pr_report([])
        for header in PR_SECTION_HEADERS:
            self.assertIn(header, report, f"Brak nagłówka przy pustej liście: {header!r}")

    def test_pr_appears_in_table(self) -> None:
        pr = PRInfo(42, "Feature X", "dev", "feat/x", "bob", "open")
        report = render_pr_report([pr])
        self.assertIn("42", report)
        self.assertIn("Feature X", report)

    def test_high_risk_shown_in_analysis(self) -> None:
        pr = PRInfo(1, "Failing PR", "dev", "feat/x", "alice", "open", mergeable="CONFLICTING")
        report = render_pr_report([pr])
        self.assertIn("HIGH", report)

    def test_merge_ready_in_recommendations(self) -> None:
        pr = PRInfo(5, "Ready PR", "dev", "feat/x", "alice", "open", mergeable="MERGEABLE")
        pr.checks = [CheckRun("ci", "SUCCESS", "pass")]
        pr.reviews = [Review("bob", "APPROVED", is_bot=False)]
        report = render_pr_report([pr])
        self.assertIn("merge", report.lower())
        self.assertIn("5", report)

    def test_conflict_shown_in_recommendations(self) -> None:
        pr = PRInfo(3, "Conflict PR", "dev", "feat/x", "alice", "open", mergeable="CONFLICTING")
        report = render_pr_report([pr])
        self.assertIn("Konflikty", report)


class TestPRStatsCommand(unittest.TestCase):
    """Integracyjny test komendy ``pr_stats_command``."""

    def test_command_returns_three_sections(self) -> None:
        data = [
            _sample_pr(1, "Alpha"),
            _sample_pr(2, "Beta", is_draft=True),
        ]
        gh = _make_gh_run(data)
        result = pr_stats_command(Path("."), gh)
        for header in PR_SECTION_HEADERS:
            self.assertIn(header, result, f"Brak sekcji: {header!r}")

    def test_command_no_prs(self) -> None:
        gh = _make_gh_run([])
        result = pr_stats_command(Path("."), gh)
        self.assertIn("Brak otwartych PR", result)

    def test_command_risk_assessment_with_failing_check(self) -> None:
        data = [_sample_pr(10, "Failing", mergeable="MERGEABLE")]
        checks = {10: [_check("ci", "FAILURE", "fail")]}
        gh = _make_gh_run(data, checks)
        result = pr_stats_command(Path("."), gh)
        self.assertIn("HIGH", result)

    def test_command_handles_gh_error(self) -> None:
        def failing_gh(argv, cwd):
            raise RuntimeError("Authentication failed")

        result = pr_stats_command(Path("."), failing_gh)
        self.assertIn("Błąd GitHub CLI", result)


if __name__ == "__main__":
    unittest.main()
