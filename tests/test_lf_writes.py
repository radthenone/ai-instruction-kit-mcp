"""
Skrypty bootstrapu i kod kita muszą zapisywać pliki z końcówkami LF.

`write_text()` bez `newline="\\n"` na Windowsie tłumaczy `\\n` na `\\r\\n`,
więc repo aplikacji dostaje CRLF mimo `.gitattributes` z `eol=lf`
i `git status` pokazuje zmiany przy pustym `git diff`. CI biegnie na Linuksie,
gdzie tego nie widać — stąd test statyczny zamiast uruchomienia bootstrapu.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# `src/` też: `scripts/render_server_guard.py` to tylko wrapper na `guides.server_guard`.
DIRS = (ROOT / "scripts", ROOT / "src")


def _calls(text: str, name: str) -> list[tuple[int, str]]:
    """Wywołania `name(...)` w całości (także wieloliniowe) → `(linia, treść)`."""
    found = []
    start = text.find(name)
    while start != -1:
        depth, end = 0, start + len(name) - 1
        for end in range(start + len(name) - 1, len(text)):
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            if depth == 0:
                break
        found.append((text.count("\n", 0, start) + 1, text[start : end + 1]))
        start = text.find(name, end)
    return found


class TestLfWrites(unittest.TestCase):
    def test_every_write_text_forces_lf(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT).as_posix()}:{lineno}"
            for directory in DIRS
            for path in sorted(directory.rglob("*"))
            if path.suffix in {".py", ".sh"}
            for lineno, call in _calls(path.read_text(encoding="utf-8"), ".write_text(")
            if 'newline="\\n"' not in call
        ]
        self.assertEqual(offenders, [], "write_text bez newline=\"\\n\"")


if __name__ == "__main__":
    unittest.main()
