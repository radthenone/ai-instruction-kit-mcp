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
    profile_has_integration,
    render_integrations,
)


def _make_symlink(link: Path, target: Path | str) -> None:
    """
    Utwórz dowiązanie symboliczne potrzebne testowi.

    Brak uprawnień albo obsługi dowiązań to błąd testu, a nie pominięcie: cichy skip zostawia
    test bez asercji ochrony plików (zasada: nie skipujemy testów, także lokalnie).

    Args:
        link: Ścieżka dowiązania do utworzenia.
        target: Cel dowiązania.
    """
    link.symlink_to(target)


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

    def test_t3code_known_without_warning(self) -> None:
        integrations, warnings = parse_integrations(["t3code"])
        self.assertEqual(integrations, ["t3code"])
        self.assertEqual(warnings, [])


class TestIntegrationsMapping(unittest.TestCase):
    """Testy mapowania integracji na pliki i szablony oraz języka CodeRabbit."""

    def test_known_integrations_constant(self) -> None:
        self.assertIn("orca", KNOWN_INTEGRATIONS)
        self.assertIn("coderabbit", KNOWN_INTEGRATIONS)

    def test_t3code_is_known_without_target_file(self) -> None:
        self.assertIn("t3code", KNOWN_INTEGRATIONS)
        self.assertNotIn("t3code", INTEGRATIONS_MAP)
        self.assertIsNone(integration_target_file("t3code"))
        self.assertIsNone(integration_template("t3code"))

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

    def test_t3code_renders_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            kit_root = workspace / "kit"
            kit_root.mkdir()

            created = render_integrations(workspace, kit_root, integrations=["t3code"])
            self.assertEqual(created, [])
            self.assertFalse((workspace / ".ai").exists())

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


    def test_remove_keeps_template_when_workspace_is_kit_root(self) -> None:
        """--remove w repo kita nie kasuje pliku, który jest szablonem integracji."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / ".coderabbit.yaml"
            target.write_text(f'{KIT_MARKER}\nlanguage: "pl-PL"\n', encoding="utf-8")
            removed = render_integrations(root, root, remove=True)
            self.assertNotIn(".coderabbit.yaml", removed)
            self.assertTrue(target.is_file())


class TestProfileHasIntegration(unittest.TestCase):
    """Warunek integracji bez pliku (karta T3): odczyt Profilu jak w renderze."""

    def _profile(self, workspace: Path, text: str) -> Path:
        profile = workspace / ".ai" / "project.profile.yaml"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(text, encoding="utf-8")
        return profile

    def test_listed_integration_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations:\n  - t3code\n")
            self.assertIs(profile_has_integration(profile, "t3code"), True)

    def test_other_integrations_only_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [orca]\n")
            self.assertIs(profile_has_integration(profile, "t3code"), False)

    def test_missing_profile_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / ".ai" / "project.profile.yaml"
            self.assertIs(profile_has_integration(missing, "t3code"), False)

    def test_yaml_syntax_error_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code\n")
            self.assertIsNone(profile_has_integration(profile, "t3code"))

    def test_unknown_name_does_not_block_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code, literowka]\n")
            self.assertIs(profile_has_integration(profile, "t3code"), True)


    def test_duplicate_integrations_key_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code]\nintegrations: []\n")
            self.assertIsNone(profile_has_integration(profile, "t3code"))

    def test_invalid_date_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code]\nreview: 2026-13-01\n")
            self.assertIsNone(profile_has_integration(profile, "t3code"))

    def test_empty_or_non_mapping_profile_is_none(self) -> None:
        for text in ("", "- t3code\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp_dir:
                profile = self._profile(Path(tmp_dir), text)
                self.assertIsNone(profile_has_integration(profile, "t3code"))

    def test_without_pyyaml_only_a_hit_is_trusted(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code]\n")
            other = self._profile(Path(tmp_dir) / "x", "integrations: [orca]\n")
            with mock.patch.dict("sys.modules", {"yaml": None}):
                self.assertIs(profile_has_integration(profile, "t3code"), True)
                self.assertIsNone(profile_has_integration(other, "t3code"))

    def test_unreadable_profile_is_none(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            profile = self._profile(Path(tmp_dir), "integrations: [t3code]\n")
            with mock.patch.object(Path, "stat", side_effect=PermissionError("odmowa dostępu")):
                self.assertIsNone(profile_has_integration(profile, "t3code"))


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

    def test_cli_has_exit_codes(self) -> None:
        """--has: 0 gdy Profil wymienia integrację, 3 gdy nie, 2 gdy nie daje się odczytać jednoznacznie; bez zapisu."""
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
            cases = [
                ("integrations: [t3code]\n", 0),
                ("integrations: [orca]\n", 3),
                ("integrations: [t3code\n", 2),
            ]
            for text, expected in cases:
                with self.subTest(text=text):
                    profile.write_text(text, encoding="utf-8")
                    buf = io.StringIO()
                    old_err = sys.stderr
                    try:
                        sys.stderr = buf
                        argv = ["render_integrations.py", "--has", "t3code", str(workspace), str(profile), str(kit_root)]
                        exit_code = main(argv, kit_root=kit_root)
                    finally:
                        sys.stderr = old_err
                    self.assertEqual(exit_code, expected)
            self.assertEqual([p.name for p in profile.parent.iterdir()], ["project.profile.yaml"])


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


KIT_ROOT = Path(__file__).resolve().parents[1]


class TestOrcaTemplate(unittest.TestCase):
    """Szablon orca.yaml w templates/ to źródło dla konsumentów: wheel nie pakuje pliku z Kit Root (#456)."""

    def test_orca_template_is_kit_marked_and_matches_kit_root_copy(self) -> None:
        """Szablon ma marker kita i jest identyczny z plikiem orca.yaml w Kit Root."""
        import yaml

        template = KIT_ROOT / "templates" / "orca.yaml"
        self.assertTrue(template.is_file(), f"Brak szablonu {template}")
        self.assertEqual(template.read_bytes(), (KIT_ROOT / "orca.yaml").read_bytes())
        content = template.read_text(encoding="utf-8")
        self.assertIn(KIT_MARKER, content)
        self.assertEqual(yaml.safe_load(content)["scripts"]["setup"], "node .ai/worktree.mjs sync .")

    def test_render_takes_orca_from_templates_without_kit_root_file(self) -> None:
        """Kit Root z koła ma `templates/`, a orca.yaml w nim nie istnieje."""
        import shutil

        with tempfile.TemporaryDirectory() as tmp_dir:
            kit_root = Path(tmp_dir) / "kit"
            shutil.copytree(KIT_ROOT / "templates", kit_root / "templates")
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()

            created = render_integrations(workspace, kit_root, integrations=["orca"])

            self.assertEqual(created, ["orca.yaml"])
            self.assertEqual((workspace / "orca.yaml").read_bytes(), (KIT_ROOT / "orca.yaml").read_bytes())


class TestIntegrationOwnershipOnReload(unittest.TestCase):
    """Reload z Profilu: własność pliku po linii markera, sprzątanie integracji wypisanych z Profilu (#456)."""

    def _write_profile(self, workspace: Path, body: str) -> Path:
        profile = workspace / ".ai" / "project.profile.yaml"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(body, encoding="utf-8")
        return profile

    def test_marker_mentioned_inside_a_line_is_not_ownership(self) -> None:
        """Plik, który tylko wspomina kit w komentarzu, nie jest plikiem kita."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "orca.yaml"
            path.write_text("scripts:\n  setup: ./mine.sh  # ai-instruction-kit style, customized\n", encoding="utf-8")
            self.assertFalse(is_kit_managed(path))

    def test_reload_removes_kit_file_of_integration_unlisted_from_profile(self) -> None:
        """Wypisanie `orca` z Profilu i reload usuwa orca.yaml wyrenderowany przez kit."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._write_profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            self.assertTrue((workspace / "orca.yaml").is_file())

            self._write_profile(workspace, "integrations: []\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertFalse((workspace / "orca.yaml").exists())

    def test_reload_keeps_user_file_of_unlisted_integration(self) -> None:
        """Plik użytkownika bez markera zostaje, nawet gdy integracji nie ma w Profilu."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "orca.yaml").write_text("custom: true\n", encoding="utf-8")
            profile = self._write_profile(workspace, "integrations: []\n")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertEqual((workspace / "orca.yaml").read_text(encoding="utf-8"), "custom: true\n")

    def test_reload_with_broken_profile_keeps_kit_files(self) -> None:
        """Błąd składni Profilu nie może skasować plików integracji."""
        import io
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._write_profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            self._write_profile(workspace, "integrations: [unclosed\n")

            old_err, sys.stderr = sys.stderr, io.StringIO()
            try:
                render_integrations(workspace, KIT_ROOT, profile_data=profile)
            finally:
                sys.stderr = old_err

            self.assertTrue((workspace / "orca.yaml").is_file())


class TestIntegrationSafetyEdges(unittest.TestCase):
    """Brzegi bezpieczeństwa renderu integracji po review PR #518 (#456)."""

    def _profile(self, workspace: Path, body: str) -> Path:
        profile = workspace / ".ai" / "project.profile.yaml"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(body, encoding="utf-8")
        return profile

    def test_indented_marker_inside_user_script_is_not_ownership(self) -> None:
        """Marker wcięty w bloku `scripts.setup` to treść użytkownika, nie znacznik kita."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "orca.yaml").write_text(
                "scripts:\n  setup: |\n    # ai-instruction-kit\n    ./mine.sh\n", encoding="utf-8"
            )
            profile = self._profile(workspace, "integrations: []\n")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertIn("./mine.sh", (workspace / "orca.yaml").read_text(encoding="utf-8"))

    def test_profile_that_is_not_a_usable_map_keeps_kit_files(self) -> None:
        """Pusty Profil albo lista zamiast mapy nie jest pustym wyborem i nie kasuje plików kita."""
        for broken in ("", "- orca\n"):
            with self.subTest(profile=broken):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    workspace = Path(tmp_dir)
                    profile = self._profile(workspace, "integrations:\n  - orca\n")
                    render_integrations(workspace, KIT_ROOT, profile_data=profile)
                    profile.write_text(broken, encoding="utf-8")

                    render_integrations(workspace, KIT_ROOT, profile_data=profile)

                    self.assertTrue((workspace / "orca.yaml").is_file())

    def test_unknown_only_profile_keeps_kit_files(self) -> None:
        """Literówka w nazwie integracji nie kasuje orca.yaml; zostaje ostrzeżenie."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("integrations:\n  - ocra\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_file())

    def test_map_without_integrations_key_prunes_kit_files(self) -> None:
        """Poprawna mapa bez klucza `integrations` oznacza zero integracji i sprząta pliki kita."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("name: test\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertFalse((workspace / "orca.yaml").exists())

    def test_unlink_failure_does_not_abort_render(self) -> None:
        """Nieudane usunięcie jednego pliku kita zostawia go do następnego reloadu i nie blokuje renderu."""
        import io
        import sys
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / ".coderabbit.yaml").write_text(f"{KIT_MARKER}\nlanguage: \"pl-PL\"\n", encoding="utf-8")
            profile = self._profile(workspace, "integrations:\n  - orca\n")

            buf = io.StringIO()
            old_err, sys.stderr = sys.stderr, buf
            try:
                with mock.patch.object(Path, "unlink", side_effect=PermissionError("zablokowany")):
                    created = render_integrations(workspace, KIT_ROOT, profile_data=profile)
            finally:
                sys.stderr = old_err

            self.assertEqual(created, ["orca.yaml"])
            self.assertIn(".coderabbit.yaml", buf.getvalue())

    def test_self_render_does_not_overwrite_root_orca_yaml(self) -> None:
        """W repo kita reload nie zastępuje lokalnie zmienionego orca.yaml kopią z templates/."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            kit = Path(tmp_dir) / "kit"
            (kit / "templates").mkdir(parents=True)
            (kit / "templates" / "orca.yaml").write_text(
                f"{KIT_MARKER}\nscripts:\n  setup: template-setup\n", encoding="utf-8"
            )
            (kit / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts:\n  setup: local-setup\n", encoding="utf-8")

            render_integrations(kit, kit, integrations=["orca"])

            self.assertIn("local-setup", (kit / "orca.yaml").read_text(encoding="utf-8"))

    def test_render_does_not_follow_dangling_symlink(self) -> None:
        """Dowiązanie symboliczne w miejscu orca.yaml nie kieruje zapisu poza repo."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kit = root / "kit"
            (kit / "templates").mkdir(parents=True)
            (kit / "templates" / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside.yaml"
            _make_symlink(workspace / "orca.yaml", outside)

            render_integrations(workspace, kit, integrations=["orca"])

            self.assertFalse(outside.exists())

    def test_dry_run_keeps_kit_source_protected_like_real_reload(self) -> None:
        """Dry-run w repo kita nie planuje usunięcia orca.yaml, którego prawdziwy reload nie usunie."""
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kit = root / "kit"
            kit.mkdir()
            (kit / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")
            sandbox = root / "sandbox"
            sandbox.mkdir()
            (sandbox / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")
            profile = self._profile(sandbox, "integrations: []\n")

            with mock.patch.dict(os.environ, {"KIT_WORKSPACE": str(kit)}):
                render_integrations(sandbox, kit, profile_data=profile)

            self.assertTrue((sandbox / "orca.yaml").is_file())

    def test_dry_run_plans_removal_of_consumer_file(self) -> None:
        """Dry-run w zwykłym repo konsumenta planuje usunięcie orca.yaml, bo prawdziwy reload go usunie."""
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kit = root / "kit"
            kit.mkdir()
            consumer = root / "consumer"
            consumer.mkdir()
            sandbox = root / "sandbox"
            sandbox.mkdir()
            (sandbox / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")
            profile = self._profile(sandbox, "integrations: []\n")

            with mock.patch.dict(os.environ, {"KIT_WORKSPACE": str(consumer)}):
                render_integrations(sandbox, kit, profile_data=profile)

            self.assertFalse((sandbox / "orca.yaml").exists())


class TestIntegrationLinksAndDuplicateKeys(unittest.TestCase):
    """Dowiązania, cykle i powtórzone klucze w Profilu po review PR #518, runda 3 (#456)."""

    def _profile(self, workspace: Path, body: str) -> Path:
        profile = workspace / ".ai" / "project.profile.yaml"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(body, encoding="utf-8")
        return profile

    def test_cyclic_symlink_does_not_abort_render(self) -> None:
        """Cykliczne dowiązanie orca.yaml nie przerywa renderu pozostałych integracji."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            _make_symlink(workspace / "orca.yaml", "orca.yaml")

            created = render_integrations(workspace, KIT_ROOT, integrations=["orca", "coderabbit"])

            self.assertIn(".coderabbit.yaml", created)

    def test_cyclic_symlink_does_not_abort_prune(self) -> None:
        """Cykliczne dowiązanie orca.yaml nie zatrzymuje sprzątania coderabbit po wypisaniu z Profilu."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / ".coderabbit.yaml").write_text(f"{KIT_MARKER}\nlanguage: \"pl-PL\"\n", encoding="utf-8")
            _make_symlink(workspace / "orca.yaml", "orca.yaml")
            profile = self._profile(workspace, "integrations: []\n")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertFalse((workspace / ".coderabbit.yaml").exists())

    def test_user_symlink_to_marked_file_is_kept_on_prune(self) -> None:
        """Dowiązanie użytkownika do pliku z markerem nie jest plikiem kita i nie znika przy sprzątaniu."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            elsewhere = root / "elsewhere.yaml"
            elsewhere.write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")
            _make_symlink(workspace / "orca.yaml", elsewhere)
            profile = self._profile(workspace, "integrations: []\n")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_symlink())

    def test_duplicate_integrations_key_keeps_kit_files(self) -> None:
        """Powtórzony klucz `integrations` w Profilu nie daje zgody na sprzątanie: PyYAML po cichu bierze ostatni."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("integrations:\n  - orca\nintegrations: []\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_file())

    def test_dry_run_in_kit_repo_uses_same_source_as_real_reload(self) -> None:
        """Dry-run w repo kita wybiera ten sam szablon co realny reload: plik korzenia, nie kopia z templates/."""
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kit = root / "kit"
            (kit / "templates").mkdir(parents=True)
            (kit / "templates" / "orca.yaml").write_text(
                f"{KIT_MARKER}\nscripts:\n  setup: template-setup\n", encoding="utf-8"
            )
            (kit / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts:\n  setup: local-setup\n", encoding="utf-8")
            sandbox = root / "sandbox"
            sandbox.mkdir()
            (sandbox / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts:\n  setup: local-setup\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"KIT_WORKSPACE": str(kit)}):
                render_integrations(sandbox, kit, integrations=["orca"])

            self.assertIn("local-setup", (sandbox / "orca.yaml").read_text(encoding="utf-8"))

    def test_dry_run_keeps_real_symlink_unplanned(self) -> None:
        """Dowiązanie w prawdziwym Workspace nie jest nadpisywane ani kasowane w planie, także gdy sandbox ma kopię."""
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kit = root / "kit"
            (kit / "templates").mkdir(parents=True)
            (kit / "templates" / "orca.yaml").write_text(
                f"{KIT_MARKER}\nscripts:\n  setup: template-setup\n", encoding="utf-8"
            )
            real = root / "consumer"
            real.mkdir()
            elsewhere = root / "elsewhere.yaml"
            elsewhere.write_text(f"{KIT_MARKER}\nscripts:\n  setup: linked\n", encoding="utf-8")
            _make_symlink(real / "orca.yaml", elsewhere)
            sandbox = root / "sandbox"
            sandbox.mkdir()
            (sandbox / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts:\n  setup: sandbox-copy\n", encoding="utf-8")
            profile = self._profile(sandbox, "integrations: []\n")

            with mock.patch.dict(os.environ, {"KIT_WORKSPACE": str(real)}):
                render_integrations(sandbox, kit, integrations=["orca"])
                render_integrations(sandbox, kit, profile_data=profile)

            self.assertIn("sandbox-copy", (sandbox / "orca.yaml").read_text(encoding="utf-8"))

    def test_unicode_line_separator_inside_yaml_value_is_not_marker(self) -> None:
        """U+2028 wewnątrz wartości YAML nie dzieli linii: fragment z markerem nie jest markerem pliku."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "orca.yaml").write_text(
                'scripts:\n  setup: "a # ai-instruction-kit b"\n', encoding="utf-8"
            )
            profile = self._profile(workspace, "integrations: []\n")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertIn("a # ai-instruction-kit", (workspace / "orca.yaml").read_text(encoding="utf-8"))

    def test_duplicate_integrations_inside_merge_key_keeps_kit_files(self) -> None:
        """Powtórzony `integrations` w mapie scalanej przez `<<` nie daje zgody na sprzątanie."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("<<: {integrations: [orca], integrations: []}\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_file())

    def _unreadable_profile_setup(self, root: Path) -> tuple[Path, Path, Path]:
        workspace = root / "ws"
        workspace.mkdir()
        kit_root = root / "kit"
        kit_root.mkdir()
        profile = workspace / ".ai" / "project.profile.yaml"
        profile.parent.mkdir(parents=True)
        profile.write_bytes(b"\x80\xff integrations: [orca]\n")
        return workspace, kit_root, profile

    def test_cli_reports_unreadable_profile_instead_of_raising(self) -> None:
        """CLI nie czyta Profilu przed renderem: nieczytelny plik kończy się ostrzeżeniem, nie wyjątkiem."""
        import io
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace, kit_root, profile = self._unreadable_profile_setup(Path(tmp_dir))
            buf = io.StringIO()
            old_err, sys.stderr = sys.stderr, buf
            try:
                exit_code = main(
                    ["render_integrations.py", str(workspace), str(profile), str(kit_root)], kit_root=kit_root
                )
            finally:
                sys.stderr = old_err

            self.assertEqual(exit_code, 0)
            self.assertIn("nie odczytano Profilu", buf.getvalue())

    def test_cli_remove_deletes_kit_file_without_reading_profile(self) -> None:
        """Ścieżka --remove usuwa oznaczony orca.yaml i nie odczytuje Profilu, nawet nieczytelnego."""
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace, kit_root, profile = self._unreadable_profile_setup(Path(tmp_dir))
            (workspace / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")

            with mock.patch("guides.integrations._parse_profile_text") as parse:
                exit_code = main(
                    ["render_integrations.py", "--remove", str(workspace), str(profile), str(kit_root)],
                    kit_root=kit_root,
                )

            self.assertEqual(exit_code, 0)
            self.assertFalse((workspace / "orca.yaml").exists())
            parse.assert_not_called()

    def test_cli_remove_accepts_cyclic_profile_symlink(self) -> None:
        """Ścieżka --remove nie rozwiązuje ścieżki Profilu, więc cykliczne dowiązanie nie blokuje usuwania."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace, kit_root, _ = self._unreadable_profile_setup(Path(tmp_dir))
            profile = workspace / ".ai" / "cyclic.yaml"
            _make_symlink(profile, "cyclic.yaml")
            (workspace / "orca.yaml").write_text(f"{KIT_MARKER}\nscripts: {{}}\n", encoding="utf-8")

            exit_code = main(
                ["render_integrations.py", "--remove", str(workspace), str(profile), str(kit_root)], kit_root=kit_root
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse((workspace / "orca.yaml").exists())

    def test_duplicate_merge_keys_keep_kit_files(self) -> None:
        """Powtórzony klucz scalania `<<` w Profilu nie daje zgody na sprzątanie: wynik jest niejednoznaczny."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("<<: {integrations: [orca]}\n<<: {integrations: []}\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_file())

    def test_non_scalar_key_blocks_prune(self) -> None:
        """Nieskalarny klucz (`? !!str {=: integrations}`) zdubluje `integrations` po konstrukcji, więc sprzątanie stoi."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("integrations: [orca]\n? !!str {=: integrations}\n: []\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertTrue((workspace / "orca.yaml").is_file())

    def test_explicit_override_of_merged_integrations_still_prunes(self) -> None:
        """Jawne `integrations: []` nadpisujące wartość z `<<` to zwykły wybór, więc sprzątanie zostaje dozwolone."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations:\n  - orca\n")
            render_integrations(workspace, KIT_ROOT, profile_data=profile)
            profile.write_text("<<: {integrations: [orca]}\nintegrations: []\n", encoding="utf-8")

            render_integrations(workspace, KIT_ROOT, profile_data=profile)

            self.assertFalse((workspace / "orca.yaml").exists())

    def test_profile_access_error_is_reported_not_raised(self) -> None:
        """Brak dostępu przy sprawdzeniu Profilu kończy się ostrzeżeniem, nie wyjątkiem renderu."""
        import io
        import sys
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            profile = self._profile(workspace, "integrations: [orca]\n")
            buf = io.StringIO()
            old_err, sys.stderr = sys.stderr, buf
            try:
                original_stat = Path.stat
                original_is_file = Path.is_file

                def stat_denied_for_profile(self: Path, *, follow_symlinks: bool = True):
                    if self == profile:
                        raise PermissionError("brak dostępu")
                    return original_stat(self, follow_symlinks=follow_symlinks)

                def is_file_hidden_for_profile(self: Path) -> bool:
                    # Python 3.14: odmowa dostępu wygląda jak brak pliku; dotyczy tylko Profilu.
                    return False if self == profile else original_is_file(self)

                with (
                    mock.patch.object(Path, "is_file", is_file_hidden_for_profile),
                    mock.patch.object(Path, "stat", stat_denied_for_profile),
                ):
                    created = render_integrations(workspace, KIT_ROOT, profile_data=profile)
            finally:
                sys.stderr = old_err

            self.assertEqual(created, [])
            self.assertIn("nie odczytano Profilu", buf.getvalue())


class TestMakeSymlinkHelper(unittest.TestCase):
    """Pomocnik dowiązań nigdy nie pomija testu: brak uprawnień ma być widoczny jako błąd."""

    def test_permission_error_fails_instead_of_skipping(self) -> None:
        """Brak uprawnień do dowiązań kończy się błędem, nie pominięciem testu."""
        from unittest import mock

        with mock.patch.object(Path, "symlink_to", side_effect=PermissionError("brak uprawnień")):
            with self.assertRaises(PermissionError):
                _make_symlink(Path("link.yaml"), "target.yaml")


class TestCodeRabbitIntegration(unittest.TestCase):
    """Testy kontraktu renderowania konfiguracji CodeRabbit (#457)."""

    def test_coderabbit_template_exists_in_templates(self) -> None:
        """Szablon .coderabbit.yaml musi istnieć w katalogu templates/ i być poprawnym YAML."""
        import yaml

        template_path = KIT_ROOT / "templates" / ".coderabbit.yaml"
        self.assertTrue(
            template_path.is_file(),
            f"Brak szablonu .coderabbit.yaml w {template_path}",
        )
        content = template_path.read_text(encoding="utf-8")
        self.assertIn("reviews:", content)
        self.assertIn("base_branches:", content)
        # Po podstawieniu języka treść musi być poprawnym YAML
        substituted = content.replace("{{language}}", "pl-PL")
        data = yaml.safe_load(substituted)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("language"), "pl-PL")
        reviews = data.get("reviews", {})
        self.assertIsInstance(reviews, dict)
        auto_review = reviews.get("auto_review", {})
        self.assertIsInstance(auto_review, dict)
        self.assertIn("^dev$", auto_review.get("base_branches", []))

    def test_render_creates_coderabbit_when_present_and_omits_when_absent(self) -> None:
        """Render tworzy .coderabbit.yaml przy wpisie coderabbit i nie tworzy go bez niego."""
        import yaml

        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir) / "consumer-ws"
            ws.mkdir()
            profile = ws / ".ai" / "project.profile.yaml"
            profile.parent.mkdir(parents=True)

            # Bez coderabbit w profilu -> nie tworzy .coderabbit.yaml
            profile.write_text("name: test\nlanguage: pl\nintegrations:\n  - orca\n", encoding="utf-8")
            created_without = render_integrations(ws, KIT_ROOT, profile_data=profile)
            self.assertNotIn(".coderabbit.yaml", created_without)
            self.assertFalse((ws / ".coderabbit.yaml").exists())

            # Z coderabbit w profilu -> tworzy .coderabbit.yaml
            profile.write_text("name: test\nlanguage: pl\nintegrations:\n  - coderabbit\n", encoding="utf-8")
            created_with = render_integrations(ws, KIT_ROOT, profile_data=profile)
            self.assertIn(".coderabbit.yaml", created_with)
            cr_file = ws / ".coderabbit.yaml"
            self.assertTrue(cr_file.is_file())
            content = cr_file.read_text(encoding="utf-8")
            self.assertIn(KIT_MARKER, content)
            self.assertIn('language: "pl-PL"', content)

            data = yaml.safe_load(content)
            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("language"), "pl-PL")
            self.assertIn("^dev$", data["reviews"]["auto_review"]["base_branches"])

    def test_remove_deletes_own_coderabbit_file_only(self) -> None:
        """Remove usuwa tylko własny plik .coderabbit.yaml oznaczony markerem."""
        import io
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir) / "consumer-ws"
            ws.mkdir()
            cr_file = ws / ".coderabbit.yaml"

            # 1. Własny plik kita z markerem
            cr_file.write_text(f"{KIT_MARKER}\nlanguage: \"pl-PL\"\n", encoding="utf-8")
            removed = render_integrations(ws, KIT_ROOT, remove=True)
            self.assertIn(".coderabbit.yaml", removed)
            self.assertFalse(cr_file.exists())

            # 2. Obcy plik użytkownika bez markera
            cr_file.write_text("language: \"en-US\"\ncustom: true\n", encoding="utf-8")
            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                removed_foreign = render_integrations(ws, KIT_ROOT, remove=True)
            finally:
                sys.stderr = old_err

            self.assertNotIn(".coderabbit.yaml", removed_foreign)
            self.assertTrue(cr_file.is_file())
            self.assertIn(".coderabbit.yaml", buf.getvalue())
            self.assertEqual(cr_file.read_text(encoding="utf-8"), "language: \"en-US\"\ncustom: true\n")

    def test_render_does_not_overwrite_foreign_coderabbit_file(self) -> None:
        """Render nie nadpisuje pliku .coderabbit.yaml stworzonego ręcznie przez użytkownika."""
        import io
        import sys

        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir) / "consumer-ws"
            ws.mkdir()
            cr_file = ws / ".coderabbit.yaml"
            cr_file.write_text("language: \"en-US\"\ncustom_config: true\n", encoding="utf-8")

            buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = buf
                created = render_integrations(ws, KIT_ROOT, integrations=["coderabbit"])
            finally:
                sys.stderr = old_err

            self.assertEqual(created, [])
            self.assertTrue(cr_file.is_file())
            self.assertEqual(cr_file.read_text(encoding="utf-8"), "language: \"en-US\"\ncustom_config: true\n")
            self.assertIn(".coderabbit.yaml", buf.getvalue())

    def test_root_coderabbit_matches_rendered_template(self) -> None:
        """Plik .coderabbit.yaml w root repo kita jest identyczny z wynikiem renderu szablonu (#490)."""
        root_cr = KIT_ROOT / ".coderabbit.yaml"
        self.assertTrue(root_cr.is_file(), f"Brak pliku .coderabbit.yaml w root {KIT_ROOT}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir) / "workspace"
            ws.mkdir()
            profile = ws / ".ai" / "project.profile.yaml"
            profile.parent.mkdir(parents=True)
            profile.write_text("name: kit\nlanguage: pl\nintegrations:\n  - coderabbit\n", encoding="utf-8")

            created = render_integrations(ws, KIT_ROOT, profile_data=profile)
            self.assertIn(".coderabbit.yaml", created)

            rendered_content = (ws / ".coderabbit.yaml").read_bytes()
            root_content = root_cr.read_bytes()
            self.assertEqual(
                root_content,
                rendered_content,
                "Plik .coderabbit.yaml w root repo kita różni się od renderu szablonu templates/.coderabbit.yaml (np. brak końcowego \\n)",
            )
