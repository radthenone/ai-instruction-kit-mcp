"""Testy modułu guides.integrations (#459)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.integrations import (
    _read_profile_integrations,
    INTEGRATIONS_MAP,
    KIT_MARKER,
    is_kit_managed,
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
            orca_file.write_text(f"{KIT_MARKER}\nscripts:\n  setup: node .ai/worktree.mjs sync .\n")

            unrelated = workspace / "other.yaml"
            unrelated.write_text("keep: true\n")

            removed = render_integrations(workspace, kit_root, remove=True)
            self.assertIn("orca.yaml", removed)
            self.assertFalse(orca_file.exists())
            self.assertTrue(unrelated.exists())




    def test_remove_leaves_foreign_file_with_warning(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            foreign_orca = workspace / "orca.yaml"
            foreign_orca.write_text("custom_orca: true\n", encoding="utf-8")

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                removed = render_integrations(workspace, kit_root, remove=True)
            finally:
                sys.stderr = old_err

            self.assertEqual(removed, [])
            self.assertTrue(foreign_orca.is_file())
            self.assertEqual(foreign_orca.read_text(encoding="utf-8"), "custom_orca: true\n")
            self.assertIn("orca.yaml", buf.getvalue())

    def test_render_does_not_overwrite_foreign_file_and_warns(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            templates_dir = kit_root / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "orca.yaml").write_text("kit_orca: true\n", encoding="utf-8")

            foreign_orca = workspace / "orca.yaml"
            foreign_orca.write_text("custom_user_orca: true\n", encoding="utf-8")

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                created = render_integrations(workspace, kit_root, integrations=["orca"])
            finally:
                sys.stderr = old_err

            self.assertEqual(created, [])
            self.assertEqual(foreign_orca.read_text(encoding="utf-8"), "custom_user_orca: true\n")
            self.assertIn("orca.yaml", buf.getvalue())



    def test_is_kit_managed_non_utf8_file_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "invalid.yaml"
            file_path.write_bytes(b"\x80\xff\xfe\x00\x00")
            self.assertFalse(is_kit_managed(file_path))

    def test_render_does_not_crash_on_non_utf8_foreign_file(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            (kit_root / "templates").mkdir(parents=True)
            (kit_root / "templates" / "orca.yaml").write_text("kit: true\n", encoding="utf-8")

            bad_orca = workspace / "orca.yaml"
            bad_orca.write_bytes(b"\x80\xff\xfe\x00\x00")

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                created = render_integrations(workspace, kit_root, integrations=["orca"])
            finally:
                sys.stderr = old_err

            self.assertEqual(created, [])
            self.assertTrue(bad_orca.is_file())
            self.assertEqual(bad_orca.read_bytes(), b"\x80\xff\xfe\x00\x00")

    def test_render_warns_on_missing_template(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                created = render_integrations(workspace, kit_root, integrations=["orca"])
            finally:
                sys.stderr = old_err

            self.assertEqual(created, [])
            self.assertIn("brak szablonu dla orca", buf.getvalue())



    def test_render_coderabbit_template_language_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "ws"
            workspace.mkdir()
            kit_root = Path(tmp_dir) / "kit"
            templates_dir = kit_root / "templates"
            templates_dir.mkdir(parents=True)
            template_file = templates_dir / ".coderabbit.yaml"
            template_file.write_text("# CodeRabbit config\nlanguage: \"{{language}}\"\nauto_review: true\n", encoding="utf-8")

            # Render dla domyślnego/polskiego języka (pl -> pl-PL)
            created = render_integrations(workspace, kit_root, integrations=["coderabbit"], language="pl")
            self.assertIn(".coderabbit.yaml", created)
            cr_path = workspace / ".coderabbit.yaml"
            self.assertTrue(cr_path.is_file())
            content_pl = cr_path.read_text(encoding="utf-8")
            self.assertIn('language: "pl-PL"', content_pl)
            self.assertNotIn("{{language}}", content_pl)
            self.assertIn(KIT_MARKER, content_pl)

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "ws"
            workspace.mkdir()
            kit_root = Path(tmp_dir) / "kit"
            templates_dir = kit_root / "templates"
            templates_dir.mkdir(parents=True)
            template_file = templates_dir / ".coderabbit.yaml"
            template_file.write_text("# CodeRabbit config\nlanguage: \"{{language}}\"\nauto_review: true\n", encoding="utf-8")

            # Render dla języka angielskiego (en -> en-US)
            created = render_integrations(workspace, kit_root, integrations=["coderabbit"], language="en")
            self.assertIn(".coderabbit.yaml", created)
            cr_path = workspace / ".coderabbit.yaml"
            content_en = cr_path.read_text(encoding="utf-8")
            self.assertIn('language: "en-US"', content_en)
            self.assertNotIn("{{language}}", content_en)
            self.assertIn(KIT_MARKER, content_en)


    def test_render_coderabbit_language_round_trip_when_target_is_template(self) -> None:
        """W repo kita szablonem jest sam plik celu: pl -> en -> pl musi wrócić do pl-PL."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / ".coderabbit.yaml"
            target.write_text(f'{KIT_MARKER}\nlanguage: "pl-PL"\nreviews: {{}}\n', encoding="utf-8")
            render_integrations(root, root, integrations=["coderabbit"], language="en")
            self.assertIn('language: "en-US"', target.read_text(encoding="utf-8"))
            render_integrations(root, root, integrations=["coderabbit"], language="pl")
            content = target.read_text(encoding="utf-8")
            self.assertIn('language: "pl-PL"', content)
            self.assertNotIn("en-US", content)


class TestIntegrationsCLI(unittest.TestCase):
    def test_cli_main_prints_unknown_integration_warnings(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            workspace = tmp / "ws"
            workspace.mkdir()
            kit_root = tmp / "kit"
            kit_root.mkdir()
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.parent.mkdir(parents=True)
            profile.write_text("integrations:\n  - unknown_integration\n", encoding="utf-8")

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                argv = ["render_integrations.py", str(workspace), str(profile), str(kit_root)]
                exit_code = main(argv, kit_root=kit_root)
            finally:
                sys.stderr = old_err

            self.assertEqual(exit_code, 0)
            self.assertIn("unknown_integration", buf.getvalue())

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


class TestReadProfileIntegrations(unittest.TestCase):
    """Testy wczytywania profilu w _read_profile_integrations."""

    def test_read_profile_integrations_returns_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = Path(tmp_dir) / "profile.yaml"
            profile.write_text("integrations:\n  - orca\n  - bogus_integration\n", encoding="utf-8")
            integrations, lang, warnings = _read_profile_integrations(profile)
            self.assertEqual(integrations, ["orca"])
            self.assertEqual(lang, "pl")
            self.assertEqual(len(warnings), 1)
            self.assertIn("bogus_integration", warnings[0])

    def test_read_profile_integrations_yaml_error_warns(self) -> None:
        import io
        import sys
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = Path(tmp_dir) / "profile.yaml"
            profile.write_text("integrations: [unclosed_list\n", encoding="utf-8")
            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                integrations, lang, warnings = _read_profile_integrations(profile)
            finally:
                sys.stderr = old_err

            self.assertEqual(integrations, [])
            # Ostrzeżenie na stderr lub w zwróconej liście warnings
            combined = buf.getvalue() + " ".join(warnings)
            self.assertIn("błąd", combined.lower())


    def test_read_profile_integrations_fallback_preserves_language_regardless_of_order(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            p1 = Path(tmp_dir) / "p1.yaml"
            p1.write_text("integrations: [coderabbit]\nlanguage: en\n", encoding="utf-8")
            with patch.dict("sys.modules", {"yaml": None}):
                integrations, lang, warnings = _read_profile_integrations(p1)
                self.assertEqual(integrations, ["coderabbit"])
                self.assertEqual(lang, "en")
                self.assertEqual(warnings, [])

            p2 = Path(tmp_dir) / "p2.yaml"
            p2.write_text("integrations:\n  - coderabbit\nlanguage: en\n", encoding="utf-8")
            with patch.dict("sys.modules", {"yaml": None}):
                integrations, lang, warnings = _read_profile_integrations(p2)
                self.assertEqual(integrations, ["coderabbit"])
                self.assertEqual(lang, "en")
                self.assertEqual(warnings, [])

    def test_read_profile_integrations_fallback_supports_scalar_and_comma_separated(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            p1 = Path(tmp_dir) / "p1.yaml"
            p1.write_text("integrations: orca\nlanguage: pl\n", encoding="utf-8")
            with patch.dict("sys.modules", {"yaml": None}):
                integrations, lang, warnings = _read_profile_integrations(p1)
                self.assertEqual(integrations, ["orca"])
                self.assertEqual(lang, "pl")
                self.assertEqual(warnings, [])

            p2 = Path(tmp_dir) / "p2.yaml"
            p2.write_text('integrations: "orca, coderabbit"\nlanguage: en\n', encoding="utf-8")
            with patch.dict("sys.modules", {"yaml": None}):
                integrations, lang, warnings = _read_profile_integrations(p2)
                self.assertEqual(integrations, ["orca", "coderabbit"])
                self.assertEqual(lang, "en")
                self.assertEqual(warnings, [])

    def test_read_profile_integrations_fallback_supports_unindented_list(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = Path(tmp_dir) / "profile.yaml"
            profile.write_text(
                "integrations:\n"
                "- orca\n"
                "- coderabbit\n"
                "language: en\n"
                "other_key:\n"
                "- should_not_be_included\n",
                encoding="utf-8",
            )
            with patch.dict("sys.modules", {"yaml": None}):
                integrations, lang, warnings = _read_profile_integrations(profile)
                self.assertEqual(integrations, ["orca", "coderabbit"])
                self.assertEqual(lang, "en")
                self.assertEqual(warnings, [])
