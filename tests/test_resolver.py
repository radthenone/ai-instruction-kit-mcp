"""Testy resolvera profili instruction-kit."""

from __future__ import annotations

import unittest
from pathlib import Path

from guides.resolver import resolve_profile

KIT_ROOT = Path(__file__).resolve().parents[1]


class TestResolver(unittest.TestCase):
    """Weryfikacja składania profili i bundle'ów."""

    def test_olivin_profile_no_missing_modules(self) -> None:
        """Profil olivin-app nie powinien mieć brakujących modułów w bundle'ach."""
        profile_path = KIT_ROOT / "profiles" / "olivin-app.yaml"
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
        profile_path = KIT_ROOT / "profiles" / "olivin-app.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)
        enabled = set(resolved.enabled_module_ids)

        self.assertIn("core:typing-python", enabled)
        self.assertIn("core:typing-typescript", enabled)
        self.assertIn("stack:expo-router:mobile-native", enabled)
        self.assertIn("pattern:capability-provider", enabled)

    def test_architecture_bundle_has_capability_provider(self) -> None:
        """Bundle architecture zawiera pełną spec capability-provider."""
        profile_path = KIT_ROOT / "profiles" / "olivin-app.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)
        arch = resolved.bundles["architecture"]

        self.assertIn("pattern:capability-provider", arch.module_ids)

    def test_base_extends_merges_patterns(self) -> None:
        """Preset _base.yaml dostarcza patterns przez extends."""
        profile_path = KIT_ROOT / "profiles" / "olivin-app.yaml"
        resolved = resolve_profile(profile_path, kit_root=KIT_ROOT)

        self.assertIn("pattern:providers-and-settings", resolved.enabled_module_ids)


if __name__ == "__main__":
    unittest.main()
