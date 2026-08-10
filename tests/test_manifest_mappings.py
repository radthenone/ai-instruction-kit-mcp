"""
Manifest jako jedyne miejsce reguł włączania modułów (ADR-0001) i kanoniczna
kolejność transformacji Module ID (ADR-0002).
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from guides.manifest import find_kit_root, load_manifest
from guides.resolver import apply_profile_decisions, resolve_profile

KIT_ROOT = find_kit_root(Path(__file__))


class TestManifestMappings(unittest.TestCase):
    """Reguły Slot / Capability / Domain / Pattern / Stack czytane z manifestu."""

    def setUp(self) -> None:
        self.manifest = load_manifest(KIT_ROOT)

    def test_slots_expose_known_decisions(self) -> None:
        """Slot `queue` zna oba warianty z modułów infra."""
        queue = self.manifest.mappings.slots["queue"]
        self.assertEqual(queue["rabbitmq"], "infra:queue:rabbitmq")
        self.assertEqual(queue["redis"], "infra:queue:redis")

    def test_every_mapped_module_id_exists_in_registry(self) -> None:
        """Każde ID po prawej stronie mapowania musi być zarejestrowanym modułem."""
        dangling = sorted(
            module_id
            for module_id in self.manifest.mappings.all_module_ids()
            if module_id not in self.manifest.modules
        )
        self.assertEqual(dangling, [], msg=f"mapowania wskazują na nieznane moduły: {dangling}")

    def test_capabilities_and_patterns_come_from_manifest(self) -> None:
        """Capability i Pattern nie są już zaszyte w Pythonie."""
        self.assertEqual(self.manifest.mappings.capabilities["payments"], "capability:payments")
        self.assertEqual(
            self.manifest.mappings.patterns["capability-provider"],
            "pattern:capability-provider",
        )

    def test_stacks_map_to_module_lists(self) -> None:
        """Stack rozwija się do listy modułów, nie do jednego."""
        self.assertIn("stack:django-drf", self.manifest.mappings.stacks["django-drf"])


class TestManifestDrivenExtension(unittest.TestCase):
    """Nowa wartość Slotu wchodzi bez dotykania Pythona (leverage z ADR-0001)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.kit = self.tmp / "kit"
        shutil.copytree(KIT_ROOT / "modules", self.kit / "modules")
        shutil.copytree(KIT_ROOT / "profiles", self.kit / "profiles")
        shutil.copy(KIT_ROOT / "manifest.yaml", self.kit / "manifest.yaml")
        self.raw = yaml.safe_load((self.kit / "manifest.yaml").read_text(encoding="utf-8"))

    def _write_manifest(self) -> None:
        (self.kit / "manifest.yaml").write_text(
            yaml.safe_dump(self.raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _write_profile(self, body: dict) -> Path:
        path = self.kit / "profiles" / "tmp-test.yaml"
        path.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_new_slot_value_needs_only_markdown_and_manifest(self) -> None:
        """Dodanie `queue: kafka` to nowy plik .md + wpis w manifeście, zero Pythona."""
        (self.kit / "modules" / "infra" / "queue" / "kafka.md").write_text(
            "# Kafka\n\nInstrukcje kolejki.\n", encoding="utf-8"
        )
        self.raw["modules"]["infra:queue:kafka"] = {
            "path": "modules/infra/queue/kafka.md",
            "title": "Kafka",
            "tags": ["infra"],
        }
        self.raw["mappings"]["slots"]["queue"]["kafka"] = "infra:queue:kafka"
        self._write_manifest()

        profile = self._write_profile({"name": "kafka-test", "decisions": {"queue": "kafka"}})
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertIn("infra:queue:kafka", resolved.enabled_module_ids)
        self.assertIn("Instrukcje kolejki.", resolved.bundles["infra"].content)

    def test_alias_onto_variant_base_still_gets_the_variant(self) -> None:
        """
        ADR-0002: Alias normalizuje się PRZED wstawieniem wariantu.

        Alias celujący w `capability:auth` musi dostać `capability:auth:jwt` obok —
        przy normalizacji na końcu wariant znikał po cichu.
        """
        self.raw["mappings"]["aliases"]["modules"]["capability:authentication"] = (
            "capability:auth"
        )
        self._write_manifest()

        profile = self._write_profile(
            {
                "name": "alias-test",
                "core": False,
                "include": ["capability:authentication"],
                "decisions": {"auth": "jwt"},
            }
        )
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertIn("capability:auth", resolved.enabled_module_ids)
        self.assertIn("capability:auth:jwt", resolved.enabled_module_ids)

    def test_unknown_decision_is_reported_not_fatal(self) -> None:
        """ADR-0004: `queue: kafka` bez mapowania nie wywraca serwera, ale widać go w indeksie."""
        profile = self._write_profile({"name": "typo-test", "decisions": {"queue": "kafkaa"}})
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertEqual(resolved.unrecognised_decisions, (("queue", "kafkaa"),))
        self.assertIn("kafkaa", resolved.index_markdown)

    def test_second_variant_slot_is_driven_by_decisions(self) -> None:
        """
        Drugi Wariant w manifeście honoruje `decisions`, nie wstawia domyślnego po cichu.

        Regresja: pipeline czytał wartość tylko dla slotów `auth` i `codegen`, więc nowy
        wpis dostawał ``None`` i zawsze lądował na wartości domyślnej.
        """
        for name in ("payments-stripe", "payments-manual"):
            (self.kit / "modules" / "capabilities" / f"{name}.md").write_text(
                f"# {name}\n", encoding="utf-8"
            )
            self.raw["modules"][f"capability:payments:{name.split('-')[1]}"] = {
                "path": f"modules/capabilities/{name}.md",
                "title": name,
                "tags": ["capability"],
            }
        self.raw["mappings"]["variants"]["payments"] = {
            "base": "capability:payments",
            "default": "manual",
            "values": {
                "stripe": "capability:payments:stripe",
                "manual": "capability:payments:manual",
            },
        }
        self._write_manifest()

        profile = self._write_profile(
            {
                "name": "payments-variant",
                "core": False,
                "capabilities": ["payments"],
                "decisions": {"payments": "stripe"},
            }
        )
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertIn("capability:payments:stripe", resolved.enabled_module_ids)
        self.assertNotIn("capability:payments:manual", resolved.enabled_module_ids)
        self.assertEqual(resolved.unrecognised_decisions, ())

    def test_manifest_without_mappings_degrades_instead_of_crashing(self) -> None:
        """
        Stary Kit Root (manifest bez `mappings`) nadal serwuje bundle.

        ADR-0004 w wersji dla Kita: widoczny-ale-uboższy bije niewidoczny-i-martwy.
        Regresja: puste reguły leciały `KeyError` z `VariantRule`.
        """
        self.raw.pop("mappings")
        self._write_manifest()

        profile = self._write_profile({"name": "stale-kit", "include": ["core:repo-first"]})
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertIn("core:repo-first", resolved.enabled_module_ids)
        self.assertIn("backend", resolved.bundles)

    def test_deprecated_alias_is_reported(self) -> None:
        """ADR-0003: Alias działa, ale zgłasza się w indeksie jako do migracji."""
        profile = self._write_profile(
            {"name": "alias-report", "core": False, "capabilities": ["files-storage"]}
        )
        resolved = resolve_profile(profile, kit_root=self.kit, workspace_root=self.tmp)

        self.assertIn("capability:files", resolved.enabled_module_ids)
        self.assertEqual(resolved.deprecated_aliases, (("files-storage", "files"),))
        self.assertIn("files-storage", resolved.index_markdown)


class TestUnifiedPipeline(unittest.TestCase):
    """Jeden seam transformacji Module ID zamiast dwóch kolejności."""

    def setUp(self) -> None:
        self.manifest = load_manifest(KIT_ROOT)

    def test_normalisation_precedes_variant_insertion(self) -> None:
        """Kolejność jest własnością `apply_profile_decisions`, nie jego wywołań."""
        result = apply_profile_decisions(
            ["capability:files-storage", "capability:auth"],
            manifest=self.manifest,
            language="en",
            selections={"codegen": "orval", "auth": "jwt"},
        )
        self.assertEqual(
            list(result),
            ["capability:files", "capability:auth", "capability:auth:jwt"],
        )

    def test_language_modules_collapse_to_one(self) -> None:
        """Wiele modułów językowych scala się w jeden, na pozycji pierwszego."""
        result = apply_profile_decisions(
            ["core:language-pl", "core:repo-first", "core:language-en"],
            manifest=self.manifest,
            language="en",
            selections={"codegen": "orval", "auth": "custom"},
        )
        self.assertEqual(list(result), ["core:language-en", "core:repo-first"])

    def test_codegen_substitutes_the_api_contract_module(self) -> None:
        """`codegen: graphql` podmienia moduł bazowy, nie dokłada drugiego."""
        result = apply_profile_decisions(
            ["arch:api-contract"],
            manifest=self.manifest,
            language="pl",
            selections={"codegen": "graphql", "auth": "custom"},
        )
        self.assertEqual(list(result), ["arch:api-contract:graphql"])

    def test_enabled_modules_and_bundles_agree_on_transforms(self) -> None:
        """Obie ścieżki (enabled + bundle) przechodzą przez ten sam pipeline."""
        resolved = resolve_profile(
            KIT_ROOT / "profiles" / "shop.yaml",
            kit_root=KIT_ROOT,
            workspace_root=KIT_ROOT,
            language_override="en",
            codegen_override="graphql",
        )
        backend = resolved.bundles["backend"].module_ids
        self.assertIn("capability:auth:allauth", backend)
        self.assertIn("capability:auth:allauth", resolved.enabled_module_ids)
        self.assertNotIn("core:language-pl", backend)
        self.assertNotIn("core:language-pl", resolved.enabled_module_ids)
        self.assertNotIn("arch:api-contract", backend)


if __name__ == "__main__":
    unittest.main()
