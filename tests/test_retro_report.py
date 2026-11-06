"""``kit-ai retro report`` — progi sesji i repo (#373, część (c) #338).

Fikstury to syntetyczne wpisy ``finding`` w kształcie zapisu ``kit-ai retro scan``
w ``<cache>/<repo>/<sesja>.jsonl``. Żadna prawdziwa wiadomość z sesji nie trafia do repo.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides import retro_report

FP_GUARD = "0123456789abcdef"
FP_TOOL = "fedcba9876543210"


def _finding(fingerprint: str, *, count: int = 1, replay: str = "deny") -> dict:
    return {
        "type": "finding",
        "kind": "guard_deny",
        "fingerprint": fingerprint,
        "guard": "git-guard",
        "tool": "Bash",
        "count": count,
        "replay": replay,
        "evidence": "git-guard: git checkout . — kasuje niezacommitowane zmiany",
    }


def _write_session(
    cache: Path, repo: str, session: str, findings: list[dict], *, kit_sha: str = "aaaaaaaaaaaa"
) -> Path:
    records: list[dict] = [{"type": "session", "repo": repo, "session": session, "findings": len(findings)}]
    records += [{**finding, "repo": repo, "session": session, "kit_sha": kit_sha} for finding in findings]
    path = cache / repo / f"{session}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def _issues(*bodies: str) -> str:
    return json.dumps([{"body": body} for body in bodies], ensure_ascii=False)


def _marker(fingerprint: str) -> str:
    return f"Opis karty\n\n<!-- retro-fingerprint: {fingerprint} -->\n"


def _no_open_issues(argv: list[str], cwd: Path) -> str:
    return "[]"


class ThresholdTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cache = self.root / "cache"
        self.workspace = self.root / "kit"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _report(self) -> str:
        return retro_report.report_command(self.workspace, cache_root=self.cache, gh_run=_no_open_issues)

    def test_empty_cache_says_so(self) -> None:
        self.assertIn("brak znalezisk", self._report())

    def test_three_sessions_in_one_repo_reach_the_threshold(self) -> None:
        for session in ("s1", "s2", "s3"):
            _write_session(self.cache, "alpha", session, [_finding(FP_GUARD)])
        self.assertIn(FP_GUARD, self._report())

    def test_two_sessions_in_one_repo_stay_below_the_threshold(self) -> None:
        for session in ("s1", "s2"):
            _write_session(self.cache, "alpha", session, [_finding(FP_GUARD)])
        report = self._report()
        self.assertNotIn(FP_GUARD, report)
        self.assertIn("Brak propozycji", report)

    def test_two_repos_reach_the_threshold_with_one_session_each(self) -> None:
        _write_session(self.cache, "alpha", "s1", [_finding(FP_GUARD)])
        _write_session(self.cache, "beta", "s2", [_finding(FP_GUARD)])
        self.assertIn(FP_GUARD, self._report())

    def test_sessions_without_the_finding_do_not_count(self) -> None:
        """Repo ma cztery sesje, ale znalezisko jest tylko w jednej — próg dotyczy wystąpień znaleziska."""
        _write_session(self.cache, "alpha", "s1", [_finding(FP_GUARD)])
        _write_session(self.cache, "alpha", "s2", [_finding(FP_TOOL)])
        _write_session(self.cache, "alpha", "s3", [_finding(FP_TOOL)])
        _write_session(self.cache, "alpha", "s4", [])
        self.assertNotIn(FP_GUARD, self._report())

    def test_count_sums_occurrences_across_sessions(self) -> None:
        for session, count in (("s1", 2), ("s2", 1), ("s3", 4)):
            _write_session(self.cache, "alpha", session, [_finding(FP_GUARD, count=count)])
        self.assertIn("wystąpienia: 7", self._report())

    def test_proposal_shows_replay_status_and_kit_versions(self) -> None:
        _write_session(self.cache, "alpha", "s1", [_finding(FP_GUARD, replay="deny")], kit_sha="aaaaaaaaaaaa")
        _write_session(self.cache, "alpha", "s2", [_finding(FP_GUARD, replay="unknown")], kit_sha="bbbbbbbbbbbb")
        _write_session(self.cache, "alpha", "s3", [_finding(FP_GUARD, replay="deny")], kit_sha="bbbbbbbbbbbb")
        report = self._report()
        self.assertIn("replay: deny, unknown", report)
        self.assertIn("kit: aaaaaaaaaaaa, bbbbbbbbbbbb", report)

    def test_malformed_lines_and_staging_files_are_not_counted(self) -> None:
        """Uszkodzona linia nie wywala raportu, a plik ``.tmp`` po przerwanym zapisie nie liczy się jako sesja."""
        _write_session(self.cache, "alpha", "s1", [_finding(FP_GUARD)])
        _write_session(self.cache, "alpha", "s2", [_finding(FP_GUARD)])
        broken = _write_session(self.cache, "alpha", "s3", [_finding(FP_GUARD)])
        broken.write_text(broken.read_text(encoding="utf-8") + "{nie json\n", encoding="utf-8")
        _write_session(self.cache, "beta", "s4", [_finding(FP_TOOL)])
        for staging_name in ("s5.jsonl.tmp", "s6.jsonl.tmp"):
            staging = self.cache / "beta" / staging_name
            staging.write_text(json.dumps(_finding(FP_TOOL)) + "\n", encoding="utf-8")
        report = self._report()
        self.assertIn(FP_GUARD, report)
        self.assertNotIn(FP_TOOL, report)


class DedupTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cache = self.root / "cache"
        self.workspace = self.root / "kit"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _report(self, open_issues: str = "[]") -> str:
        return retro_report.report_command(self.workspace, cache_root=self.cache, gh_run=lambda argv, cwd: open_issues)

    def _three_sessions(self, *fingerprints: str) -> None:
        for session in ("s1", "s2", "s3"):
            _write_session(self.cache, "alpha", session, [_finding(fp) for fp in fingerprints])

    def test_open_issue_with_marker_drops_the_proposal(self) -> None:
        self._three_sessions(FP_GUARD)
        report = self._report(_issues(_marker(FP_GUARD)))
        self.assertNotIn(FP_GUARD, report)
        self.assertIn("pominięte (otwarte issue): 1", report)
        self.assertIn("propozycje 0", report)

    def test_other_fingerprints_are_still_proposed(self) -> None:
        self._three_sessions(FP_GUARD, FP_TOOL)
        report = self._report(_issues(_marker(FP_GUARD)))
        self.assertNotIn(FP_GUARD, report)
        self.assertIn(FP_TOOL, report)
        self.assertIn("pominięte (otwarte issue): 1", report)

    def test_marker_must_carry_a_full_fingerprint(self) -> None:
        self._three_sessions(FP_GUARD)
        self.assertIn(FP_GUARD, self._report(_issues("<!-- retro-fingerprint: 0123 -->")))

    def test_github_is_asked_for_open_issues_only(self) -> None:
        self._three_sessions(FP_GUARD)
        gh_run = mock.Mock(return_value="[]")
        retro_report.report_command(self.workspace, cache_root=self.cache, gh_run=gh_run)
        gh_run.assert_called_once()
        argv, cwd = gh_run.call_args.args
        self.assertEqual(argv[:3], ["gh", "issue", "list"])
        self.assertEqual(argv[argv.index("--state") + 1], "open")
        self.assertEqual(argv[argv.index("--json") + 1], "body")
        self.assertEqual(cwd, self.workspace)

    def test_github_is_not_asked_without_candidates(self) -> None:
        _write_session(self.cache, "alpha", "s1", [_finding(FP_GUARD)])
        gh_run = mock.Mock(return_value="[]")
        retro_report.report_command(self.workspace, cache_root=self.cache, gh_run=gh_run)
        gh_run.assert_not_called()

    def test_missing_gh_refuses_the_report_instead_of_listing_duplicates(self) -> None:
        self._three_sessions(FP_GUARD)
        with mock.patch("guides.retro_report.subprocess.run", side_effect=OSError("brak gh")):
            with self.assertRaises(ValueError) as context:
                retro_report.report_command(self.workspace, cache_root=self.cache)
        self.assertIn("gh", str(context.exception))

    def test_unreadable_github_answer_is_refused(self) -> None:
        self._three_sessions(FP_GUARD)
        with self.assertRaises(ValueError):
            self._report("nie json")

    def test_proposal_carries_marker_for_the_card(self) -> None:
        self._three_sessions(FP_GUARD)
        self.assertIn(f"<!-- retro-fingerprint: {FP_GUARD} -->", self._report())

    def test_proposal_names_both_card_routes(self) -> None:
        self._three_sessions(FP_GUARD)
        report = self._report()
        self.assertIn("/create-task", report)
        self.assertIn("/kit-project-edit", report)


class ParseOpenIssuesTests(unittest.TestCase):
    def test_collects_markers_from_every_issue_body(self) -> None:
        payload = _issues(_marker(FP_GUARD), "bez markera", _marker(FP_TOOL))
        self.assertEqual(retro_report.parse_open_issues(payload), {FP_GUARD, FP_TOOL})

    def test_issues_without_text_body_contribute_nothing(self) -> None:
        self.assertEqual(retro_report.parse_open_issues('[{"title": "x"}, {"body": null}]'), set())

    def test_non_list_answer_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            retro_report.parse_open_issues('{"body": "x"}')


if __name__ == "__main__":
    unittest.main()
