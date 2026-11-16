"""``kit-ai retro scan`` — nocne logi ``night-run`` i ``opencode.log`` (#423).

Fixtury są syntetyczne i zamaskowane: żadna prawdziwa linia z nocy ani z ``opencode.log``
nie trafia do repo. Katalog nocy i plik ``opencode.log`` podaje test, nie cache użytkownika.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from guides import retro

KIT_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
NIGHT = "night-run-olivin-app-2026-10-28-catalog"
NIGHT_SESSION = "night-2026-10-28-catalog"
RUN_HEADER = (
    "[headless] log: ~/projects/olivin-app-night/.ai/headless-runs/"
    "2026-10-28T14-10-15-712Z-opencode/headless.log\n"
)
TICKET = "[headless] ticket #357\n"
ATTEMPT = "[headless] claude → opencode: ~/.bun/bin/opencode2 run --standalone --auto (timeout 90 min)\n"
REPORT = (
    "[headless] raport końcowy\n## git status --short\n(czysto)\n"
    "## git log 1fc3fea..HEAD --oneline\n(brak commitów)\n"
)
HALT_WITH_TICKET = (
    "night-run halted: wykonawca `/headless opencode` nie implementuje ticketów — "
    "2/2 próby na #357 zakończone bez żadnej zmiany w kodzie.\n"
)
WINDOW_END = datetime(2026, 10, 28, 15, 0, tzinfo=UTC).timestamp()
SECRET = "gho_" + "a" * 36


def _opencode(ts: str, level: str, message: str, cause: str = "") -> str:
    """Linia logfmt jak w ``opencode.log`` (synteza, bez prawdziwych danych)."""
    line = f"timestamp={ts} level={level} run=55ea6ea8 message=\"{message}\""
    if cause:
        line += f" cause=\"{cause}\""
    return line + "\n"


class NightRunScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.workspace = self.root / "work" / "olivin-app"
        self.workspace.mkdir(parents=True)
        self.home_cache = self.root / "home" / ".cache"
        self.night = self.home_cache / NIGHT
        self.night.mkdir(parents=True)
        self.opencode_log = self.root / "opencode.log"
        self.cache = self.root / "retro-cache"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _log(self, name: str, text: str, mtime: float | None = None) -> None:
        path = self.night / name
        path.write_text(text, encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def _scan(self, since: str | None = None) -> str:
        return retro.scan_command(
            self.workspace,
            session=None,
            since=since,
            projects_root=self.root / "no-claude-projects",
            cache_root=self.cache,
            kit_root=KIT_ROOT,
            runner=lambda signal: "deny",
            now=NOW,
            night_root=self.home_cache,
            opencode_log=self.opencode_log,
        )

    def _records(self, session: str) -> list[dict]:
        target = self.cache / "olivin-app" / f"{session}.jsonl"
        self.assertTrue(target.is_file(), f"brak sesji {session}")
        return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]

    def _findings(self, session: str) -> list[dict]:
        return [record for record in self._records(session) if record["type"] == "finding"]

    def test_two_logs_of_one_ticket_make_one_session_with_two_attempts(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        self._log("headless-357-r2.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        self._scan()
        records = self._records(f"{NIGHT_SESSION}-357")
        self.assertEqual(records[0]["type"], "session")
        self.assertEqual(records[0]["attempts"], 2)
        self.assertEqual(records[0]["files"], 2)
        self.assertEqual(
            sorted(path.name for path in (self.cache / "olivin-app").iterdir()),
            [f"{NIGHT_SESSION}-357.jsonl"],
        )

    def test_echoed_attempt_lines_do_not_count_as_attempts(self) -> None:
        echo = "[headless] ticket #357\n[headless] claude → opencode: ~/.bun/bin/opencode2 run --standalone --auto\n"
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + echo + REPORT)
        self._scan()
        self.assertEqual(self._records(f"{NIGHT_SESSION}-357")[0]["attempts"], 1)

    def test_since_keeps_every_log_of_a_ticket_when_one_is_fresh(self) -> None:
        old = datetime(2026, 10, 1, tzinfo=UTC).timestamp()
        fresh = datetime(2026, 11, 10, tzinfo=UTC).timestamp()
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=old)
        self._log("headless-357-r2.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=fresh)
        self._scan(since="2026-11-01")
        records = self._records(f"{NIGHT_SESSION}-357")
        self.assertEqual(records[0]["attempts"], 2)
        self.assertEqual(records[0]["files"], 2)

    def test_night_level_halt_id_does_not_collide_with_ticket_of_base_night(self) -> None:
        base = self.home_cache / "night-run-olivin-app-2026-10-28"
        suffixed = self.home_cache / "night-run-olivin-app-2026-10-28-2"
        base.mkdir()
        suffixed.mkdir()
        (base / "headless-2.log").write_text(RUN_HEADER + TICKET.replace("357", "2") + ATTEMPT + REPORT, encoding="utf-8")
        (suffixed / "halt.md").write_text("night-run halted: brak zasobów w CI\n", encoding="utf-8")
        self._scan()
        self.assertEqual(self._findings("night-2026-10-28-2"), [])
        self.assertEqual([finding["kind"] for finding in self._findings("night-2026-10-28-2-halt")], ["night_halt"])

    def test_since_includes_a_fresh_halt_for_a_ticket_with_stale_logs(self) -> None:
        old = datetime(2026, 10, 1, tzinfo=UTC).timestamp()
        fresh = datetime(2026, 11, 10, tzinfo=UTC).timestamp()
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=old)
        (self.night / "halt.md").write_text(HALT_WITH_TICKET, encoding="utf-8")
        os.utime(self.night / "halt.md", (fresh, fresh))
        self._scan(since="2026-11-01")
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["kind"], "night_halt")
        self.assertEqual(self._records(f"{NIGHT_SESSION}-357")[0]["files"], 1)

    def test_since_keeps_a_stale_halt_when_its_ticket_has_fresh_logs(self) -> None:
        old = datetime(2026, 10, 1, tzinfo=UTC).timestamp()
        fresh = datetime(2026, 11, 10, tzinfo=UTC).timestamp()
        (self.night / "halt.md").write_text(HALT_WITH_TICKET, encoding="utf-8")
        os.utime(self.night / "halt.md", (old, old))
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=fresh)
        self._scan(since="2026-11-01")
        self.assertEqual([finding["kind"] for finding in self._findings(f"{NIGHT_SESSION}-357")], ["night_halt"])

    def test_since_skips_a_stale_halt_without_ticket_number(self) -> None:
        old = datetime(2026, 10, 1, tzinfo=UTC).timestamp()
        (self.night / "halt.md").write_text("night-run halted: brak zasobów w CI\n", encoding="utf-8")
        os.utime(self.night / "halt.md", (old, old))
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=old)
        self._scan(since="2026-11-01")
        self.assertFalse((self.cache / "olivin-app" / f"{NIGHT_SESSION}-halt.jsonl").exists())

    def test_last_exit_line_of_a_log_decides_over_echoed_ones(self) -> None:
        self._log(
            "headless-357.log",
            RUN_HEADER + TICKET + ATTEMPT + "[headless] kod wyjścia: 1\n" + REPORT + "[headless] kod wyjścia: 0\n",
        )
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["fingerprint"], retro.fingerprint("headless_no_change", "exit0-clean-tree"))

    def test_report_without_exit_line_is_old_format_not_exit_missing(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        self._scan()
        self.assertEqual(self._findings(f"{NIGHT_SESSION}-357"), [])

    def test_log_without_exit_line_and_report_is_exit_missing(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + "[headless] sygnał SIGTERM po 1837.7 s\n")
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["fingerprint"], retro.fingerprint("headless_exit", "exit-missing"))

    def test_nonzero_exit_line_is_classified(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + "[headless] kod wyjścia: 1\n")
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["fingerprint"], retro.fingerprint("headless_exit", "exit-nonzero"))

    def test_zero_exit_with_clean_tree_is_no_change(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + "[headless] kod wyjścia: 0\n" + REPORT)
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["fingerprint"], retro.fingerprint("headless_no_change", "exit0-clean-tree"))

    def test_halt_with_ticket_number_lands_on_that_session(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        (self.night / "halt.md").write_text(HALT_WITH_TICKET + "\n## szczegóły\n", encoding="utf-8")
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual(finding["kind"], "night_halt")

    def test_halt_without_ticket_number_is_counted_on_night_session(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        (self.night / "halt.md").write_text("night-run halted: brak zasobów w CI\n", encoding="utf-8")
        self._scan()
        [finding] = self._findings(f"{NIGHT_SESSION}-halt")
        self.assertEqual(finding["kind"], "night_halt")
        self.assertEqual(self._findings(f"{NIGHT_SESSION}-357"), [])

    def test_error_lines_in_ticket_window_become_one_fingerprint(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=WINDOW_END)
        lines = [
            _opencode(
                f"2026-10-28T14:20:{i:02d}.000Z",
                "ERROR",
                "Failed to drain Session",
                f"FileSystem.DirectoryNotFoundError: Directory not found: /home/tester/projects/synthetic-app-{i}",
            )
            for i in range(22)
        ]
        lines.append(
            _opencode(
                "2026-10-28T14:30:00.000Z",
                "ERROR",
                "cli process failed",
                "Cause([Fail(~effect/cli/CliError/ShowHelp: Help requested)])",
            )
        )
        lines.append(_opencode("2026-10-28T14:31:00.000Z", "WARN", "config noise"))
        lines.append(
            _opencode(
                "2026-10-28T16:30:00.000Z",
                "ERROR",
                "Failed to drain Session",
                "FileSystem.DirectoryNotFoundError: Directory not found: /home/tester/x",
            )
        )
        self.opencode_log.write_text("".join(lines), encoding="utf-8")
        self._scan()
        findings = self._findings(f"{NIGHT_SESSION}-357")
        self.assertEqual([(finding["kind"], finding["count"]) for finding in findings], [("opencode_error", 22)])

    def test_evidence_from_night_sources_is_masked(self) -> None:
        (self.night / "halt.md").write_text(
            f"night-run halted: #357 kontakt ops.synthetic@example.invalid token={SECRET} w /home/tester/work\n",
            encoding="utf-8",
        )
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=WINDOW_END)
        self.opencode_log.write_text(
            _opencode(
                "2026-10-28T14:20:00.000Z",
                "ERROR",
                "Failed to drain Session",
                f"FileSystem.DirectoryNotFoundError: Directory not found: /home/tester/x {SECRET}",
            ),
            encoding="utf-8",
        )
        self._scan()
        raw = (self.cache / "olivin-app" / f"{NIGHT_SESSION}-357.jsonl").read_text(encoding="utf-8")
        for leaked in ("ops.synthetic@example.invalid", SECRET, "/home/tester"):
            self.assertNotIn(leaked, raw)
        self.assertIn("<email>", raw)
        self.assertIn("<secret>", raw)

    def test_night_dir_of_other_repo_is_not_scanned(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT)
        other = self.home_cache / "night-run-olivin-app-kit-test-2026-11-10"
        other.mkdir()
        (other / "headless-500.log").write_text(RUN_HEADER + TICKET + ATTEMPT + REPORT, encoding="utf-8")
        self._scan()
        self.assertEqual(
            sorted(path.name for path in (self.cache / "olivin-app").iterdir()),
            [f"{NIGHT_SESSION}-357.jsonl"],
        )

    def test_since_skips_night_logs_older_than_cutoff(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=0)
        self._scan(since="2020-01-01")
        self.assertFalse((self.cache / "olivin-app" / f"{NIGHT_SESSION}-357.jsonl").exists())

    def test_missing_opencode_log_is_not_an_error(self) -> None:
        self._log("headless-357.log", RUN_HEADER + TICKET + ATTEMPT + REPORT, mtime=WINDOW_END)
        self._scan()
        self.assertEqual(self._findings(f"{NIGHT_SESSION}-357"), [])


if __name__ == "__main__":
    unittest.main()
