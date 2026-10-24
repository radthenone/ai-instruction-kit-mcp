"""Kontrakt skilli Matta i ``CODING_STANDARDS.md`` w repo aplikacji (#241).

Testy modułu: render plików z ziaren setupu Matta, blok ``## Agent skills``,
indeks standardów i ``--remove`` wyłącznie dla nietkniętego renderu kita.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _shell import is_ci, resolve_bash

from guides.bootstrap import plan_bootstrap, run_bootstrap
from guides.matt_contract import (
    AGENT_SKILLS_HEADING,
    CODING_STANDARDS_REL,
    agent_skills_block,
    coding_standards,
    has_matt_skills,
    merge_agent_skills,
    remove,
    sync,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = Path(".agents/skills/setup-matt-pocock-skills")

SEED_ISSUE_TRACKER = """# Issue tracker: GitHub

Issues live as GitHub issues. Use `gh`.
"""
SEED_TRIAGE = """# Triage Labels

| Label in mattpocock/skills | Label in our tracker | Meaning |
| -------------------------- | -------------------- | ------- |
| `needs-triage`             | `needs-triage`       | evaluate |
| `wontfix`                  | `wontfix`            | no      |
"""
SEED_DOMAIN = """# Domain Docs

Read `GLOSSARY.md` or `GLOSSARY-MAP.md` and `docs/adr/`.

## File structure

Single-context repo (most repos):

```
/
├── GLOSSARY.md
└── docs/adr/
```
"""


def _lock(workspace: Path, source: str = "mattpocock/skills") -> None:
    payload = {"version": 1, "skills": {"grill-me": {"source": source, "sourceType": "github"}}}
    (workspace / "skills-lock.json").write_text(json.dumps(payload), encoding="utf-8")


def _seeds(workspace: Path, *, tracker: str = SEED_ISSUE_TRACKER,
           triage: str = SEED_TRIAGE, domain: str = SEED_DOMAIN) -> None:
    target = workspace / SEED_DIR
    target.mkdir(parents=True, exist_ok=True)
    (target / "issue-tracker-github.md").write_text(tracker, encoding="utf-8", newline="\n")
    (target / "triage-labels.md").write_text(triage, encoding="utf-8", newline="\n")
    (target / "domain.md").write_text(domain, encoding="utf-8", newline="\n")


def _workspace(tmp: str, *, matt: bool = True, seeds: bool = True) -> Path:
    workspace = Path(tmp) / "app"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("# App\n\nReguły projektu.\n", encoding="utf-8")
    if matt:
        _lock(workspace)
    if seeds:
        _seeds(workspace)
    return workspace


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestDetection(unittest.TestCase):
    def test_lock_with_matt_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            self.assertTrue(has_matt_skills(workspace))

    def test_other_source_and_broken_lock_are_not_matt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp, seeds=False)
            _lock(workspace, source="someone/else")
            self.assertFalse(has_matt_skills(workspace))

            (workspace / "skills-lock.json").write_text("{not json", encoding="utf-8")
            self.assertFalse(has_matt_skills(workspace))

    def test_missing_lock_is_not_matt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self.assertFalse(has_matt_skills(workspace))


class TestContractFiles(unittest.TestCase):
    def test_creates_missing_files_from_seeds(self) -> None:
        """Ziarna Matta są czytane w momencie reloadu — treść trafia 1:1."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)

            sync(workspace, KIT_ROOT)

            self.assertEqual(
                _read(workspace / "docs/agents/issue-tracker.md"), SEED_ISSUE_TRACKER
            )
            labels = _read(workspace / "docs/agents/triage-labels.md")
            self.assertIn("| `needs-triage`", labels)
            self.assertIn("| `wontfix`", labels)
            domain = _read(workspace / "docs/agents/domain.md")
            self.assertIn("single-context", domain)
            self.assertIn("`CONTEXT.md`", domain)
            self.assertNotIn("GLOSSARY", domain)

    def test_existing_files_are_never_overwritten(self) -> None:
        """Użytkownik może edytować docs/agents/* — setup Matta tego nie nadpisuje."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            target = workspace / "docs/agents/issue-tracker.md"
            target.parent.mkdir(parents=True)
            target.write_text("# Mój tracker\n", encoding="utf-8", newline="\n")

            sync(workspace, KIT_ROOT)

            self.assertEqual(_read(target), "# Mój tracker\n")

    def test_seed_update_reaches_new_render(self) -> None:
        """Aktualizacja skilli (nowe ziarno) zmienia render bez zmian w kicie."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            sync(workspace, KIT_ROOT)
            (workspace / "docs/agents/issue-tracker.md").unlink()

            _seeds(workspace, tracker="# Issue tracker: GitHub v2\n\nNowe ziarno.\n")
            sync(workspace, KIT_ROOT)

            self.assertIn("v2", _read(workspace / "docs/agents/issue-tracker.md"))

    def test_no_matt_skills_skips_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp, matt=False)
            sync(workspace, KIT_ROOT)
            self.assertFalse((workspace / "docs/agents").exists())
            self.assertNotIn(AGENT_SKILLS_HEADING, _read(workspace / "AGENTS.md"))

    def test_missing_seeds_skip_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp, seeds=False)
            sync(workspace, KIT_ROOT)
            self.assertFalse((workspace / "docs/agents").exists())
            # CODING_STANDARDS to nie kontrakt Matta — powstaje zawsze.
            self.assertTrue((workspace / CODING_STANDARDS_REL).is_file())

    def test_multi_context_layout_follows_context_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "CONTEXT-MAP.md").write_text("# Mapa\n", encoding="utf-8")

            sync(workspace, KIT_ROOT)

            domain = _read(workspace / "docs/agents/domain.md")
            self.assertIn("multi-context", domain)
            self.assertIn("`CONTEXT-MAP.md`", domain)
            self.assertIn("multi-context", _read(workspace / "AGENTS.md").lower())

    def test_written_files_use_lf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            sync(workspace, KIT_ROOT)
            for path in (workspace / "docs/agents").glob("*.md"):
                with self.subTest(path=path.name):
                    self.assertNotIn(b"\r\n", path.read_bytes())


class TestAgentSkillsBlock(unittest.TestCase):
    def test_block_matches_matt_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            block = agent_skills_block(workspace)
            self.assertTrue(block.startswith(AGENT_SKILLS_HEADING + "\n"))
            for needle in (
                "### Issue tracker",
                "### Triage labels",
                "### Domain docs",
                "docs/agents/issue-tracker.md",
                "docs/agents/triage-labels.md",
                "docs/agents/domain.md",
            ):
                self.assertIn(needle, block)

    def test_appends_once_when_missing(self) -> None:
        text = "# App\n\nReguły.\n"
        block = "## Agent skills\n\nTreść.\n"
        merged = merge_agent_skills(text, block)
        self.assertEqual(merged, "# App\n\nReguły.\n\n## Agent skills\n\nTreść.\n")
        self.assertEqual(merge_agent_skills(merged, block), merged)

    def test_updates_in_place_and_keeps_surrounding_sections(self) -> None:
        text = "# App\n\nWstęp.\n\n## Agent skills\n\nstara treść\n\n## Inne\n\nZostaje.\n"
        block = "## Agent skills\n\nnowa treść\n"
        merged = merge_agent_skills(text, block)
        self.assertNotIn("stara treść", merged)
        self.assertIn("## Inne\n\nZostaje.", merged)
        self.assertEqual(merged.count(AGENT_SKILLS_HEADING), 1)


class TestCodingStandards(unittest.TestCase):
    def test_lists_only_sources_that_exist_in_priority_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "AGENTS.md").write_text("# App\n", encoding="utf-8")

            text = coding_standards(workspace)

            self.assertIn("`AGENTS.md`", text)
            for absent in (".ai/project.md", "`BUGBOT.md`", "`docs/adr/`", "`CONTEXT.md`"):
                self.assertNotIn(absent, text)
            self.assertIn("project-guides", text)

            (workspace / ".ai").mkdir()
            (workspace / ".ai" / "project.md").write_text("overlay\n", encoding="utf-8")
            (workspace / "BUGBOT.md").write_text("# Bugbot\n", encoding="utf-8")
            (workspace / "docs" / "adr").mkdir(parents=True)
            (workspace / "docs" / "adr" / "0001-x.md").write_text("# ADR\n", encoding="utf-8")
            (workspace / "CONTEXT.md").write_text("# Słownik\n", encoding="utf-8")

            text = coding_standards(workspace)
            order = [
                text.index("`AGENTS.md`"),
                text.index("`.ai/project.md`"),
                text.index("`BUGBOT.md`"),
                text.index("`docs/adr/`"),
                text.index("`CONTEXT.md`"),
                text.index("project-guides"),
            ]
            self.assertEqual(order, sorted(order))

    def test_reload_refreshes_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp, matt=False, seeds=False)
            target = workspace / CODING_STANDARDS_REL
            target.write_text("stary indeks\n", encoding="utf-8", newline="\n")

            sync(workspace, KIT_ROOT)

            self.assertNotIn("stary indeks", _read(target))


class TestRemove(unittest.TestCase):
    def test_removes_only_pristine_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            sync(workspace, KIT_ROOT)
            edited = workspace / "docs/agents/domain.md"
            edited.write_text("# Mój domain\n", encoding="utf-8", newline="\n")
            standards = workspace / CODING_STANDARDS_REL
            standards.write_text("moje standardy\n", encoding="utf-8", newline="\n")

            remove(workspace, KIT_ROOT)

            self.assertFalse((workspace / "docs/agents/issue-tracker.md").exists())
            self.assertFalse((workspace / "docs/agents/triage-labels.md").exists())
            self.assertTrue(edited.is_file())
            self.assertTrue(standards.is_file())
            self.assertNotIn(AGENT_SKILLS_HEADING, _read(workspace / "AGENTS.md"))

    def test_removes_pristine_contract_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            sync(workspace, KIT_ROOT)

            remove(workspace, KIT_ROOT)

            self.assertFalse((workspace / "docs/agents").exists())
            self.assertFalse((workspace / CODING_STANDARDS_REL).exists())
            self.assertEqual(_read(workspace / "AGENTS.md"), "# App\n\nReguły projektu.\n")


class TestReviewAgents(unittest.TestCase):
    """`/review-*` biorą źródła standardów z jednego indeksu, nie z wyliczanki w każdym agencie."""

    def test_every_review_agent_reads_coding_standards(self) -> None:
        agents = sorted((KIT_ROOT / "templates/shared/agents").glob("review-*.md"))
        self.assertTrue(agents)
        for agent in agents:
            with self.subTest(agent=agent.name):
                self.assertIn("`CODING_STANDARDS.md`", _read(agent))

    def test_backend_and_frontend_do_not_keep_their_own_source_list(self) -> None:
        for name in ("review-backend.md", "review-frontend.md"):
            text = _read(KIT_ROOT / "templates/shared/agents" / name)
            with self.subTest(agent=name):
                self.assertNotIn("`.cursor/BUGBOT.md` — tylko żeby uniknąć overlapu", text)
                self.assertIn("`CODING_STANDARDS.md` — przeczytaj wskazane źródła", text)


class TestBootstrapReload(unittest.TestCase):
    """Reload (prawdziwy ``bootstrap-project.sh``) tworzy i utrzymuje kontrakt."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI — kontrakt Matta musi się wykonać")
            self.skipTest("brak bash / Git for Windows w PATH")
        config_home = tempfile.TemporaryDirectory()
        self.addCleanup(config_home.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config_home.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _install(self, workspace: Path, *, remove: bool = False) -> None:
        run_bootstrap(
            target=workspace, kit_root=KIT_ROOT, clients="claude", remove=remove
        )

    def test_reload_creates_contract_files_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)

            self._install(workspace)

            for rel in ("issue-tracker.md", "triage-labels.md", "domain.md"):
                path = workspace / "docs/agents" / rel
                self.assertTrue(path.is_file(), rel)
                self.assertNotIn(b"\r\n", path.read_bytes(), rel)
            self.assertIn(AGENT_SKILLS_HEADING, _read(workspace / "AGENTS.md"))
            standards = _read(workspace / CODING_STANDARDS_REL)
            self.assertIn("`AGENTS.md`", standards)
            self.assertIn("`BUGBOT.md`", standards)
            self.assertNotIn(b"\r\n", (workspace / CODING_STANDARDS_REL).read_bytes())

    def test_reload_keeps_edited_docs_and_refreshes_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            self._install(workspace)
            edited = workspace / "docs/agents/issue-tracker.md"
            edited.write_text("# Własny tracker\n", encoding="utf-8", newline="\n")
            standards = workspace / CODING_STANDARDS_REL
            standards.write_text("stary indeks\n", encoding="utf-8", newline="\n")
            (workspace / "docs/agents/triage-labels.md").unlink()
            _seeds(workspace, triage=SEED_TRIAGE.replace("evaluate", "ocena"))

            self._install(workspace)

            self.assertEqual(_read(edited), "# Własny tracker\n")
            self.assertIn("ocena", _read(workspace / "docs/agents/triage-labels.md"))
            self.assertNotIn("stary indeks", _read(standards))

    def test_reload_without_matt_skills_creates_no_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "AGENTS.md").write_text("# App\n", encoding="utf-8")

            self._install(workspace)

            self.assertFalse((workspace / "docs/agents").exists())
            self.assertTrue((workspace / CODING_STANDARDS_REL).is_file())

    def test_remove_drops_pristine_contract_but_keeps_edited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            self._install(workspace)
            edited = workspace / "docs/agents/domain.md"
            edited.write_text("# Mój domain\n", encoding="utf-8", newline="\n")

            self._install(workspace, remove=True)

            self.assertFalse((workspace / "docs/agents/issue-tracker.md").exists())
            self.assertFalse((workspace / "docs/agents/triage-labels.md").exists())
            self.assertTrue(edited.is_file())
            self.assertFalse((workspace / CODING_STANDARDS_REL).exists())
            agents = _read(workspace / "AGENTS.md")
            self.assertNotIn(AGENT_SKILLS_HEADING, agents)
            self.assertIn("# App", agents)

    def test_dry_run_lists_contract_files_without_touching_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            before = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file()
            }

            plan = plan_bootstrap(
                workspace_root=workspace, kit_root=KIT_ROOT, clients="claude"
            )

            self.assertIn(CODING_STANDARDS_REL, plan.created)
            self.assertIn("docs/agents/issue-tracker.md", plan.created)
            self.assertIn("docs/agents/triage-labels.md", plan.created)
            self.assertIn("docs/agents/domain.md", plan.created)
            after = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
