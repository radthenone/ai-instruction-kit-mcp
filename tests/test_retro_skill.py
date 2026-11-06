"""Skill `/retro` (#372): kontrakt źródła i degradacja do jednego pliku.

Skill klasyfikuje znaleziska ze skanu `kit-ai retro scan` i niczego nie zapisuje w repo.
Testy pilnują rzeczy, które łatwo zepsuć po cichu: nazwy skilla (od niej zależy komenda
u klientów bez natywnych skilli), taksonomii z GLOSSARY.md oraz tego, że skill przeżywa
degradację do jednego pliku — bez `references/`, `scripts/` ani `assets/`.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = KIT_ROOT / "templates" / "shared" / "skills" / "retro"
SKILL_FILE = SKILL_DIR / "SKILL.md"
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from install_shared_skills import (  # noqa: E402
    DEGRADED_CLIENTS,
    install_degraded,
    install_native,
    parse_frontmatter,
)

# Cztery kategorie z opisu #372 (taksonomia z `mattpocock-skills:retro`).
CATEGORIES = ("kit", "projekt", "agent", "zewnętrzne")
# Pola rekordu `finding` z `kit-ai retro scan` (src/guides/retro.py), które skill czyta.
RECORD_FIELDS = ("kind", "fingerprint", "count", "replay", "evidence")


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
        self.assertIn("/retro", description)
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


class RetroSkillDegradationTests(unittest.TestCase):
    def test_degraded_clients_get_one_complete_file(self) -> None:
        """Klient bez natywnych skilli dostaje komendę `/retro` jako jeden kompletny plik."""
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
            self.assertEqual(sorted(p.name for p in (dest / "retro").iterdir()), ["SKILL.md"])


if __name__ == "__main__":
    unittest.main()
