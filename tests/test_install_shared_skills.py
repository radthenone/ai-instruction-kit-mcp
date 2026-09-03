"""
Instalacja skilli ze wspólnego źródła: parser frontmatter i degradacja.

Suita `test_bootstrap_clients.sh` sprawdza, że pliki lądują we właściwych
katalogach. Tutaj chodzi o to, **co** w nich jest — a konkretnie o dwie rzeczy,
które łatwo zepsuć po cichu: składany blok YAML w `description` (parser liniowy
zwróciłby dosłowne ">-", a to jedyne pole odpowiedzialne za odpalanie skilla)
oraz gubienie zasobów przy degradacji do jednego pliku.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from install_shared_skills import (  # noqa: E402
    DEGRADED_CLIENTS,
    NATIVE_CLIENTS,
    install_degraded,
    install_native,
    iter_skills,
    parse_frontmatter,
)


def write_skill(root: Path, name: str, frontmatter: str, body: str = "tresc\n") -> Path:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return skill


class TestParseFrontmatter(unittest.TestCase):
    """Frontmatter skilla → pola + treść."""

    def test_plain_scalar(self) -> None:
        meta, body = parse_frontmatter("---\nname: a\ndescription: jedno zdanie\n---\n\ntresc\n")
        self.assertEqual(meta, {"name": "a", "description": "jedno zdanie"})
        self.assertEqual(body, "tresc\n")

    def test_folded_block_becomes_one_line(self) -> None:
        """`description: >-` z wciętymi liniami to jedno zdanie, nie ">-"."""
        meta, _ = parse_frontmatter(
            "---\nname: a\ndescription: >-\n  pierwsza\n  druga\ndisable-model-invocation: true\n---\n\nx\n"
        )
        self.assertEqual(meta["description"], "pierwsza druga")
        self.assertEqual(meta["disable-model-invocation"], "true")

    def test_blank_line_inside_block(self) -> None:
        """Pusta linia w składanym bloku nie kończy pola."""
        meta, _ = parse_frontmatter("---\nname: a\ndescription: >-\n  jeden\n\n  dwa\n---\n\nx\n")
        self.assertEqual(meta["description"], "jeden dwa")

    def test_missing_frontmatter(self) -> None:
        with self.assertRaises(ValueError):
            parse_frontmatter("bez frontmatter\n")

    def test_unterminated_frontmatter(self) -> None:
        with self.assertRaises(ValueError):
            parse_frontmatter("---\nname: a\n")


class TestInstall(unittest.TestCase):
    """Kopia natywna vs degradacja do komendy."""

    def setUp(self) -> None:
        import tempfile

        self.tmp = Path(tempfile.mkdtemp(prefix="kit-skills-"))
        self.src = self.tmp / "src"
        self.src.mkdir()
        self.dest = self.tmp / "dest"
        self.dest.mkdir()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_iter_skills_only_dirs_with_skill_md(self) -> None:
        """Katalog bez SKILL.md nie jest skillem."""
        write_skill(self.src, "prawdziwy", "name: prawdziwy\ndescription: x\n")
        (self.src / "smiec").mkdir()
        (self.src / "smiec" / "notatka.md").write_text("x", encoding="utf-8")
        self.assertEqual([s.name for s in iter_skills(self.src)], ["prawdziwy"])

    def test_native_copies_bundled_resources(self) -> None:
        """Natywny klient dostaje cały katalog, nie sam SKILL.md."""
        skill = write_skill(self.src, "z-zasobami", "name: z-zasobami\ndescription: x\n")
        (skill / "scripts").mkdir()
        (skill / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
        install_native(skill, self.dest)
        self.assertTrue((self.dest / "z-zasobami" / "SKILL.md").is_file())
        self.assertTrue((self.dest / "z-zasobami" / "scripts" / "run.py").is_file())

    def test_native_reinstall_removes_stale_files(self) -> None:
        """Druga instalacja nie zostawia pliku usuniętego ze źródła."""
        skill = write_skill(self.src, "s", "name: s\ndescription: x\n")
        install_native(skill, self.dest)
        (self.dest / "s" / "stary.md").write_text("x", encoding="utf-8")
        install_native(skill, self.dest)
        self.assertFalse((self.dest / "s" / "stary.md").exists())

    def test_degraded_uses_directory_name_not_frontmatter(self) -> None:
        """Komendę nazywa katalog — to jedyna nazwa wspólna dla wszystkich klientów."""
        skill = write_skill(self.src, "katalog", "name: co-innego\ndescription: x\n")
        install_degraded(skill, self.dest, "opencode")
        self.assertTrue((self.dest / "katalog.md").is_file())
        self.assertFalse((self.dest / "co-innego.md").exists())

    def test_degraded_codex_writes_toml(self) -> None:
        skill = write_skill(self.src, "s", "name: s\ndescription: >-\n  jeden\n  dwa\n")
        install_degraded(skill, self.dest, "codex")
        out = (self.dest / "s.toml").read_text(encoding="utf-8")
        self.assertIn('description = "jeden dwa"', out)
        self.assertIn("tresc", out)

    def test_degraded_kiro_copies_raw(self) -> None:
        """kiro czyta surowe pliki agentów — bez renderera, bajt w bajt."""
        skill = write_skill(self.src, "s", "name: s\ndescription: x\n")
        install_degraded(skill, self.dest, None)
        self.assertEqual(
            (self.dest / "s.md").read_text(encoding="utf-8"),
            (skill / "SKILL.md").read_text(encoding="utf-8"),
        )

    def test_degraded_warns_about_dropped_resources(self) -> None:
        """Gubione `scripts/` musi być głośne — inaczej skill cicho staje się wydmuszką."""
        skill = write_skill(self.src, "s", "name: s\ndescription: x\n")
        (skill / "scripts").mkdir()
        (skill / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")

        import contextlib
        import io

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            install_degraded(skill, self.dest, "kilo")
        self.assertIn("scripts", err.getvalue())

    def test_every_known_client_has_a_mode(self) -> None:
        """Każdy klient z `--clients` musi wiedzieć, co zrobić ze skillem."""
        from guides.clients import KNOWN_CLIENTS

        covered = NATIVE_CLIENTS | set(DEGRADED_CLIENTS)
        self.assertEqual(sorted(covered), sorted(KNOWN_CLIENTS))


if __name__ == "__main__":
    unittest.main()
