"""Testy resolvera profili instruction-kit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.resolver import normalize_language, resolve_preset_path, resolve_profile

KIT_ROOT = Path(__file__).resolve().parents[1]


class TestResolver(unittest.TestCase):
    """Weryfikacja składania profili i bundle'ów."""

    def test_shop_profile_no_missing_modules(self) -> None:
        """Kategoria shop nie powinna mieć brakujących modułów w bundle'ach."""
        profile_path = KIT_ROOT / "profiles" / "shop.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)

        for bundle_name, bundle in resolved.bundles.items():
            with self.subTest(bundle=bundle_name):
                self.assertEqual(
                    bundle.missing_modules,
                    (),
                    msg=f"Bundle {bundle_name} ma brakujące moduły: {bundle.missing_modules}",
                )

    def test_enabled_modules_include_bundle_defaults(self) -> None:
        """Indeks profilu zawiera moduły z default bundle'ów (typing, mobile-native)."""
        profile_path = KIT_ROOT / "profiles" / "shop.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)
        enabled = set(resolved.enabled_module_ids)

        self.assertIn("core:typing-python", enabled)
        self.assertIn("core:typing-typescript", enabled)
        self.assertIn("stack:expo-router:mobile-native", enabled)
        self.assertIn("pattern:capability-provider", enabled)

    def test_architecture_bundle_has_capability_provider(self) -> None:
        """Bundle architecture zawiera pełną spec capability-provider."""
        profile_path = KIT_ROOT / "profiles" / "shop.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)
        arch = resolved.bundles["architecture"]

        self.assertIn("pattern:capability-provider", arch.module_ids)

    def test_base_extends_merges_patterns(self) -> None:
        """Preset _base.yaml dostarcza patterns przez extends."""
        profile_path = KIT_ROOT / "profiles" / "shop.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)

        self.assertIn("pattern:providers-and-settings", resolved.enabled_module_ids)

    def test_resolve_preset_path_shop(self) -> None:
        """resolve_preset_path znajduje profiles/shop.yaml."""
        path = resolve_preset_path("shop", KIT_ROOT)
        self.assertEqual(path, (KIT_ROOT / "profiles" / "shop.yaml").resolve())

    def test_preset_with_workspace_overlay(self) -> None:
        """Preset + workspace ładuje .ai/project.md bez lokalnego project.profile.yaml."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            ai_dir = workspace / ".ai"
            ai_dir.mkdir()
            (ai_dir / "project.md").write_text("# Overlay test\n\nport: 9999\n", encoding="utf-8")

            profile_path = resolve_preset_path("shop", KIT_ROOT)
            resolved = resolve_profile(
                profile_path,
                kit_root=KIT_ROOT,
                workspace_root=workspace,
            )

            self.assertEqual(resolved.workspace_root, workspace.resolve())
            self.assertIn("Overlay test", resolved.overlay_content)
            self.assertIn("9999", resolved.overlay_content)

    def test_extra_overlays_cli(self) -> None:
        """Dodatkowe --overlay trafiają do overlay_content."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            extra = workspace / "extra.md"
            extra.write_text("# Extra overlay\n", encoding="utf-8")
            profile_path = resolve_preset_path("shop", KIT_ROOT)
            resolved = resolve_profile(
                profile_path,
                kit_root=KIT_ROOT,
                workspace_root=workspace,
                extra_overlays=[extra],
            )
            self.assertIn("Extra overlay", resolved.overlay_content)

    def test_default_language_pl_module(self) -> None:
        """Domyślny język profilu to pl i moduł core:language-pl."""
        resolved = resolve_profile(
            resolve_preset_path("shop", KIT_ROOT), kit_root=KIT_ROOT
        )
        self.assertEqual(resolved.language, "pl")
        self.assertIn("core:language-pl", resolved.enabled_module_ids)
        self.assertNotIn("core:language-en", resolved.enabled_module_ids)
        self.assertIn("core:language-pl", resolved.bundles["backend"].module_ids)

    def test_language_override_en_swaps_module(self) -> None:
        """language_override=en zamienia language-pl na language-en we wszystkich bundle'ach."""
        resolved = resolve_profile(
            resolve_preset_path("shop", KIT_ROOT),
            kit_root=KIT_ROOT,
            language_override="EN",
        )
        self.assertEqual(resolved.language, "en")
        self.assertIn("core:language-en", resolved.enabled_module_ids)
        self.assertNotIn("core:language-pl", resolved.enabled_module_ids)
        for name, bundle in resolved.bundles.items():
            with self.subTest(bundle=name):
                self.assertNotIn("core:language-pl", bundle.module_ids)
                if "core:language-en" in bundle.module_ids or any(
                    mid.startswith("core:language") for mid in bundle.module_ids
                ):
                    self.assertIn("core:language-en", bundle.module_ids)

    def test_normalize_language_exact_tags(self) -> None:
        """normalize_language akceptuje tylko jawne tagi EN/PL, nie prefiksy w stylu enable."""
        cases: list[tuple[str | None, str]] = [
            (None, "pl"),
            ("", "pl"),
            ("pl", "pl"),
            ("PL", "pl"),
            ("pl-PL", "pl"),
            ("polish", "pl"),
            ("en", "en"),
            ("EN", "en"),
            ("en-US", "en"),
            ("eng", "en"),
            ("english", "en"),
            ("enable", "pl"),
            ("engine", "pl"),
            (" ent ", "pl"),
        ]
        for raw, expect in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_language(raw), expect)

    def test_files_storage_alias_in_bundle(self) -> None:
        """``capability:files-storage`` w bundle mapuje się na ``capability:files``."""
        from guides.resolver import normalize_module_id

        self.assertEqual(
            normalize_module_id("capability:files-storage"),
            "capability:files",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "fork.yaml"
            profile.write_text(
                "\n".join(
                    [
                        "name: fork-files-alias",
                        "extends: profiles/_base.yaml",
                        "bundles:",
                        "  backend:",
                        "    - capability:files-storage",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            resolved = resolve_profile(profile, kit_root=KIT_ROOT)
            backend = resolved.bundles["backend"]
            self.assertIn("capability:files", backend.module_ids)
            self.assertNotIn("capability:files-storage", backend.module_ids)
            self.assertNotIn("capability:files-storage", backend.missing_modules)
            self.assertIn("capability:files", backend.content)


if __name__ == "__main__":
    unittest.main()
