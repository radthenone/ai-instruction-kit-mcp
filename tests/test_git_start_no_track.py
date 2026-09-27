"""
Branch feature nie może śledzić gałęzi integracyjnej.

`git checkout -b X origin/dev` ustawia upstream X na `origin/dev`, więc push/Sync
w IDE wysyła commity prosto na `dev` z pominięciem PR (olivin-app #232).
Każde polecenie tworzące branch w instrukcjach git-start musi mieć `--no-track`.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    KIT_ROOT / "templates" / "shared" / "agents" / "git-start.md",
    KIT_ROOT / "instructions" / "git-start.md",
]


class TestGitStartNoTrack(unittest.TestCase):
    def test_branch_creation_does_not_track_base(self) -> None:
        offenders = [
            f"{path.relative_to(KIT_ROOT).as_posix()}:{lineno}"
            for path in SOURCES
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"git (checkout -b|switch -c)\s", line) and "--no-track" not in line
        ]
        self.assertEqual(offenders, [], "tworzenie brancha bez --no-track")


if __name__ == "__main__":
    unittest.main()
