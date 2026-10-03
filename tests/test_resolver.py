"""Testy resolvera profili instruction-kit (Tiery zamiast presetów)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.manifest import load_manifest
from guides.resolver import (
    MIGRATION_NOTICE,
    normalize_auth_variant,
    normalize_language,
    profile_tiers,
    resolve_profile,
    resolve_workspace_profile,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = load_manifest(KIT_ROOT)

CORE_ONLY = (
    "core:repo-first",
    "core:language-pl",
    "core:external-knowledge",
    "core:tooling-rtk",
)


def _workspace(body: str | None) -> tuple[tempfile.TemporaryDirectory, Path]:
    """Workspace z opcjonalnym `.ai/project.profile.yaml`; caller sprząta."""
    tmp = tempfile.TemporaryDirectory()
    workspace = Path(tmp.name)
    if body is not None:
        ai_dir = workspace / ".ai"
        ai_dir.mkdir()
        (ai_dir / "project.profile.yaml").write_text(body, encoding="utf-8")
    return tmp, workspace


class TestTierResolution(unittest.TestCase):
    """Profil bez wyborów daje sam core; Tiery rozwijają się z manifestu."""

    def test_empty_workspace_is_core_only(self) -> None:
        """Brak `.ai/project.profile.yaml` — sam core + ostrzeżenie o migracji."""
        tmp, workspace = _workspace(None)
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(set(resolved.enabled_module_ids), set(CORE_ONLY))
        self.assertEqual(resolved.codegen, "none")
        self.assertEqual(
            resolved.tiers, {"backend": "none", "web": "none", "mobile": "none"}
        )
        self.assertTrue(resolved.notice)
        self.assertIn("kit-ai reload", resolved.notice)
        self.assertIn("kit-ai reload", resolved.bundles["backend"].content)
        self.assertIn("kit-ai reload", resolved.index_markdown)
        for bundle in resolved.bundles.values():
            with self.subTest(bundle=bundle.name):
                self.assertEqual(set(bundle.module_ids), set(CORE_ONLY))

    def test_legacy_flags_without_profile_show_notice_once(self) -> None:
        """`--preset` (notice z serwera) + brak profilu — ostrzeżenie tylko raz."""
        tmp, workspace = _workspace(None)
        try:
            resolved = resolve_workspace_profile(
                workspace, kit_root=KIT_ROOT, notice=MIGRATION_NOTICE
            )
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.bundles["backend"].content.count(MIGRATION_NOTICE), 1)

    def test_extends_removed_preset_shows_notice(self) -> None:
        """Stary profil `extends: profiles/_base.yaml` — ostrzeżenie, nie cichy core."""
        tmp, workspace = _workspace("name: t\nextends: profiles/_base.yaml\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertIn(MIGRATION_NOTICE, resolved.bundles["backend"].content)

    def test_legacy_stacks_keep_codegen_and_contract(self) -> None:
        """Legacy `stacks:` backend + klient — codegen z profilu, nie wymuszone `none`."""
        tmp, workspace = _workspace(
            "name: t\ncodegen: orval\nstacks:\n  django-drf: '1'\n  expo-router: '1'\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.codegen, "orval")
        self.assertIn("core:typing-python", resolved.enabled_module_ids)

    def test_explicit_none_tiers_is_core_only_without_notice(self) -> None:
        """Profil z samymi `none` — core, ale bez ostrzeżenia (profil istnieje)."""
        tmp, workspace = _workspace("name: t\nbackend: none\nweb: none\nmobile: none\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(set(resolved.enabled_module_ids), set(CORE_ONLY))
        self.assertEqual(resolved.notice, "")

    def test_backend_fastapi_brings_stack_and_typing(self) -> None:
        """`backend: fastapi` — moduł Stacka + typing-python, bez TypeScript."""
        tmp, workspace = _workspace("name: t\nbackend: fastapi\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        enabled = set(resolved.enabled_module_ids)
        self.assertIn("stack:fastapi:layout", enabled)
        self.assertIn("core:typing-python", enabled)
        self.assertNotIn("core:typing-typescript", enabled)
        self.assertIn("stack:fastapi:layout", resolved.bundles["backend"].module_ids)
        self.assertNotIn(
            "stack:fastapi:layout", resolved.bundles["frontend"].module_ids
        )

    def test_web_expo_twice_lists_modules_once(self) -> None:
        """`web: expo` + `mobile: expo` — moduły expo raz (dedup)."""
        tmp, workspace = _workspace("name: t\nweb: expo\nmobile: expo\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        frontend = list(resolved.bundles["frontend"].module_ids)
        self.assertEqual(len(frontend), len(set(frontend)))
        self.assertIn("stack:expo-router:web-target", frontend)
        self.assertIn("stack:expo-router:mobile-native", frontend)
        self.assertIn("core:typing-typescript", frontend)
        self.assertNotIn("core:typing-python", frontend)

    def test_angular_with_payments_has_no_expo_stripe(self) -> None:
        """`web: angular` + payments — bez modułu expo-stripe."""
        tmp, workspace = _workspace(
            "name: t\nbackend: django\nweb: angular\ncapabilities: [payments]\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        enabled = set(resolved.enabled_module_ids)
        self.assertIn("capability:payments", enabled)
        self.assertNotIn("capability:payments:expo-stripe", enabled)
        for bundle in resolved.bundles.values():
            with self.subTest(bundle=bundle.name):
                self.assertNotIn(
                    "capability:payments:expo-stripe", bundle.module_ids
                )

    def test_expo_with_payments_adds_expo_stripe(self) -> None:
        """expo w Tierze + payments — expo-stripe doklejone (frontend/payments/full)."""
        tmp, workspace = _workspace(
            "name: t\nbackend: django\nweb: expo\ncapabilities: [payments]\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertIn(
            "capability:payments:expo-stripe", resolved.enabled_module_ids
        )
        self.assertIn(
            "capability:payments:expo-stripe",
            resolved.bundles["frontend"].module_ids,
        )
        self.assertIn(
            "capability:payments:expo-stripe",
            resolved.bundles["payments"].module_ids,
        )
        self.assertNotIn(
            "capability:payments:expo-stripe",
            resolved.bundles["backend"].module_ids,
        )

    def test_backend_only_forces_codegen_none(self) -> None:
        """Sam backend (bez klienta) — efektywny codegen `none`, brak api-contract."""
        tmp, workspace = _workspace("name: t\nbackend: flask\ncodegen: graphql\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.codegen, "none")
        self.assertNotIn("arch:api-contract", resolved.enabled_module_ids)
        self.assertNotIn(
            "arch:api-contract:graphql", resolved.enabled_module_ids
        )

    def test_backend_plus_web_enables_api_contract(self) -> None:
        """Para backend + web — moduł kontraktu API wg codegen."""
        tmp, workspace = _workspace(
            "name: t\nbackend: django\nweb: react\ncodegen: graphql\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.codegen, "graphql")
        self.assertIn(
            "arch:api-contract:graphql", resolved.bundles["architecture"].module_ids
        )

    def test_unknown_tier_value_is_reported_not_fatal(self) -> None:
        """ADR-0004: `web: vue` nie wywraca serwera — raport w indeksie, Tier = none."""
        tmp, workspace = _workspace("name: t\nweb: vue\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.unrecognised_decisions, (("web", "vue"),))
        self.assertEqual(resolved.tiers["web"], "none")
        self.assertIn("vue", resolved.index_markdown)

    def test_tier_values_are_case_insensitive(self) -> None:
        """`Web: Expo` + `BACKEND: Django` — normalizacja do małych liter."""
        tmp, workspace = _workspace("name: t\nbackend: Django\nweb: Expo\n")
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(resolved.tiers, {"backend": "django", "web": "expo", "mobile": "none"})

    def test_profile_tiers_helper(self) -> None:
        """`profile_tiers` — brak klucza to ciche none."""
        tiers, unknown = profile_tiers({}, MANIFEST.mappings)
        self.assertEqual(tiers, {"backend": "none", "web": "none", "mobile": "none"})
        self.assertEqual(unknown, ())
        tiers, unknown = profile_tiers({"web": "react@legacy"}, MANIFEST.mappings)
        self.assertEqual(tiers["web"], "react@legacy")
        self.assertEqual(unknown, ())

    def test_legacy_stacks_and_patterns_still_read(self) -> None:
        """Stare klucze `stacks:` / `patterns:` nadal włączają moduły."""
        tmp, workspace = _workspace(
            "name: t\nstacks:\n  django-drf: '1'\npatterns:\n  - webhooks\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        enabled = set(resolved.enabled_module_ids)
        self.assertIn("stack:django-drf", enabled)
        self.assertIn("stack:django-drf", resolved.bundles["backend"].module_ids)
        self.assertIn("pattern:webhooks", enabled)
        self.assertIn(
            "pattern:webhooks", resolved.bundles["architecture"].module_ids
        )

    def test_legacy_profile_bundles_fold_into_include(self) -> None:
        """Profilowe `bundles:` traktowane jak `include` (routing wg tagów)."""
        tmp, workspace = _workspace(
            "name: t\ncore: false\nbundles:\n  backend:\n    - capability:files\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertIn("capability:files", resolved.enabled_module_ids)
        self.assertIn(
            "capability:files", resolved.bundles["backend"].module_ids
        )

    def test_include_modules_route_by_tags(self) -> None:
        """`include:` trafia do bundli wg tagów — infra do infra/devops, nie do backend."""
        tmp, workspace = _workspace(
            "name: t\ncore: false\ninclude:\n  - infra:queue:rabbitmq\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertIn("infra:queue:rabbitmq", resolved.enabled_module_ids)
        self.assertIn(
            "infra:queue:rabbitmq", resolved.bundles["infra"].module_ids
        )
        self.assertIn(
            "infra:queue:rabbitmq", resolved.bundles["devops"].module_ids
        )
        self.assertIn("infra:queue:rabbitmq", resolved.bundles["full"].module_ids)
        self.assertNotIn(
            "infra:queue:rabbitmq", resolved.bundles["backend"].module_ids
        )

    def test_full_bundle_takes_everything(self) -> None:
        """Bundle `full` zawiera wszystkie włączone moduły."""
        tmp, workspace = _workspace(
            "name: t\nbackend: django\nweb: expo\ncapabilities: [auth, payments]\n"
            "decisions:\n  auth: jwt\n  queue: redis\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertEqual(
            set(resolved.bundles["full"].module_ids),
            set(resolved.enabled_module_ids),
        )

    def test_auth_variant_flows_to_backend_bundle(self) -> None:
        """`decisions.auth: jwt` dokleja wariant do bundle'a backend."""
        tmp, workspace = _workspace(
            "name: t\nbackend: django\ncapabilities: [auth]\ndecisions:\n  auth: jwt\n"
        )
        try:
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
        finally:
            tmp.cleanup()
        self.assertIn("capability:auth:jwt", resolved.enabled_module_ids)
        self.assertIn(
            "capability:auth:jwt", resolved.bundles["backend"].module_ids
        )
        self.assertNotIn("capability:auth:allauth", resolved.enabled_module_ids)


class TestLanguageAndCodegen(unittest.TestCase):
    """Język i codegen na profilach z Tierami."""

    def _resolve(self, body: str, **kwargs):
        tmp, workspace = _workspace(body)
        try:
            return resolve_workspace_profile(workspace, kit_root=KIT_ROOT, **kwargs)
        finally:
            tmp.cleanup()

    def test_default_language_pl_module(self) -> None:
        """Domyślny język profilu to pl i moduł core:language-pl."""
        resolved = self._resolve("name: t\nbackend: django\n")
        self.assertEqual(resolved.language, "pl")
        self.assertIn("core:language-pl", resolved.enabled_module_ids)
        self.assertNotIn("core:language-en", resolved.enabled_module_ids)
        self.assertIn("core:language-pl", resolved.bundles["backend"].module_ids)

    def test_language_override_en_swaps_module(self) -> None:
        """language_override=en zamienia language-pl na language-en w bundle'ach."""
        resolved = self._resolve("name: t\nbackend: django\n", language_override="EN")
        self.assertEqual(resolved.language, "en")
        self.assertIn("core:language-en", resolved.enabled_module_ids)
        self.assertNotIn("core:language-pl", resolved.enabled_module_ids)
        for name, bundle in resolved.bundles.items():
            with self.subTest(bundle=name):
                self.assertNotIn("core:language-pl", bundle.module_ids)

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

    def test_normalize_auth_variant_default_custom(self) -> None:
        """Brak/nierozpoznana wartość decisions.auth → default custom."""
        self.assertEqual(normalize_auth_variant(None, MANIFEST), "custom")
        self.assertEqual(normalize_auth_variant("unknown", MANIFEST), "custom")
        self.assertEqual(normalize_auth_variant("ALLAUTH", MANIFEST), "allauth")
        self.assertEqual(normalize_auth_variant(" jwt ", MANIFEST), "jwt")
        self.assertEqual(normalize_auth_variant("custom", MANIFEST), "custom")

    def test_normalize_auth_variant_non_string_does_not_crash(self) -> None:
        """decisions.auth jako YAML bool/int (niecudzysłowione) nie crashuje, default custom."""
        for raw in (True, False, 1, 0, ["allauth"], {"a": 1}):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_auth_variant(raw, MANIFEST), "custom")

    def test_files_storage_alias_in_bundle(self) -> None:
        """``capability:files-storage`` w include mapuje się na ``capability:files``."""
        from guides.resolver import normalize_module_id

        self.assertEqual(
            normalize_module_id("capability:files-storage", MANIFEST),
            "capability:files",
        )
        resolved = self._resolve(
            "name: fork-files-alias\ncore: false\ninclude:\n  - capability:files-storage\n"
        )
        backend = resolved.bundles["backend"]
        self.assertIn("capability:files", backend.module_ids)
        self.assertNotIn("capability:files-storage", backend.module_ids)
        self.assertNotIn("capability:files-storage", backend.missing_modules)
        self.assertIn("capability:files", backend.content)

    def test_codegen_graphql_swaps_api_contract(self) -> None:
        """codegen: graphql podmienia arch:api-contract na arch:api-contract:graphql."""
        resolved = self._resolve(
            "name: t\nbackend: django\nweb: expo\ncodegen: graphql\n"
        )
        self.assertEqual(resolved.codegen, "graphql")
        self.assertIn("arch:api-contract:graphql", resolved.enabled_module_ids)
        self.assertNotIn("arch:api-contract", resolved.enabled_module_ids)
        self.assertIn(
            "arch:api-contract:graphql",
            resolved.bundles["architecture"].module_ids,
        )

    def test_search_decision_flows_to_infra_bundle(self) -> None:
        """decisions.search: postgres trafia do bundle infra jak inne sloty infra."""
        resolved = self._resolve(
            "name: t\ndecisions:\n  search: postgres\ncore: false\n"
        )
        self.assertIn("infra:search:postgres", resolved.bundles["infra"].module_ids)

    def test_extra_overlays_cli(self) -> None:
        """Dodatkowe extra_overlays trafiają do overlay_content."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            extra = workspace / "extra.md"
            extra.write_text("# Extra overlay\n", encoding="utf-8")
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.parent.mkdir()
            profile.write_text("name: t\n", encoding="utf-8")
            resolved = resolve_profile(
                profile,
                kit_root=KIT_ROOT,
                workspace_root=workspace,
                extra_overlays=[extra],
            )
            self.assertIn("Extra overlay", resolved.overlay_content)


if __name__ == "__main__":
    unittest.main()
