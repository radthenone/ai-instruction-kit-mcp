"""Etykiety kita: zestaw `labels.tsv` i provisioning brakujących przez `gh` (#187)."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from guides import server
from guides.labels import (
    LABELS_REL_PATH,
    STATE_LABELS,
    LabelsError,
    ensure_labels,
    read_label_set,
    triage_names,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"
TIERS = {"backend", "web", "mobile"}

# Tabela 1a z #187 — niezależne źródło prawdy dla testu mapowania.
CATEGORY = {
    "type: fix": "bug",
    "type: security": "bug",
    "type: feature": "enhancement",
    "type: performance": "enhancement",
    "type: refactor": None,
    "type: docs": None,
    "type: test": None,
    "type: style": None,
    "type: chore": None,
}


class FakeGh:
    """Atrapa `gh`: zwraca listę etykiet i zapisuje każde wywołanie."""

    def __init__(
        self, existing: list[str], *, fail: str | None = None, missing: bool = False,
        hang: bool = False,
    ):
        self.existing = existing
        self.fail = fail
        self.missing = missing
        self.hang = hang
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        if self.missing:
            raise FileNotFoundError("gh")
        if self.hang:
            raise subprocess.TimeoutExpired(args, 30)
        self.calls.append(args)
        if self.fail:
            return subprocess.CompletedProcess(args, 1, "", self.fail)
        if args[:3] == ["gh", "label", "list"]:
            out = json.dumps([{"name": n} for n in self.existing])
            return subprocess.CompletedProcess(args, 0, out, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    def created(self) -> list[str]:
        return [c[3] for c in self.calls if c[:3] == ["gh", "label", "create"]]


def _workspace(root: Path, *, triage: str | None = None, **tiers: str) -> Path:
    lines = [f"{tier}: {tiers.get(tier, 'none')}" for tier in ("backend", "web", "mobile")]
    (root / ".ai").mkdir()
    (root / ".ai" / "project.profile.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if triage is not None:
        (root / "docs" / "agents").mkdir(parents=True)
        (root / "docs" / "agents" / "triage-labels.md").write_text(triage, encoding="utf-8")
    return root


class TestLabelSet(unittest.TestCase):
    def test_rows_are_well_formed(self) -> None:
        rows = (KIT_ROOT / LABELS_REL_PATH).read_text(encoding="utf-8").splitlines()
        names = set()
        for row in rows:
            cols = row.split("\t")
            self.assertEqual(len(cols), 4, row)
            name, color, _description, when = cols
            self.assertRegex(color, r"^[0-9A-F]{6}$", row)
            self.assertTrue(when == "always" or set(when.split(",")) <= TIERS, row)
            self.assertNotIn(name.lower(), names, row)
            names.add(name.lower())

    def test_state_labels_match_kit_triage_doc(self) -> None:
        state = {label.name for label in read_label_set(KIT_ROOT) if label.name in STATE_LABELS}
        self.assertEqual(state, set(triage_names(KIT_ROOT).values()))
        self.assertEqual(set(STATE_LABELS), set(triage_names(KIT_ROOT)))

    def test_triage_labels_doc_describes_needs_local(self) -> None:
        """Dokumentacja etykiet opisuje `needs-local`, warunek wykonania i sposób zdjęcia."""
        doc = (KIT_ROOT / "docs" / "agents" / "triage-labels.md").read_text(encoding="utf-8")
        self.assertIn("needs-local", doc)
        self.assertIn("ready-for-agent", doc)
        self.assertNotIn("| `needs-local`", doc)
        self.assertTrue(
            "warunek wykonania" in doc.lower() or "execution condition" in doc.lower(),
            "brak wzmianki, że to warunek wykonania / execution condition",
        )
        self.assertTrue(
            "zdjąć" in doc.lower() or "remove" in doc.lower(),
            "brak opisu zdjęcia etykiety przez użytkownika",
        )

    def test_every_type_has_category_row(self) -> None:
        names = {label.name for label in read_label_set(KIT_ROOT)}
        self.assertEqual({n for n in names if n.startswith("type: ")}, set(CATEGORY))
        self.assertLessEqual({"bug", "enhancement"}, names)

    def test_agents_map_type_to_category(self) -> None:
        names = {label.name for label in read_label_set(KIT_ROOT)}
        for agent in ("create-task.md", "git-start.md", "git-end.md"):
            text = (AGENTS / agent).read_text(encoding="utf-8")
            for type_label, category in CATEGORY.items():
                if category:
                    self.assertRegex(text, rf"`{type_label}`[^\n]*`{category}`", agent)
            for used in set(re.findall(r"`(type: [a-z]+)`", text)):
                self.assertIn(used, names, f"{agent}: {used} spoza labels.tsv")
            self.assertIn("scope:", text, agent)


class TestAgentsUseLabels(unittest.TestCase):
    def _text(self, name: str) -> str:
        return (AGENTS / name).read_text(encoding="utf-8")

    def test_create_task_readiness_block(self) -> None:
        text = self._text("create-task.md")
        self.assertIn("## Gotowość", text)
        self.assertIn("ready-for-agent | ready-for-human | needs-info", text)
        self.assertNotIn("może nie być; sprawdzaj, nie zakładaj", text)
        self.assertIn("kit-ai labels --apply", text)

    def test_night_run_queue_and_hand_back(self) -> None:
        text = self._text("night-run.md")
        self.assertIn("--label ready-for-agent", text)
        self.assertIn("--remove-label ready-for-agent --add-label ready-for-human", text)
        self.assertIn("nazwy z `triage-labels.md` projektu, nie dosłownie", text)
        self.assertIn("skipped: <etykieta>", text)
        self.assertIn("AGENT-BRIEF", text)

    def test_kit_project_agents_offer_provisioning(self) -> None:
        for name in ("kit-project-begin.md", "kit-project-edit.md"):
            text = self._text(name)
            self.assertIn("ensure_labels(dry_run=True)", text, name)
            self.assertIn("kit-ai labels --apply", text, name)


class TestEnsureLabels(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_dry_run_plans_only_missing_and_never_creates(self) -> None:
        ws = _workspace(self.root, backend="django")
        gh = FakeGh(["Type: Feature", "bug"])
        report = ensure_labels(ws, KIT_ROOT, dry_run=True, run=gh)
        self.assertEqual(gh.created(), [])
        self.assertNotIn("+ type: feature", report)
        self.assertNotIn("+ bug", report)
        self.assertIn("+ scope: backend", report)
        self.assertIn("existing: 2", report)
        self.assertIn("to create:", report)

    def test_apply_creates_missing_without_force(self) -> None:
        ws = _workspace(self.root, backend="django")
        gh = FakeGh(["type: feature"])
        report = ensure_labels(ws, KIT_ROOT, dry_run=False, run=gh)
        created = gh.created()
        self.assertIn("scope: backend", created)
        self.assertNotIn("type: feature", created)
        self.assertTrue(all("--force" not in c for c in gh.calls))
        self.assertIn(f"created: {len(created)}", report)

    def test_needs_local_is_always_provisioned(self) -> None:
        """`needs-local` (warunek wykonania, nie stan triage) wchodzi nawet przy Tierach none."""
        ws = _workspace(self.root)
        gh = FakeGh([])
        report = ensure_labels(ws, KIT_ROOT, dry_run=True, run=gh)
        self.assertIn("+ needs-local", report)
        self.assertEqual(gh.created(), [])

    def test_tier_none_skips_scope(self) -> None:
        ws = _workspace(self.root, web="react")
        gh = FakeGh([])
        report = ensure_labels(ws, KIT_ROOT, dry_run=False, run=gh)
        self.assertIn("scope: frontend:web", gh.created())
        self.assertNotIn("scope: frontend:mobile", gh.created())
        self.assertNotIn("scope: backend", gh.created())
        self.assertIn("skipped (Tier none / bez claude): 2", report)

    def test_when_list_matches_any_tier(self) -> None:
        ws = _workspace(self.root, mobile="expo")
        tsv = self.root / "kit" / LABELS_REL_PATH
        tsv.parent.mkdir(parents=True)
        tsv.write_text("x: both\t000000\td\tweb,mobile\n", encoding="utf-8")
        gh = FakeGh([])
        tiers = {"backend": "none", "web": "none", "mobile": "expo"}
        ensure_labels(ws, self.root / "kit", dry_run=False, run=gh, tiers=tiers)
        self.assertEqual(gh.created(), ["x: both"])

    def test_project_triage_mapping_renames_state_labels(self) -> None:
        doc = (
            "| Label in mattpocock/skills | Label in our tracker | Meaning |\n"
            "| --- | --- | --- |\n"
            "| `ready-for-agent` | `agent:ready` | x |\n"
        )
        ws = _workspace(self.root, triage=doc)
        gh = FakeGh([])
        ensure_labels(ws, KIT_ROOT, dry_run=False, run=gh)
        self.assertIn("agent:ready", gh.created())
        self.assertNotIn("ready-for-agent", gh.created())
        self.assertIn("ready-for-human", gh.created())
        call = next(c for c in gh.calls if c[3:4] == ["agent:ready"])
        self.assertIn("7057FF", call)

    def test_gh_missing_failing_or_hanging_raises_one_line(self) -> None:
        ws = _workspace(self.root)
        for gh in (
            FakeGh([], missing=True),
            FakeGh([], fail="gh auth login\nmore"),
            FakeGh([], hang=True),
        ):
            with self.assertRaises(LabelsError) as ctx:
                ensure_labels(ws, KIT_ROOT, dry_run=False, run=gh)
            self.assertEqual(len(str(ctx.exception).strip().splitlines()), 1)

    def test_when_tolerates_spaces(self) -> None:
        ws = _workspace(self.root, mobile="expo")
        tsv = self.root / "kit" / LABELS_REL_PATH
        tsv.parent.mkdir(parents=True)
        tsv.write_text("x: both\t000000\td\tweb, mobile\n", encoding="utf-8")
        gh = FakeGh([])
        tiers = {"backend": "none", "web": "none", "mobile": "expo"}
        ensure_labels(ws, self.root / "kit", dry_run=False, run=gh, tiers=tiers)
        self.assertEqual(gh.created(), ["x: both"])


class TestMcpEnsureLabels(unittest.TestCase):
    def test_default_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _workspace(Path(tmp))
            gh = FakeGh([])
            saved = (server._kit_root, server._workspace_root, server._gh_runner)
            server._kit_root, server._workspace_root, server._gh_runner = KIT_ROOT, ws, gh
            try:
                report = server.ensure_labels()
            finally:
                server._kit_root, server._workspace_root, server._gh_runner = saved
            self.assertEqual(gh.created(), [])
            self.assertIn("dry_run=False", report)

    def test_errors_are_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _workspace(Path(tmp))
            saved = (server._kit_root, server._workspace_root, server._gh_runner)
            server._kit_root, server._workspace_root = KIT_ROOT, ws
            server._gh_runner = FakeGh([], missing=True)
            try:
                report = server.ensure_labels()
            finally:
                server._kit_root, server._workspace_root, server._gh_runner = saved
            self.assertIn("ensure_labels: błąd", report)


class TestCliLabels(unittest.TestCase):
    def test_dry_run_unless_apply(self) -> None:
        from unittest import mock

        from guides import cli

        for argv, dry in ((["labels", "."], True), (["labels", ".", "--apply"], False)):
            with mock.patch.object(cli, "ensure_labels", return_value="ok") as fake:
                self.assertEqual(cli.main(argv), 0)
            self.assertEqual(fake.call_args.kwargs["dry_run"], dry)

    def test_gh_error_exits_non_zero(self) -> None:
        from unittest import mock

        from guides import cli
        from guides.labels import LabelsError

        with mock.patch.object(cli, "ensure_labels", side_effect=LabelsError("labels: brak `gh`")):
            self.assertEqual(cli.main(["labels", "."]), 1)


if __name__ == "__main__":
    unittest.main()
