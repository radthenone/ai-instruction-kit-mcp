"""Testy katalogu pytań (`questions:` / `layouts:` w manifeście) i narzędzia `list_questions`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides import server
from guides.manifest import load_manifest
from guides.questions import active_questions, layout_hint, render_catalog
from guides.resolver import resolve_workspace_profile

KIT_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_MODULES = {
    "stack:frontend:expo-unified",
    "stack:frontend:expo-web",
    "stack:frontend:react-expo-split",
    "stack:frontend:react-native-split",
    "stack:frontend:react-web",
}


def _values(backend: str = "none", web: str = "none", mobile: str = "none") -> dict[str, str]:
    return {"backend": backend, "web": web, "mobile": mobile}


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(KIT_ROOT)

    def _active(self, **tiers: str) -> set[str]:
        return {q.question_id for q in active_questions(self.manifest, _values(**tiers))}

    def test_catalog_loads_from_manifest(self) -> None:
        questions = self.manifest.questions
        for qid in ("backend", "web", "mobile", "codegen", "docker", "taskfile", "ci-cd",
                    "monorepo", "capability-provider", "webhooks", "paths-backend"):
            self.assertIn(qid, questions)
        self.assertIn("fastapi", questions["backend"].options)
        self.assertIn("none", questions["web"].options)
        self.assertTrue(any(s.glob == "manage.py" and s.value == "django"
                            for s in questions["backend"].detect))
        self.assertTrue(any(s.glob == "angular.json" for s in questions["web"].detect))

    def test_references_point_at_known_ids(self) -> None:
        """Każdy Module ID / Pattern / opcja Tieru z katalogu istnieje (literówka = test, nie runtime)."""
        mappings = self.manifest.mappings
        for question in self.manifest.questions.values():
            for module_id in question.on_yes.get("include", ()):
                self.assertIn(module_id, self.manifest.modules, question.question_id)
            for pattern in question.on_yes.get("patterns", ()):
                self.assertIn(pattern, mappings.patterns, question.question_id)
            if question.sets in mappings.tiers:
                for option in question.options:
                    self.assertTrue(option == "none" or option in mappings.tiers[question.sets],
                                    f"{question.question_id}: {option}")
            if question.options:
                self.assertIn(question.default, question.options, question.question_id)
        for hint in self.manifest.layouts:
            if hint.module:
                self.assertIn(hint.module, self.manifest.modules)

    def test_codegen_only_with_backend_and_client(self) -> None:
        self.assertNotIn("codegen", self._active(backend="fastapi"))
        self.assertNotIn("codegen", self._active(web="react"))
        self.assertIn("codegen", self._active(backend="fastapi", mobile="expo"))
        self.assertIn("codegen", self._active(backend="django", web="react"))

    def test_django_html_defaults_clients_to_none(self) -> None:
        web = self.manifest.questions["web"]
        self.assertEqual(web.default_for(_values(backend="django-html")), "none")
        self.assertEqual(web.default_for(_values(backend="django")), "react")
        self.assertEqual(self.manifest.questions["mobile"].default_for(_values(backend="django-html")), "none")

    def test_variant_and_path_questions_follow_tiers(self) -> None:
        self.assertIn("web-variant-react", self._active(web="react@legacy"))
        self.assertNotIn("web-variant-angular", self._active(web="react"))
        self.assertEqual(self._active() & {"paths-backend", "paths-web", "paths-mobile"}, set())
        unified = _values(web="expo", mobile="expo")
        self.assertEqual(self.manifest.questions["paths-web"].default_for(unified), "frontend/")
        self.assertEqual(self.manifest.questions["paths-web"].default_for(_values(web="react")),
                         "frontend/web/")

    def test_layout_hints(self) -> None:
        hint = layout_hint(self.manifest, _values(web="react", mobile="expo"))
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(hint.module, "stack:frontend:react-expo-split")
        warning = layout_hint(self.manifest, _values(web="expo", mobile="react-native"))
        assert warning is not None
        self.assertIn("react-native", warning.warning or "")
        self.assertIsNone(layout_hint(self.manifest, _values(backend="django")))

    def test_render_includes_layout_tree_and_skipped(self) -> None:
        out = render_catalog(self.manifest, {**_values(web="react", mobile="expo"), "codegen": "none"})
        self.assertIn("stack:frontend:react-expo-split", out)
        self.assertIn("packages/", out)
        self.assertIn("`codegen`", out.split("## Pominięte")[1])


class TestLayoutModulesLeftBundles(unittest.TestCase):
    def test_layout_modules_never_reach_bundles(self) -> None:
        combos = [("none", "react", "none"), ("none", "react", "expo"), ("none", "expo", "expo"),
                  ("none", "react", "react-native"), ("django", "expo", "none")]
        for backend, web, mobile in combos:
            with self.subTest(web=web, mobile=mobile), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / ".ai").mkdir()
                (workspace / ".ai" / "project.profile.yaml").write_text(
                    f"name: t\nbackend: {backend}\nweb: {web}\nmobile: {mobile}\n", encoding="utf-8"
                )
                resolved = resolve_workspace_profile(workspace, KIT_ROOT)
                for bundle in resolved.bundles.values():
                    self.assertEqual(set(bundle.module_ids) & LAYOUT_MODULES, set(), bundle.name)


class TestListQuestionsTool(unittest.TestCase):
    def _call(self, profile: str) -> str:
        saved = (server._kit_root, server._workspace_root)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".ai").mkdir()
            (workspace / ".ai" / "project.profile.yaml").write_text(profile, encoding="utf-8")
            server._kit_root, server._workspace_root = KIT_ROOT, workspace
            try:
                return server.list_questions()
            finally:
                server._kit_root, server._workspace_root = saved

    def test_backend_only_has_no_codegen_question(self) -> None:
        out = self._call("name: t\nbackend: fastapi\nweb: none\n")
        active = out.split("## Pominięte")[0]
        self.assertNotIn("`codegen`", active)
        self.assertIn("`paths-backend`", active)

    def test_react_expo_gets_split_layout(self) -> None:
        out = self._call("name: t\nweb: react\nmobile: expo\n")
        self.assertIn("stack:frontend:react-expo-split", out)


if __name__ == "__main__":
    unittest.main()
