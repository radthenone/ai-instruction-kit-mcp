"""Testy renderowania i migracji ``BUGBOT.md`` (#240).

Moduł ``guides.bugbot_md`` trzyma całą logikę: render szablonu z Tierami, chroniony
blok ``project:rules``, migrację dostosowanych plików po historii szablonu i zapis LF.
Bootstrap woła go z ``scripts/bootstrap-project.sh``.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from guides.bugbot_md import (
    MAX_MIGRATED_LINES,
    Migration,
    extract_rules,
    is_pristine,
    migrate,
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

    def test_no_git_means_no_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_template_history(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
