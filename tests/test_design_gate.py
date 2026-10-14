"""Etykiety `design: *`, bloki agentów zależne od klienta i dokument przekazania sesji designu (#189)."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from test_bootstrap import _BootstrapTestCase
from test_labels import FakeGh

from guides.bootstrap import run_bootstrap
from guides.labels import LABELS_REL_PATH, ensure_labels, read_label_set

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"
BLOCK = re.compile(r"<!-- clients: claude -->\n(.*?)<!-- /clients -->", re.DOTALL)
HANDOFF = "docs/agents/design-handoff.md"
CLAUDE_ONLY = ("Claude Design", "claude.ai/design", "/design-sync")


def _profile(root: Path, *, clients: str, web: str = "none", mobile: str = "none") -> Path:
    (root / ".ai").mkdir(parents=True, exist_ok=True)
    (root / ".ai" / "project.profile.yaml").write_text(
        f"name: t\nclients: {clients}\nbackend: none\nweb: {web}\nmobile: {mobile}\n",
        encoding="utf-8",
    )
    return root


class TestDesignLabels(unittest.TestCase):
    def test_label_rows(self) -> None:
        rows = {lb.name: lb for lb in read_label_set(KIT_ROOT)}
        for name in ("design: layout", "design: tokens"):
            self.assertEqual(rows[name].when, "web,mobile", name)
        self.assertTrue((KIT_ROOT / LABELS_REL_PATH).is_file())

    def _created(self, **profile: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _profile(Path(tmp), **profile)
            gh = FakeGh([])
            ensure_labels(ws, KIT_ROOT, dry_run=False, run=gh)
            return [n for n in gh.created() if n.startswith("design: ")]

    def test_design_labels_need_claude_and_client_tier(self) -> None:
        both = ["design: layout", "design: tokens"]
        self.assertEqual(self._created(clients="claude,opencode", web="react"), both)
        self.assertEqual(self._created(clients="[claude, opencode]", mobile="expo"), both)
        self.assertEqual(self._created(clients="opencode", web="react"), [])
        self.assertEqual(self._created(clients="claude"), [])


class TestAgentBlocks(unittest.TestCase):
    def _text(self, name: str) -> str:
        return (AGENTS / name).read_text(encoding="utf-8")

    def test_night_run_filter_outside_and_follow_up_inside(self) -> None:
        text = self._text("night-run.md")
        outside = BLOCK.sub("", text)
        self.assertIn("skipped: design spec missing", outside)
        self.assertIn("skipped: design: tokens", outside)
        inside = "".join(BLOCK.findall(text))
        self.assertIn("refactor: design layout for", inside)

    def test_create_task_design_line_in_block(self) -> None:
        inside = "".join(BLOCK.findall(self._text("create-task.md")))
        self.assertIn("Design: teraz | później", inside)
        self.assertIn("design: tokens", inside)

    def test_claude_only_names_live_in_blocks(self) -> None:
        for path in AGENTS.glob("*.md"):
            outside = BLOCK.sub("", path.read_text(encoding="utf-8"))
            for name in CLAUDE_ONLY:
                self.assertNotIn(name, outside, path.name)


class TestBootstrapGate(_BootstrapTestCase):
    def _run(self, workspace: Path, clients: str, web: str = "react") -> None:
        _profile(workspace, clients=clients, web=web)
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)

    def test_claude_keeps_block_without_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._run(workspace, "claude")
            text = (workspace / ".claude" / "agents" / "create-task.md").read_text(encoding="utf-8")
            self.assertIn("Design: teraz | później", text)
            self.assertNotIn("<!-- clients", text)
            self.assertNotIn("<!-- /clients", text)
            self.assertTrue((workspace / HANDOFF).is_file())

    def test_opencode_drops_block_and_claude_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._run(workspace, "opencode")
            self.assertFalse((workspace / HANDOFF).exists())
            for path in workspace.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    self.assertNotIn("Design: teraz", text, path)
                    for name in CLAUDE_ONLY:
                        self.assertNotIn(name, text, path)

    def test_reload_without_claude_removes_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._run(workspace, "claude,opencode")
            self.assertTrue((workspace / HANDOFF).is_file())
            self._run(workspace, "opencode")
            self.assertFalse((workspace / HANDOFF).exists())

    def test_no_client_tier_no_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._run(workspace, "claude", web="none")
            self.assertFalse((workspace / HANDOFF).exists())


if __name__ == "__main__":
    unittest.main()
