"""Reguły frontendu (tokeny, sekcja/strona) i spec layoutu `docs/design/<N>.md` (#188)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.manifest import load_manifest
from guides.questions import active_questions
from guides.resolver import resolve_workspace_profile

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"
MODULE_ID = "stack:frontend:ui-structure"
DESIGN_TOOLS = ("Claude Design", "claude.ai/design", "/design-sync", "Figma", "Penpot", "Sketch")


def _bundle_ids(**tiers: str) -> set[str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".ai").mkdir()
        profile = "".join(f"{t}: {tiers.get(t, 'none')}\n" for t in ("backend", "web", "mobile"))
        (root / ".ai" / "project.profile.yaml").write_text(profile, encoding="utf-8")
        resolved = resolve_workspace_profile(root, kit_root=KIT_ROOT)
    return {mid for bundle in resolved.bundles.values() for mid in bundle.module_ids}


class TestUiStructureModule(unittest.TestCase):
    def test_in_bundle_for_web_and_mobile_only(self) -> None:
        self.assertIn(MODULE_ID, _bundle_ids(web="react"))
        self.assertIn(MODULE_ID, _bundle_ids(web="angular"))
        self.assertIn(MODULE_ID, _bundle_ids(mobile="expo"))
        self.assertIn(MODULE_ID, _bundle_ids(mobile="react-native"))
        self.assertNotIn(MODULE_ID, _bundle_ids(backend="django"))
        self.assertNotIn(MODULE_ID, _bundle_ids())

    def test_content_rules_and_spec_format(self) -> None:
        text = load_manifest(KIT_ROOT).modules[MODULE_ID].path.read_text(encoding="utf-8")
        for needle in (
            "Tylko tokeny",
            "Sekcja / strona",
            "Layout domyślny",
            "docs/design/<N>.md",
            "## Breakpointy",
            "## Sekcje (kolejność i położenie)",
            "## Nowe / zmienione tokeny",
            "design-tokens",
            "docs(design): layout spec for #<N>",
        ):
            self.assertIn(needle, text)
        for tool in DESIGN_TOOLS:
            self.assertNotIn(tool, text)


class TestDesignQuestions(unittest.TestCase):
    def _active(self, **tiers: str) -> set[str]:
        values = {t: tiers.get(t, "none") for t in ("backend", "web", "mobile")}
        values["codegen"] = "none"
        return {q.question_id for q in active_questions(load_manifest(KIT_ROOT), values)}

    def test_questions_depend_on_tiers(self) -> None:
        self.assertLessEqual({"design-tokens", "routes-web"}, self._active(web="react"))
        self.assertNotIn("routes-mobile", self._active(web="react"))
        self.assertLessEqual({"design-tokens", "routes-mobile"}, self._active(mobile="expo"))
        self.assertNotIn("routes-web", self._active(mobile="expo"))
        self.assertFalse({"design-tokens", "routes-web", "routes-mobile"} & self._active())

    def test_answers_go_to_paths_section(self) -> None:
        questions = load_manifest(KIT_ROOT).questions
        for qid in ("design-tokens", "routes-web", "routes-mobile"):
            self.assertEqual(questions[qid].sets, f"paths.{qid}")


class TestAgentsUseDesignSpec(unittest.TestCase):
    def test_night_run_ticket_prompt_and_report(self) -> None:
        text = (AGENTS / "night-run.md").read_text(encoding="utf-8")
        prompt = text[text.index("## Prompt ticketu") : text.index("## Testy — piramida")]
        self.assertIn("docs/design/<N>.md", prompt)
        self.assertIn("Nowe ekrany", text[text.index("## NIGHT-RUN REPORT") :])

    def test_review_frontend_checks_rules(self) -> None:
        text = (AGENTS / "review-frontend.md").read_text(encoding="utf-8")
        for needle in ("token", "route", "docs/design/<N>.md"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
