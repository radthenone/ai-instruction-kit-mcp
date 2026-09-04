"""Testy check_kit_updates — tani status driftu kita vs stamp bootstrapu."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from guides.kit_status import check_kit_updates


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_kit_repo(kit_root: Path) -> None:
    kit_root.mkdir(parents=True, exist_ok=True)
    _git(kit_root, "init", "-q")
    _git(kit_root, "config", "user.email", "test@test.local")
    _git(kit_root, "config", "user.name", "test")
    agents_dir = kit_root / "templates" / "shared" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "git-start.md").write_text("v1\n", encoding="utf-8")
    (kit_root / "templates" / "AGENTS.md").write_text("agents v1\n", encoding="utf-8")
    (kit_root / "unrelated.md").write_text("noise\n", encoding="utf-8")
    _git(kit_root, "add", "-A")
    _git(kit_root, "commit", "-q", "-m", "initial")


def _head(kit_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(kit_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_stamp(workspace: Path, kit_commit: str, kit_from: str = "local") -> None:
    ai_dir = workspace / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    (ai_dir / ".kit-bootstrap.json").write_text(
        json.dumps(
            {
                "kit_commit": kit_commit,
                "kit_from": kit_from,
                "bootstrapped_at": "2026-01-01T00:00:00Z",
                "preset": "_base",
                "language": "pl",
                "codegen": "orval",
                "clients": "all",
            }
        ),
        encoding="utf-8",
    )


class TestKitStatus(unittest.TestCase):
    def test_no_stamp_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            _init_kit_repo(kit_root)
            out = check_kit_updates(kit_root, workspace)
            self.assertIn("brak stampu", out)

    def test_empty_kit_commit_reports_no_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit="", kit_from="git+https://example.com/kit.git")
            out = check_kit_updates(kit_root, workspace)
            self.assertIn("brak historii git", out)

    def test_up_to_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))
            out = check_kit_updates(kit_root, workspace)
            self.assertIn("aktualny", out)

    def test_changed_tracked_file_lists_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            (kit_root / "templates" / "shared" / "agents" / "git-start.md").write_text(
                "v2\n", encoding="utf-8"
            )
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "update git-start")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("ZMIENIŁ SIĘ", out)
            self.assertIn("templates/shared/agents/git-start.md", out)

    def test_changed_untracked_file_no_rebootstrap_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            (kit_root / "unrelated.md").write_text("more noise\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "unrelated change")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("ZMIENIŁ SIĘ", out)
            self.assertIn("re-bootstrap niepotrzebny", out)
            self.assertNotIn("unrelated.md", out)

    def test_manual_file_is_not_promised_as_overwritten(self) -> None:
        """AGENTS.md bootstrap kopiuje tylko gdy brak — status nie może obiecać nadpisania."""
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            (kit_root / "templates" / "AGENTS.md").write_text("agents v2\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "update AGENTS template")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("templates/AGENTS.md", out)
            self.assertIn("NIE nadpisze", out)
            self.assertNotIn("Re-bootstrap wciągnie sam", out)

    def test_overwritten_and_manual_reported_separately(self) -> None:
        """Zmiana w obu kategoriach naraz — każda ląduje pod swoim nagłówkiem."""
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            (kit_root / "templates" / "shared" / "agents" / "git-start.md").write_text(
                "v2\n", encoding="utf-8"
            )
            (kit_root / "templates" / "AGENTS.md").write_text("agents v2\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "update both")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("Re-bootstrap wciągnie sam", out)
            self.assertIn("NIE nadpisze", out)
            overwritten_at = out.index("Re-bootstrap wciągnie sam")
            manual_at = out.index("NIE nadpisze")
            self.assertLess(overwritten_at, manual_at)
            # git-start jest nadpisywany, AGENTS.md nie — każdy pod swoją sekcją.
            self.assertLess(out.index("git-start.md"), manual_at)
            self.assertGreater(out.index("templates/AGENTS.md"), manual_at)

    def test_guard_change_is_reported(self) -> None:
        """Hooki bezpieczeństwa też są kopiowane — ich zmiana musi być widoczna."""
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            guards = kit_root / "templates" / "shared" / "guards"
            guards.mkdir(parents=True)
            (guards / "gate-destructive.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "add guard")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("templates/shared/guards/gate-destructive.sh", out)
            self.assertIn("Re-bootstrap wciągnie sam", out)

    def test_net_zero_change_shows_no_tracked_diff(self) -> None:
        """Commit + revert netto się znoszą — diff --name-only nic nie pokaże."""
        with tempfile.TemporaryDirectory() as tmp:
            kit_root = Path(tmp) / "kit"
            workspace = Path(tmp) / "workspace"
            _init_kit_repo(kit_root)
            _write_stamp(workspace, kit_commit=_head(kit_root))

            target = kit_root / "templates" / "shared" / "agents" / "git-start.md"
            target.write_text("v2\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "temp change")
            target.write_text("v1\n", encoding="utf-8")
            _git(kit_root, "add", "-A")
            _git(kit_root, "commit", "-q", "-m", "revert temp change")

            out = check_kit_updates(kit_root, workspace)
            self.assertIn("re-bootstrap niepotrzebny", out)


if __name__ == "__main__":
    unittest.main()
