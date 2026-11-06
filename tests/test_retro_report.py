"""``kit-ai retro report`` — progi sesji i repo (#373, część (c) #338).

Fikstury to syntetyczne wpisy ``finding`` w kształcie zapisu ``kit-ai retro scan``
w ``<cache>/<repo>/<sesja>.jsonl``. Żadna prawdziwa wiadomość z sesji nie trafia do repo.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
        return retro_report.report_command(self.workspace, cache_root=self.cache)

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


if __name__ == "__main__":
    unittest.main()
