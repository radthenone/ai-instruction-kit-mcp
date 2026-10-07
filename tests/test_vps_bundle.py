"""Testy doklejania modułu VPS do bundle'i (issue #152)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.host_profile import VPS_LIGHTWEIGHT_MODULE
from guides.manifest import load_manifest
from guides.resolver import resolve_profile

KIT_ROOT = Path(__file__).resolve().parents[1]


def _profile_path(body: str, tmpdir: str) -> Path:
    workspace = Path(tmpdir) / "ws"
    ai_dir = workspace / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    path = ai_dir / "project.profile.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class TestVpsBundle(unittest.TestCase):
    def test_vps_adds_module_to_all_bundles(self) -> None:
        manifest = load_manifest(KIT_ROOT)
        self.assertIn(VPS_LIGHTWEIGHT_MODULE, manifest.modules)
        with tempfile.TemporaryDirectory() as tmp:
            path = _profile_path("name: t\nbackend: none\nweb: none\nmobile: none\n", tmp)
            resolved = resolve_profile(
                path,
                kit_root=KIT_ROOT,
                workspace_root=Path(tmp) / "ws",
                host_profile="vps",
            )
        self.assertIn(VPS_LIGHTWEIGHT_MODULE, resolved.enabled_module_ids)
        for bundle in resolved.bundles.values():
            with self.subTest(bundle=bundle.name):
                self.assertIn(VPS_LIGHTWEIGHT_MODULE, bundle.module_ids)
                self.assertIn("lekki tryb", bundle.content.lower())
        self.assertIn("- Host: `vps`", resolved.index_markdown)

    def test_local_has_no_vps_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _profile_path("name: t\nbackend: none\nweb: none\nmobile: none\n", tmp)
            resolved = resolve_profile(
                path,
                kit_root=KIT_ROOT,
                workspace_root=Path(tmp) / "ws",
                host_profile="local",
            )
        self.assertNotIn(VPS_LIGHTWEIGHT_MODULE, resolved.enabled_module_ids)
        for bundle in resolved.bundles.values():
            with self.subTest(bundle=bundle.name):
                self.assertNotIn(VPS_LIGHTWEIGHT_MODULE, bundle.module_ids)

    def test_vps_module_has_no_stack_assumptions(self) -> None:
        text = (KIT_ROOT / "modules" / "infra" / "vps-lightweight.md").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("docker compose", lowered)
        self.assertIn("lint", lowered)
        self.assertIn("ci", lowered)
        for stack in ("django", "fastapi", "flask", "angular", "react", "expo"):
            self.assertNotIn(stack, lowered)


if __name__ == "__main__":
    unittest.main()
