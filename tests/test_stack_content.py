"""Moduły Stacków: istnieją, trafiają do Bundle'a swojego Tieru i nie zakładają Django/Expo."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from guides.manifest import load_manifest
from guides.resolver import resolve_workspace_profile

KIT_ROOT = Path(__file__).resolve().parents[1]
TIER_BUNDLE = {"backend": "backend", "web": "frontend", "mobile": "frontend"}
# Stacki, których treść z natury mówi o Django / Expo.
OWN_WORDING = {"django", "django-html", "expo"}


class TestStackModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(KIT_ROOT)

    def _stacks(self):
        for tier, stacks in self.manifest.mappings.tiers.items():
            for stack, module_ids in stacks.items():
                yield tier, stack, module_ids

    def test_every_stack_module_exists(self) -> None:
        for tier, stack, module_ids in self._stacks():
            for module_id in module_ids:
                with self.subTest(tier=tier, stack=stack, module=module_id):
                    info = self.manifest.modules.get(module_id)
                    self.assertIsNotNone(info, "brak wpisu w `modules:`")
                    assert info is not None
                    self.assertTrue(info.path.is_file(), f"brak pliku {info.path}")

    def test_stack_modules_land_in_their_tier_bundle(self) -> None:
        for tier, stack, module_ids in self._stacks():
            if not module_ids:
                continue
            with self.subTest(tier=tier, stack=stack), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                (workspace / ".ai").mkdir()
                (workspace / ".ai" / "project.profile.yaml").write_text(
                    f"name: t\n{tier}: {stack}\n", encoding="utf-8"
                )
                resolved = resolve_workspace_profile(workspace, KIT_ROOT)
                bundle = resolved.bundles[TIER_BUNDLE[tier]]
                for module_id in module_ids:
                    self.assertIn(module_id, bundle.module_ids)
                    self.assertIn(f"<!-- module:{module_id} -->", bundle.content)

    def test_other_stacks_read_without_django_or_expo(self) -> None:
        """Instrukcje FastAPI/Flask/React/Angular/RN nie zakładają znajomości Django ani Expo."""
        for tier, stack, module_ids in self._stacks():
            if stack.split("@")[0] in OWN_WORDING:
                continue
            for module_id in module_ids:
                text = self.manifest.modules[module_id].path.read_text(encoding="utf-8")
                with self.subTest(stack=stack, module=module_id):
                    self.assertIsNone(re.search(r"\b(Django|DRF|Expo)\b", text))

    def test_stack_paths_point_at_overlay(self) -> None:
        """Ścieżki w treści z `## Ścieżki` overlayu, nie wpisane na sztywno.

        Moduły `*:layout` to podpowiedzi domyślnych ścieżek — z definicji je nazywają.
        """
        for tier, stack, module_ids in self._stacks():
            if stack.split("@")[0] in OWN_WORDING:
                continue
            for module_id in (m for m in module_ids if not m.endswith(":layout")):
                text = self.manifest.modules[module_id].path.read_text(encoding="utf-8")
                with self.subTest(stack=stack, module=module_id):
                    self.assertNotIn("](backend/", text)
                    self.assertNotRegex(text, r"(?m)^\s*(backend|frontend)/\s*$")


if __name__ == "__main__":
    unittest.main()
