"""Testy renderowania i migracji ``BUGBOT.md`` (#240).

Moduł ``guides.bugbot_md`` trzyma całą logikę: render szablonu z Tierami, chroniony
blok ``project:rules``, migrację dostosowanych plików po historii szablonu i zapis LF.
Bootstrap woła go z ``scripts/bootstrap-project.sh``.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides.bugbot_md import (
    MAX_MIGRATED_LINES,
    extract_rules,
    is_pristine,
    main,
    migrate,
    needs_migration,
    overlay_paths,
    read_template_history,
    render,
    sync_file,
)

CURRENT_TEMPLATE = """# Bugbot — reguły projektu

Intro.

## Reguły projektu

<!-- project:rules -->
<!-- Wpisz tu własne reguły projektu — blok przetrwa `kit-ai reload` bez zmian. -->
<!-- /project:rules -->

## Ogólne

- kit rule

<!-- tier:backend -->
## Backend

- backend rule
<!-- /tier:backend -->

<!-- tier:client -->
## Frontend

- client rule
<!-- /tier:client -->
"""

# Starsza wersja szablonu: bez bloku, z innym brzmieniem reguł kita.
OLD_TEMPLATE = """# Bugbot — reguły projektu

Intro.

## Ogólne

- kit rule (stara treść)

<!-- tier:backend -->
## Backend

- backend rule (stara treść)
<!-- /tier:backend -->

<!-- tier:client -->
## Frontend

- client rule
<!-- /tier:client -->
"""

DEFAULT_RULES = "\n<!-- Wpisz tu własne reguły projektu — blok przetrwa `kit-ai reload` bez zmian. -->\n"


class TestRender(unittest.TestCase):
    def test_tier_sections_follow_profile(self) -> None:
        """Sekcje ``<!-- tier:X -->`` zostają tylko dla wybranych Tierów."""
        only_backend = render(CURRENT_TEMPLATE, "backend")
        self.assertIn("## Backend", only_backend)
        self.assertNotIn("## Frontend", only_backend)
        self.assertNotIn("<!-- tier:", only_backend)

        no_tiers = render(CURRENT_TEMPLATE, "")
        self.assertNotIn("## Backend", no_tiers)
        self.assertNotIn("## Frontend", no_tiers)

    def test_block_is_kept_by_default(self) -> None:
        """Bez podmiany treści blok zostaje z instrukcją z szablonu."""
        self.assertEqual(extract_rules(render(CURRENT_TEMPLATE, "")), DEFAULT_RULES)

    def test_render_works_for_template_without_block(self) -> None:
        """Starsze szablony nie mają bloku — render nie może ich zepsuć."""
        text = render(OLD_TEMPLATE, "backend")
        self.assertIn("- backend rule (stara treść)", text)
        self.assertIsNone(extract_rules(text))


KIT_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "cursor" / "BUGBOT.md"


class TestRenderPaths(unittest.TestCase):
    """#266: ścieżki reguł szablonu z `## Ścieżki` overlayu, bez nich — domyślne."""

    def test_backend_path_comes_from_overlay(self) -> None:
        template = KIT_TEMPLATE.read_text(encoding="utf-8")

        text = render(template, "backend", paths={"backend": "server/"})

        self.assertIn("`server/`", text)
        self.assertNotIn("{{path:", text)

    def test_missing_key_renders_default(self) -> None:
        template = KIT_TEMPLATE.read_text(encoding="utf-8")

        text = render(template, "backend")

        self.assertIn("`backend/`", text)
        self.assertNotIn("{{path:", text)

    def test_overlay_paths_tolerate_missing_backticks_and_key_case(self) -> None:
        overlay = (
            "## Ścieżki\n\n- Backend: backend/src/ — kod API\n- web: `frontend/web/`\n"
            "\n## Inne\n\n- api: `x/`\n"
        )

        self.assertEqual(
            overlay_paths(overlay), {"backend": "backend/src/", "web": "frontend/web/"}
        )

    def test_reload_reads_overlay_paths_and_keeps_file_pristine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            overlay = workspace / ".ai" / "project.md"
            overlay.parent.mkdir()
            overlay.write_text("## Ścieżki\n\n- backend: `server/` — API\n", encoding="utf-8")
            dest = workspace / "BUGBOT.md"
            env = {
                "SRC": str(KIT_TEMPLATE),
                "DEST": str(dest),
                "TIERS": "backend",
                "OVERLAY": str(overlay),
            }

            with mock.patch.dict(os.environ, env):
                main()
            with mock.patch.dict(os.environ, {**env, "CHECK_ONLY": "1"}):
                pristine = main()

            self.assertIn("`server/`", dest.read_text(encoding="utf-8"))
            self.assertEqual(pristine, 0)


class TestPristine(unittest.TestCase):
    def test_current_render_is_pristine(self) -> None:
        self.assertTrue(is_pristine(render(CURRENT_TEMPLATE, "backend"), CURRENT_TEMPLATE))

    def test_empty_block_counts_as_pristine(self) -> None:
        """Blok opróżniony przez użytkownika to nadal nietknięty plik kita."""
        emptied = render(CURRENT_TEMPLATE, "backend", "\n")
        self.assertTrue(is_pristine(emptied, CURRENT_TEMPLATE))

    def test_project_rules_make_file_customized(self) -> None:
        custom = render(CURRENT_TEMPLATE, "backend", "\n- moja reguła\n")
        self.assertFalse(is_pristine(custom, CURRENT_TEMPLATE))

    def test_needs_migration_only_for_customized_file_without_block(self) -> None:
        self.assertFalse(needs_migration(render(CURRENT_TEMPLATE, ""), CURRENT_TEMPLATE))
        self.assertFalse(
            needs_migration(
                render(CURRENT_TEMPLATE, "", "\n- moja reguła\n"), CURRENT_TEMPLATE
            )
        )
        self.assertTrue(needs_migration(render(OLD_TEMPLATE, ""), CURRENT_TEMPLATE))


class TestSyncBlock(unittest.TestCase):
    def test_block_survives_reload_byte_for_byte(self) -> None:
        """Reguły projektu wracają identyczne, a reszta pliku jest z bieżącego szablonu."""
        rules = "\n- Moja reguła A\n- Moja reguła B\n"
        customized = render(CURRENT_TEMPLATE, "backend", rules)
        customized = customized.replace("- kit rule", "- kit rule po mojemu")

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            dest.write_text(customized, encoding="utf-8", newline="\n")
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")

            result = sync_file(dest, source, "backend")

            self.assertEqual(result.action, "refreshed")
            text = dest.read_text(encoding="utf-8")
            self.assertEqual(extract_rules(text), rules)
            self.assertIn("- kit rule\n", text)
            self.assertNotIn("po mojemu", text)

    def test_new_file_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")

            result = sync_file(dest, source, "")

            self.assertEqual(result.action, "created")
            self.assertEqual(dest.read_text(encoding="utf-8"), render(CURRENT_TEMPLATE, ""))

    def test_written_file_uses_lf(self) -> None:
        """Zapis zawsze z LF, także na Windows (#224)."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")

            sync_file(dest, source, "backend")

            self.assertNotIn(b"\r\n", dest.read_bytes())

    def test_crlf_file_with_block_is_rewritten_once_to_lf(self) -> None:
        """CRLF w pliku z blokiem: pierwszy reload zapisuje LF, drugi nic nie zmienia."""
        rules = "\n- Moja reguła\n"
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")
            dest.write_bytes(
                render(CURRENT_TEMPLATE, "backend", rules).replace("\n", "\r\n").encode("utf-8")
            )

            first = sync_file(dest, source, "backend")
            second = sync_file(dest, source, "backend")

            self.assertEqual(first.action, "refreshed")
            self.assertEqual(second.action, "unchanged")
            self.assertNotIn(b"\r", dest.read_bytes())
            self.assertEqual(extract_rules(dest.read_text(encoding="utf-8")), rules)

    def test_unclosed_block_is_uncertain_and_untouched(self) -> None:
        """Sam otwierający albo sam zamykający znacznik → plik bez zmian, ostrzeżenie."""
        full = render(CURRENT_TEMPLATE, "", "\n- Moja reguła\n")
        variants = {
            "open": full.replace("<!-- /project:rules -->", ""),
            "close": full.replace("<!-- project:rules -->", ""),
        }
        for name, text in variants.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "BUGBOT.md"
                source = Path(tmp) / "template.md"
                source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")
                dest.write_text(text, encoding="utf-8", newline="\n")

                result = sync_file(dest, source, "", history=[OLD_TEMPLATE, CURRENT_TEMPLATE])

                self.assertEqual(result.action, "uncertain")
                self.assertIn("niedomknięty blok project:rules", result.message)
                self.assertEqual(dest.read_text(encoding="utf-8"), text)


class TestMigration(unittest.TestCase):
    def test_migrates_added_rules_into_block(self) -> None:
        """Plik ze starszego renderu + 2 dopisane reguły → bieżący szablon z blokiem."""
        dest = render(OLD_TEMPLATE, "backend") + "\n- Moja reguła A\n- Moja reguła B\n"

        result = migrate(dest, CURRENT_TEMPLATE, "backend", [OLD_TEMPLATE])

        self.assertIsNotNone(result.text)
        self.assertEqual(result.moved, ["- Moja reguła A", "- Moja reguła B"])
        self.assertEqual(
            result.text,
            render(CURRENT_TEMPLATE, "backend", "\n- Moja reguła A\n- Moja reguła B\n"),
        )
        self.assertIsNone(result.reason)

    def test_old_render_without_additions_is_just_refreshed(self) -> None:
        result = migrate(render(OLD_TEMPLATE, ""), CURRENT_TEMPLATE, "", [OLD_TEMPLATE])

        self.assertIsNotNone(result.text)
        self.assertEqual(result.moved, [])
        self.assertEqual(result.text, render(CURRENT_TEMPLATE, ""))

    def test_missing_history_leaves_file_uncertain(self) -> None:
        dest = render(OLD_TEMPLATE, "backend") + "\n- Moja reguła\n"

        result = migrate(dest, CURRENT_TEMPLATE, "backend", [])

        self.assertIsNone(result.text)
        self.assertIn("histor", result.reason or "")

    def test_too_many_added_lines_is_uncertain(self) -> None:
        additions = "\n" + "\n".join(f"- reguła {i}" for i in range(MAX_MIGRATED_LINES + 1)) + "\n"
        dest = render(OLD_TEMPLATE, "") + additions

        result = migrate(dest, CURRENT_TEMPLATE, "", [OLD_TEMPLATE])

        self.assertIsNone(result.text)
        self.assertIn("diff", (result.reason or "").lower())

    def test_removed_template_lines_are_uncertain(self) -> None:
        """Edycja reguły kita w pliku to nie „dopisana reguła” — nie zgadujemy."""
        dest = render(OLD_TEMPLATE, "").replace("- kit rule (stara treść)", "- moja wersja kita")

        result = migrate(dest, CURRENT_TEMPLATE, "", [OLD_TEMPLATE])

        self.assertIsNone(result.text)

    def test_uncertain_file_is_not_touched(self) -> None:
        dest_text = render(OLD_TEMPLATE, "") + "\n- Moja reguła\n"
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            dest.write_text(dest_text, encoding="utf-8", newline="\n")
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")

            result = sync_file(dest, source, "", history=[])

            self.assertEqual(result.action, "uncertain")
            self.assertEqual(dest.read_text(encoding="utf-8"), dest_text)
            self.assertIn("project:rules", result.message)
            # #266: jedna linia z trybem naprawy zamiast instrukcji ręcznego przenoszenia.
            self.assertEqual(len(result.message.splitlines()), 1, result.message)
            self.assertIn('/kit-project-edit "napraw zgłoszenia doctora"', result.message)

    def test_migration_message_lists_moved_lines(self) -> None:
        dest_text = render(OLD_TEMPLATE, "") + "\n- Moja reguła A\n- Moja reguła B\n"
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "BUGBOT.md"
            source = Path(tmp) / "template.md"
            dest.write_text(dest_text, encoding="utf-8", newline="\n")
            source.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")

            result = sync_file(dest, source, "", history=[OLD_TEMPLATE])

            self.assertEqual(result.action, "migrated")
            self.assertIn("Moja reguła A", result.message)
            self.assertIn("Moja reguła B", result.message)


class TestHistory(unittest.TestCase):
    def test_reads_versions_from_git_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kit"
            (root / "templates" / "cursor").mkdir(parents=True)
            path = root / "templates" / "cursor" / "BUGBOT.md"
            path.write_text(OLD_TEMPLATE, encoding="utf-8", newline="\n")

            def git(*args: str) -> None:
                subprocess.run(
                    ["git", "-C", str(root), *args],
                    check=True,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                )

            try:
                git("init", "-q")
                git("config", "user.email", "test@test.local")
                git("config", "user.name", "test")
                git("add", ".")
                git("commit", "-q", "-m", "old")
                path.write_text(CURRENT_TEMPLATE, encoding="utf-8", newline="\n")
                git("commit", "-q", "-am", "current")
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("brak gita w środowisku")

            history = read_template_history(root)

            self.assertGreaterEqual(len(history), 2)
            self.assertEqual(history[0], CURRENT_TEMPLATE)
            self.assertIn(OLD_TEMPLATE, history)

    def test_kit_inside_foreign_repo_means_no_history(self) -> None:
        """Kit (np. koło w venv) wewnątrz cudzego repo nie czyta historii tamtego repo."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "app"
            kit = repo / ".venv" / "guides" / "_data"
            (kit / "templates" / "cursor").mkdir(parents=True)
            # Ten sam rel_path w obu miejscach: `git show sha:<rel>` trafiłby w plik repo.
            for root in (repo, kit):
                (root / "templates" / "cursor").mkdir(parents=True, exist_ok=True)
                (root / "templates" / "cursor" / "BUGBOT.md").write_text(
                    OLD_TEMPLATE, encoding="utf-8", newline="\n"
                )
            try:
                for args in (
                    ("init", "-q"),
                    ("config", "user.email", "test@test.local"),
                    ("config", "user.name", "test"),
                    ("add", "."),
                    ("commit", "-q", "-m", "app"),
                ):
                    subprocess.run(
                        ["git", "-C", str(repo), *args],
                        check=True,
                        capture_output=True,
                        stdin=subprocess.DEVNULL,
                    )
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("brak gita w środowisku")

            self.assertEqual(read_template_history(kit), [])

    def test_no_git_means_no_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_template_history(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
