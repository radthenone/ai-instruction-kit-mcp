"""
Whitelista śledzenia komend kita w .gitignore (#528).

Sekcja instruction-kit w .gitignore ma być dokładnie tym, co bootstrap wycina z
templates/gitignore-kit.txt, a pliki generowane dla klientów nie mogą być ignorowane.
Obce skille z ``npx skills add`` nadal zostają ignorowane.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guides.bootstrap import find_bash
from guides.manifest import find_kit_root

KIT_ROOT = find_kit_root()
CLIENTS = "claude,codex,vscode,antigravity,opencode"
BEGIN = "# >>> instruction-kit >>>"
END = "# <<< instruction-kit <<<"
GENERATED_SKILL_DIRS = (".agents/skills", ".codex/skills", ".claude/skills")
# Ścieżki, które #526 i #527 wygenerują; sprawdzamy same reguły, bez plików.
TRACKABLE_KIT_PATHS = (
    ".claude/skills/kit-ai/.claude-plugin/plugin.json",
    ".claude/skills/kit-ai/skills/git-start/SKILL.md",
    ".opencode/commands/kit-ai/git-start.md",
)
FOREIGN_PATHS = (".agents/skills/npx-cudzy-skill/SKILL.md",)


def _kit_block(text: str) -> str:
    """Wytnij sekcję instruction-kit razem z markerami."""
    start = text.index(BEGIN)
    return text[start : text.index(END) + len(END)]


def _ignored(repo: Path, path: str) -> bool:
    """Czy git ignoruje ścieżkę według reguł .gitignore w ``repo`` (bez indeksu).

    Args:
        repo: Katalog repozytorium z plikiem .gitignore.
        path: Ścieżka względem ``repo``.

    Returns:
        bool: True, gdy reguła ją ignoruje.

    Raises:
        AssertionError: Gdy ``git check-ignore`` zwróci błąd.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--no-index", "-q", "--", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(f"git check-ignore {path}: {result.stderr}")
    return result.returncode == 0


class TestKitGitignoreSection(unittest.TestCase):
    """Sekcja kita: zgodność z szablonem i whitelista ścieżek klientów."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.workspace = root / "ws"
        cls.workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(cls.workspace)], check=True)
        env = {**os.environ, "KIT_PYTHON": sys.executable, "XDG_CONFIG_HOME": str(root / "config")}
        cls.result = subprocess.run(
            [find_bash(), str(KIT_ROOT / "scripts" / "bootstrap-project.sh"), str(cls.workspace), "--clients", CLIENTS],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_repo_block_matches_bootstrap_output(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        generated = (self.workspace / ".gitignore").read_text(encoding="utf-8")
        repo = (KIT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(_kit_block(repo), _kit_block(generated))

    def test_generated_skill_files_are_not_ignored(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        checked = 0
        for directory in GENERATED_SKILL_DIRS:
            for path in sorted((self.workspace / directory).rglob("*")):
                if not path.is_file():
                    continue
                checked += 1
                rel = path.relative_to(self.workspace).as_posix()
                with self.subTest(path=rel):
                    self.assertFalse(_ignored(self.workspace, rel))
        self.assertGreater(checked, 0)

    def test_trackable_kit_paths_are_not_ignored(self) -> None:
        for path in TRACKABLE_KIT_PATHS:
            with self.subTest(path=path):
                self.assertFalse(_ignored(KIT_ROOT, path))

    def test_foreign_agent_skills_stay_ignored(self) -> None:
        for path in FOREIGN_PATHS:
            with self.subTest(path=path):
                self.assertTrue(_ignored(KIT_ROOT, path))
