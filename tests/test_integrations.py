"""Testy modułu guides.integrations (#459)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.integrations import (
    INTEGRATIONS_MAP,
    main,
    KNOWN_INTEGRATIONS,
    coderabbit_language,
    integration_target_file,
    integration_template,
    parse_integrations,
    render_integrations,
)


class TestIntegrationsParser(unittest.TestCase):
    """Testy parsowania i walidacji listy integrations z Profilu."""

    def test_empty_or_missing_returns_empty_list_and_no_warnings(self) -> None:
        for empty_val in [None, "", [], (), "   "]:
            parsed = parse_integrations(empty_val)
            self.assertEqual(parsed.integrations, [])
            self.assertEqual(parsed.warnings, [])

    def test_known_integrations_list(self) -> None:
        parsed = parse_integrations(["orca", "coderabbit"])
        self.assertEqual(parsed.integrations, ["orca", "coderabbit"])
        self.assertEqual(parsed.warnings, [])

    def test_known_integrations_comma_separated_string(self) -> None:
        parsed = parse_integrations("orca, coderabbit")
        self.assertEqual(parsed.integrations, ["orca", "coderabbit"])
        self.assertEqual(parsed.warnings, [])

    def test_whitespace_and_case_normalization(self) -> None:
        parsed = parse_integrations(["  Orca  ", "CodeRabbit"])
        self.assertEqual(parsed.integrations, ["orca", "coderabbit"])
        self.assertEqual(parsed.warnings, [])

    def test_deduplication_preserves_order(self) -> None:
        parsed = parse_integrations(["orca", "coderabbit", "orca"])
        self.assertEqual(parsed.integrations, ["orca", "coderabbit"])
        self.assertEqual(parsed.warnings, [])

    def test_unknown_name_generates_warning_and_omits_it(self) -> None:
        parsed = parse_integrations(["orca", "unknown_app", "coderabbit"])
        self.assertEqual(parsed.integrations, ["orca", "coderabbit"])
        self.assertEqual(len(parsed.warnings), 1)
        self.assertIn("nieznana integracja `unknown_app` — pominięto", parsed.warnings[0])

    def test_named_tuple_unpacking(self) -> None:
        integrations, warnings = parse_integrations(["orca"])
        self.assertEqual(integrations, ["orca"])
        self.assertEqual(warnings, [])


class TestIntegrationsMapping(unittest.TestCase):
    """Testy mapowania integracji na pliki i szablony oraz języka CodeRabbit."""

    def test_known_integrations_constant(self) -> None:
        self.assertIn("orca", KNOWN_INTEGRATIONS)
        self.assertIn("coderabbit", KNOWN_INTEGRATIONS)

    def test_target_files_mapping(self) -> None:
        self.assertEqual(integration_target_file("orca"), "orca.yaml")
        self.assertEqual(integration_target_file("coderabbit"), ".coderabbit.yaml")
        self.assertIsNone(integration_target_file("nonexistent"))

    def test_template_mapping(self) -> None:
        self.assertEqual(integration_template("orca"), "orca.yaml")
        self.assertEqual(integration_template("coderabbit"), ".coderabbit.yaml")
        self.assertIsNone(integration_template("nonexistent"))

    def test_integrations_map_structure(self) -> None:
        orca_def = INTEGRATIONS_MAP["orca"]
        self.assertEqual(orca_def.name, "orca")
        self.assertEqual(orca_def.target_file, "orca.yaml")

        cr_def = INTEGRATIONS_MAP["coderabbit"]
        self.assertEqual(cr_def.name, "coderabbit")
        self.assertEqual(cr_def.target_file, ".coderabbit.yaml")

    def test_coderabbit_language(self) -> None:
        self.assertEqual(coderabbit_language("pl"), "pl-PL")
        self.assertEqual(coderabbit_language("PL"), "pl-PL")
        self.assertEqual(coderabbit_language("pol"), "pl-PL")
        self.assertEqual(coderabbit_language("en"), "en-US")
        self.assertEqual(coderabbit_language("EN"), "en-US")
        self.assertEqual(coderabbit_language(None), "pl-PL")


class TestIntegrationsRender(unittest.TestCase):
    """Testy renderowania i usuwania plików integracji."""

    def test_empty_integrations_renders_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            created = render_integrations(workspace, kit_root, integrations=[])
            self.assertEqual(created, [])
            self.assertFalse((workspace / "orca.yaml").exists())
            self.assertFalse((workspace / ".coderabbit.yaml").exists())

    def test_empty_profile_dict_renders_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            created = render_integrations(workspace, kit_root, profile_data={"integrations": []})
            self.assertEqual(created, [])
            self.assertFalse((workspace / "orca.yaml").exists())
            self.assertFalse((workspace / ".coderabbit.yaml").exists())

    def test_remove_deletes_only_own_integration_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            orca_file = workspace / "orca.yaml"
            orca_file.write_text("scripts:\n  setup: node .ai/worktree.mjs sync .\n")

            unrelated = workspace / "other.yaml"
            unrelated.write_text("keep: true\n")

            removed = render_integrations(workspace, kit_root, remove=True)
            self.assertIn("orca.yaml", removed)
            self.assertFalse(orca_file.exists())
            self.assertTrue(unrelated.exists())



class TestIntegrationsCLI(unittest.TestCase):
    """Testy CLI render_integrations."""

    def test_cli_main_slices_argv_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            workspace = tmp / "ws"
            workspace.mkdir()
            kit_root = tmp / "kit"
            (kit_root / "templates").mkdir(parents=True)
            (kit_root / "templates" / "orca.yaml").write_text("orca_cfg: true\n", encoding="utf-8")
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.parent.mkdir(parents=True)
            profile.write_text("integrations:\n  - orca\n", encoding="utf-8")

            argv = ["render_integrations.py", str(workspace), str(profile), str(kit_root)]
            exit_code = main(argv, kit_root=kit_root)
            self.assertEqual(exit_code, 0)
            self.assertTrue((workspace / "orca.yaml").is_file())
