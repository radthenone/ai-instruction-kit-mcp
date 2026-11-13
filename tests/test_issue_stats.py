"""Testy jednostkowe ``kit-ai issue stats``.

Syntetyczne dane zamiast prawdziwych wywołań ``gh``.
Kluczowy test: wyjście zawiera dokładnie 4 sekcje z ustalonymi nagłówkami.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guides.issue_stats import (
    SECTION_HEADERS,
    IssueInfo,
    fetch_issues,
    generate_issue_stats_report,
    issue_stats_command,
    render_report,
    run_issue_stats,
)


def _make_gh_run(issues_data: list[dict], pr_data: list[dict] | None = None):
    """Fabryka fałszywego ``gh_run`` zwracającego syntetyczne dane."""
    pr_data = pr_data or []

    def gh_run(argv: list[str], cwd: Path) -> str:
        cmd = " ".join(argv)
        if "issue list" in cmd:
            return json.dumps(issues_data)
        if "pr list" in cmd:
            return json.dumps(pr_data)
        return ""

    return gh_run


def _sample_issue(
    number: int = 1,
    title: str = "Test issue",
    labels: list[str] | None = None,
    body: str = "",
) -> dict:
    if labels is None:
        labels = ["ready-for-agent"]
    return {
        "number": number,
        "title": title,
        "labels": [{"name": lbl} for lbl in labels],
        "body": body,
        "state": "open",
    }


def _body_with_criteria(n: int = 2) -> str:
    criteria_lines = "\n".join(f"- Kryterium {i}" for i in range(1, n + 1))
    return f"## Kryteria akceptacji\n\n{criteria_lines}\n"


class TestFetchIssues(unittest.TestCase):
    """Testy parsowania odpowiedzi ``gh issue list``."""

    def _fetch(self, data: list[dict]) -> list[IssueInfo]:
        gh = _make_gh_run(data)
        issues, _ = fetch_issues(Path("."), gh)
        return issues

    def test_empty_response_returns_empty_list(self) -> None:
        self.assertEqual(self._fetch([]), [])

    def test_parses_basic_issue(self) -> None:
        issues = self._fetch([_sample_issue(42, "Foo bar")])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].number, 42)
        self.assertEqual(issues[0].title, "Foo bar")

    def test_labels_parsed_from_dict(self) -> None:
        issues = self._fetch([_sample_issue(1, labels=["ready-for-agent", "bug"])])
        self.assertIn("ready-for-agent", issues[0].labels)
        self.assertIn("bug", issues[0].labels)

    def test_invalid_json_returns_empty(self) -> None:
        def bad_gh(argv, cwd):
            return "not json"

        issues, _ = fetch_issues(Path("."), bad_gh)
        self.assertEqual(issues, [])

    def test_missing_number_skipped(self) -> None:
        data = [{"title": "No number", "labels": [], "body": "", "state": "open"}]
        issues = self._fetch(data)
        self.assertEqual(issues, [])


class TestIssueInfoProperties(unittest.TestCase):
    """Testy właściwości IssueInfo."""

    def test_is_ready_when_label_present(self) -> None:
        issue = IssueInfo(1, "X", labels=["ready-for-agent"])
        self.assertTrue(issue.is_ready)

    def test_not_ready_when_label_absent(self) -> None:
        issue = IssueInfo(1, "X", labels=["bug"])
        self.assertFalse(issue.is_ready)

    def test_skip_label_wontfix(self) -> None:
        issue = IssueInfo(1, "X", labels=["wontfix", "ready-for-agent"])
        self.assertEqual(issue.skip_label, "wontfix")

    def test_skip_label_needs_triage(self) -> None:
        issue = IssueInfo(1, "X", labels=["needs-triage"])
        self.assertIsNotNone(issue.skip_label)

    def test_no_skip_label(self) -> None:
        issue = IssueInfo(1, "X", labels=["ready-for-agent"])
        self.assertIsNone(issue.skip_label)

    def test_acceptance_criteria_count_zero_for_empty_body(self) -> None:
        issue = IssueInfo(1, "X", body="")
        self.assertEqual(issue.acceptance_criteria_count, 0)

    def test_acceptance_criteria_count_two(self) -> None:
        issue = IssueInfo(1, "X", body=_body_with_criteria(2))
        self.assertEqual(issue.acceptance_criteria_count, 2)

    def test_acceptance_criteria_count_five(self) -> None:
        issue = IssueInfo(1, "X", body=_body_with_criteria(5))
        self.assertEqual(issue.acceptance_criteria_count, 5)

    def test_acceptance_criteria_stops_on_h3(self) -> None:
        """Kryteria kończą się na nagłówku ### Uwagi."""
        body = "## Kryteria akceptacji\n- Kryterium 1\n### Uwagi\n- Nie kryterium\n"
        issue = IssueInfo(1, "X", body=body)
        self.assertEqual(issue.acceptance_criteria_count, 1)

    def test_effort_label_small(self) -> None:
        issue = IssueInfo(1, "X", body=_body_with_criteria(1))
        self.assertIn("S", issue.effort_label)
        self.assertEqual(issue.estimated_minutes, "5–15 min")

    def test_effort_label_medium(self) -> None:
        issue = IssueInfo(1, "X", body=_body_with_criteria(3))
        self.assertIn("M", issue.effort_label)
        self.assertEqual(issue.estimated_minutes, "15–30 min")

    def test_effort_label_large(self) -> None:
        issue = IssueInfo(1, "X", body=_body_with_criteria(5))
        self.assertIn("L", issue.effort_label)
        self.assertEqual(issue.estimated_minutes, "30–60 min")

    def test_clean_title_escapes_pipe(self) -> None:
        issue = IssueInfo(1, "Fix A | B")
        self.assertEqual(issue.clean_title, "Fix A / B")

    def test_dependencies_parsing(self) -> None:
        body = "## Zakres\nZależy od #42 oraz wymaga #10"
        issue = IssueInfo(1, "Test", body=body)
        self.assertEqual(issue.dependencies, [42, 10])

    def test_open_questions_parsing(self) -> None:
        body = "## Otwarte pytania\n- Czy użyć biblioteki X?\n- Jaki timeout?\n"
        issue = IssueInfo(1, "Test", body=body)
        self.assertEqual(len(issue.open_questions), 2)


class TestRenderReport(unittest.TestCase):
    """Testy renderowania raportu."""

    def test_report_has_exactly_four_sections(self) -> None:
        """Raport musi zawierać dokładnie 4 sekcje z ustalonymi nagłówkami."""
        issues = [
            IssueInfo(1, "Issue A", labels=["ready-for-agent"], body=_body_with_criteria(2)),
            IssueInfo(2, "Issue B", labels=["ready-for-agent"], body=_body_with_criteria(4)),
        ]
        report = render_report(issues)
        # Wyodrębnij dokładnie nagłówki `## N.`
        headers = [line.strip() for line in report.splitlines() if re.match(r"^## \d+\.", line.strip())]
        self.assertEqual(headers, SECTION_HEADERS)

    def test_section_1_header_exact(self) -> None:
        issues = [IssueInfo(1, "X", labels=["ready-for-agent"])]
        report = render_report(issues)
        self.assertIn("## 1. Status bieżący: Co faktycznie zostało do zrobienia?", report)

    def test_section_2_header_exact(self) -> None:
        issues = [IssueInfo(1, "X", labels=["ready-for-agent"])]
        report = render_report(issues)
        self.assertIn("## 2. Rekomendowana kolejność prac (Roadmapa)", report)

    def test_section_3_header_exact(self) -> None:
        issues = [IssueInfo(1, "X", labels=["ready-for-agent"])]
        report = render_report(issues)
        self.assertIn("## 3. Podejście, skille i metodyka per zadanie", report)

    def test_section_4_header_exact(self) -> None:
        issues = [IssueInfo(1, "X", labels=["ready-for-agent"])]
        report = render_report(issues)
        self.assertIn("## 4. Przegląd gotowości issues pod night-run", report)

    def test_merged_issue_in_section_1(self) -> None:
        issue = IssueInfo(5, "Done issue", labels=["ready-for-agent"], merged_pr=True)
        report = render_report([issue])
        self.assertIn("zmergowane", report)
        self.assertIn("5", report)

    def test_skipped_issue_shown_in_section_1(self) -> None:
        issue = IssueInfo(3, "Skip me", labels=["wontfix"])
        report = render_report([issue])
        self.assertIn("wontfix", report)

    def test_ready_issue_in_night_run_table(self) -> None:
        issue = IssueInfo(7, "Ready issue", labels=["ready-for-agent"])
        report = render_report([issue])
        self.assertIn("/night-run #7", report)

    def test_empty_issues_still_has_four_sections(self) -> None:
        """Nawet przy braku issues muszą być 4 sekcje."""
        report = render_report([])
        headers = [line.strip() for line in report.splitlines() if re.match(r"^## \d+\.", line.strip())]
        self.assertEqual(headers, SECTION_HEADERS)

    def test_dependencies_ordering_in_roadmap(self) -> None:
        """Zadanie zależne musi być po zadaniu, od którego zależy."""
        issue_a = IssueInfo(1, "Podstawa", labels=["ready-for-agent"], body=_body_with_criteria(5))
        issue_b = IssueInfo(2, "Zależne", labels=["ready-for-agent"], body="## Zakres\nwymaga #1\n" + _body_with_criteria(1))
        report = render_report([issue_b, issue_a])
        pos_a = report.find("#1")
        pos_b = report.find("#2")
        self.assertTrue(pos_a != -1 and pos_b != -1)


class TestIssueStatsCommand(unittest.TestCase):
    """Integracyjny test komendy ``issue_stats_command``."""

    def test_command_returns_four_sections(self) -> None:
        data = [
            _sample_issue(1, "Alpha", body=_body_with_criteria(2)),
            _sample_issue(2, "Beta", labels=["needs-triage"], body=""),
        ]
        gh = _make_gh_run(data)
        result = issue_stats_command(Path("."), gh)
        headers = [line.strip() for line in result.splitlines() if re.match(r"^## \d+\.", line.strip())]
        self.assertEqual(headers, SECTION_HEADERS)

    def test_command_no_issues(self) -> None:
        gh = _make_gh_run([])
        result = issue_stats_command(Path("."), gh)
        self.assertIn("Brak otwartych issues", result)
        headers = [line.strip() for line in result.splitlines() if re.match(r"^## \d+\.", line.strip())]
        self.assertEqual(headers, SECTION_HEADERS)

    def test_command_detects_merged_pr(self) -> None:
        """Issue z powiązanym zmergowanym PR pojawia się jako 'zmergowane: 1'."""
        data = [_sample_issue(10, "Done", labels=["ready-for-agent"])]
        pr_data = [{"number": 99, "title": "PR for #10", "baseRefName": "dev", "headRefName": "feat/10-done", "body": "closes #10"}]
        gh = _make_gh_run(data, pr_data)
        result = issue_stats_command(Path("."), gh)
        self.assertIn("zmergowane: 1", result)
        self.assertIn("#10", result)

    def test_command_handles_gh_error(self) -> None:
        def failing_gh(argv, cwd):
            raise RuntimeError("Authentication failed")

        result = issue_stats_command(Path("."), failing_gh)
        self.assertIn("Błąd GitHub CLI", result)


if __name__ == "__main__":
    unittest.main()
