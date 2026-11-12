"""Skill `/kit-retro` (#372): kontrakt źródła i degradacja do jednego pliku.

Skill klasyfikuje znaleziska ze skanu `kit-ai retro scan` i niczego nie zapisuje w repo.
Testy pilnują rzeczy, które łatwo zepsuć po cichu: nazwy skilla (od niej zależy komenda
u klientów bez natywnych skilli), taksonomii z CONTEXT.md oraz tego, że skill przeżywa
degradację do jednego pliku — bez `references/`, `scripts/` ani `assets/`.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = KIT_ROOT / "templates" / "shared" / "skills" / "kit-retro"
SKILL_FILE = SKILL_DIR / "SKILL.md"
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from install_shared_skills import (  # noqa: E402
    DEGRADED_CLIENTS,
    install_degraded,
    install_native,
    remove_renamed,
    parse_frontmatter,
)

# Początek opisu skilla kita sprzed zmiany nazwy (#422) — taki sam we wszystkich wersjach.
OLD_KIT_SKILL = "Klasyfikacja znalezisk z wyniku skanu sesji agentów (`kit-ai retro scan`, zapisy JSONL"

# Cztery kategorie z opisu #372 (taksonomia z `mattpocock-skills:retro`).
CATEGORIES = ("kit", "projekt", "agent", "zewnętrzne")
# Pola rekordu `finding` z `kit-ai retro scan` (src/guides/retro.py), które skill czyta.
RECORD_FIELDS = ("kind", "fingerprint", "count", "replay", "evidence")
# Samo „retro” w cudzysłowie jako fraza triggera — koliduje z `/retro` z mattpocock-skills (#422).
BARE_RETRO_TRIGGER = "„retro[“”]"


class RetroSkillSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL_FILE.read_text(encoding="utf-8")
        self.meta, self.body = parse_frontmatter(self.text)

    def test_directory_holds_only_skill_md(self) -> None:
        """Degradacja gubi zasoby obok SKILL.md, więc skill nie ma żadnych."""
        self.assertEqual(sorted(p.name for p in SKILL_DIR.iterdir()), ["SKILL.md"])

    def test_name_matches_directory(self) -> None:
        """Komendę u klientów bez skilli nazywa katalog, a `name` ma być z nim zgodny."""
        self.assertEqual(self.meta.get("name"), SKILL_DIR.name)

    def test_name_does_not_collide_with_agent(self) -> None:
        """Agent i skill o tej samej nazwie nadpisałyby się w katalogu komend."""
        self.assertFalse((KIT_ROOT / "templates" / "shared" / "agents" / "retro.md").exists())

    def test_description_names_trigger_and_read_only_contract(self) -> None:
        description = self.meta.get("description", "")
        self.assertIn("/kit-retro", description)
        self.assertIn("kit-ai retro scan", description)
        self.assertIn("Nie edytuje plików", description)

    def test_body_defines_taxonomy(self) -> None:
        for category in CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(f"**{category}**", self.body)

    def test_body_reads_scan_record_fields(self) -> None:
        for field in RECORD_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.body)

    def test_body_stays_within_length_ceiling(self) -> None:
        self.assertLess(len(self.body.splitlines()), 500)

    def test_body_forbids_issue_creation(self) -> None:
        self.assertIn("nie zakłada issue", self.body)

    def test_description_names_kit_trigger(self) -> None:
        """Tryb `--kit` ma być w opisie, inaczej skill nie odpali się na `/kit-retro --kit`."""
        self.assertIn("--kit", self.meta.get("description", ""))

    def test_description_does_not_trigger_on_bare_retro(self) -> None:
        """'retro' jako samodzielna fraza triggera koliduje z /retro Matta (#422).

        Opis może zawierać 'retro' jako część fraz specyficznych dla kita
        (np. 'kit-ai retro scan', '/kit-retro'), ale nie jako osobne słowo
        cytowane cudzysłowem (np. „retro“) — traktowane jako trigger skilla.
        """
        description = self.meta.get("description", "")
        # Szukamy „retro“ jako samodzielnie cytowanej frazy triggera,
        # ale nie jako fragmentu dłuższej nazwy (kit-retro, retro scan etc.)
        self.assertNotRegex(
            description,
            BARE_RETRO_TRIGGER,
            "Opis nie może zawierać samodzielnego retro jako frazy triggera "
            "— to koliduje z /retro z mattpocock-skills.",
        )

    def test_bare_retro_pattern_catches_the_old_description(self) -> None:
        """Wzorzec ma łapać opis sprzed #422, inaczej test wyżej niczego nie pilnuje."""
        self.assertRegex("pisze `/kit-retro`, „retro”, „przejrzyj sesję”", BARE_RETRO_TRIGGER)

    def test_description_defers_general_retro_to_mattpocock(self) -> None:
        """Opis ma wskazywać /retro z mattpocock-skills dla ogólnej retrospektywy (#422)."""
        # Cały zwrot: samo "/retro" siedzi też w ścieżce cache `kit-ai/retro/`.
        self.assertIn(
            "`/retro` z mattpocock-skills",
            self.meta.get("description", ""),
            "Opis powinien odsyłać ogólną retrospektywę do /retro z mattpocock-skills.",
        )

    def test_body_heading_uses_kit_retro_name(self) -> None:
        """Nagłówek H1 w body ma używać nazwy 'kit-retro', nie samego 'Retro' (#422)."""
        self.assertTrue(
            self.body.startswith("# kit-retro — klasyfikacja znalezisk"),
            "Nagłówek H1 musi brzmieć '# kit-retro — klasyfikacja znalezisk'.",
        )

    def test_body_describes_kit_mode_over_the_report(self) -> None:
        """`/kit-retro --kit` czyta agregację z `kit-ai retro report`, a nie pojedynczy skan."""
        self.assertIn("`/kit-retro --kit`", self.body)
        self.assertIn("`kit-ai retro report`", self.body)

    def test_kit_mode_routes_cards_and_keeps_dedup_marker(self) -> None:
        """Karty idą przez `/create-task` albo `/kit-project-edit`, a marker z raportu trafia do karty."""
        for needle in ("/create-task", "/kit-project-edit", "retro-fingerprint"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.body)

    def test_kit_mode_leaves_card_creation_to_the_human(self) -> None:
        self.assertIn("karty tworzy człowiek", self.body)

    def test_kit_mode_proposes_only_kit_and_agent(self) -> None:
        """`/kit-project-edit` nie zakłada issue, więc propozycja `projekt` wracałaby w każdym raporcie (#410)."""
        kit_mode = self.body[self.body.index("## Tryb `--kit`") : self.body.index("## Zasady")]
        self.assertIn("tylko dla `kit` i `agent`", kit_mode)
        self.assertIn("znalezisk projektowych, uruchom `/kit-retro` w repo", kit_mode)

    def test_kit_mode_dedups_against_issues_in_every_state(self) -> None:
        self.assertIn("otwartym albo zamkniętym", self.body)
        self.assertNotIn("otwartych issue", self.body)


class CreateTaskRetroMarkerTests(unittest.TestCase):
    """`/create-task` przenosi marker z propozycji do body issue — bez tego dedup z ADR-0015 nie działa (#410)."""

    def setUp(self) -> None:
        self.text = (KIT_ROOT / "templates" / "shared" / "agents" / "create-task.md").read_text(encoding="utf-8")
        self.card = self.text[self.text.index("## FAZA 3") : self.text.index("## FAZA 4")]

    def test_card_shows_the_marker_at_the_end_of_context(self) -> None:
        context = self.card[self.card.index("## Kontekst") :]
        self.assertIn("<!-- retro-fingerprint: <fingerprint> -->", context)

    def test_marker_comes_only_from_the_report(self) -> None:
        self.assertIn("kit-ai retro report", self.card)
        self.assertIn("nigdy go nie zgadujesz", self.card)

    def test_split_stamps_one_card_only(self) -> None:
        split = self.text[self.text.index("## `--split`") : self.text.index("## Etykiety")]
        self.assertIn("retro-fingerprint", split)


class RetroSkillDegradationTests(unittest.TestCase):
    def test_degraded_clients_get_one_complete_file(self) -> None:
        """Klient bez natywnych skilli dostaje komendę `/kit-retro` jako jeden kompletny plik."""
        for client, fmt in DEGRADED_CLIENTS.items():
            with self.subTest(client=client), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp)
                install_degraded(SKILL_DIR, dest, fmt)
                written = sorted(dest.iterdir())
                self.assertEqual(len(written), 1)
                content = written[0].read_text(encoding="utf-8")
                for category in CATEGORIES:
                    self.assertIn(category, content)
                self.assertIn("Nie edytuje plików", content)

    def test_native_client_gets_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            install_native(SKILL_DIR, dest)
            self.assertEqual(sorted(p.name for p in (dest / "kit-retro").iterdir()), ["SKILL.md"])

    def test_reload_removes_kit_skill_under_old_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "retro").mkdir()
            (dest / "retro" / "SKILL.md").write_text(OLD_KIT_SKILL, encoding="utf-8")
            (dest / "retro.md").write_text(OLD_KIT_SKILL, encoding="utf-8")
            remove_renamed("kit-retro", dest, None)
            remove_renamed("kit-retro", dest, ".md")
            self.assertEqual(list(dest.iterdir()), [])

    def test_reload_keeps_foreign_skill_under_old_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "retro").mkdir()
            (dest / "retro" / "SKILL.md").write_text("Conduct a retrospective on a coding session.", encoding="utf-8")
            (dest / "retro.md").write_text("cudza komenda", encoding="utf-8")
            remove_renamed("kit-retro", dest, None)
            remove_renamed("kit-retro", dest, ".md")
            self.assertTrue((dest / "retro" / "SKILL.md").is_file())
            self.assertTrue((dest / "retro.md").is_file())

    def test_reload_keeps_foreign_skill_mentioning_kit_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "retro").mkdir()
            (dest / "retro" / "SKILL.md").write_text("Mój skill; po sesji odpal kit-ai retro scan.", encoding="utf-8")
            (dest / "retro.md").write_text("Moja komenda: kit-ai retro scan", encoding="utf-8")
            remove_renamed("kit-retro", dest, None)
            remove_renamed("kit-retro", dest, ".md")
            self.assertTrue((dest / "retro" / "SKILL.md").is_file())
            self.assertTrue((dest / "retro.md").is_file())

    def test_reload_keeps_old_kit_skill_with_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "retro" / "scripts").mkdir(parents=True)
            (dest / "retro" / "SKILL.md").write_text(OLD_KIT_SKILL, encoding="utf-8")
            (dest / "retro" / "scripts" / "mine.sh").write_text("echo moje", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                remove_renamed("kit-retro", dest, None)
            self.assertTrue((dest / "retro" / "scripts" / "mine.sh").is_file())
            self.assertIn("zostawiam", err.getvalue())

    def test_reload_keeps_link_under_old_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            target = Path(tmp) / "elsewhere"
            dest.mkdir()
            target.mkdir()
            (target / "SKILL.md").write_text("kit-ai retro scan", encoding="utf-8")
            try:
                (dest / "retro").symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("brak uprawnień do symlinków")
            remove_renamed("kit-retro", dest, None)
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertTrue((dest / "retro").is_symlink())


if __name__ == "__main__":
    unittest.main()
