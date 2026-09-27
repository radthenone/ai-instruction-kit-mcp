"""
Skrypty bootstrapu muszą zapisywać pliki z końcówkami LF.

`write_text()` bez `newline="\\n"` na Windowsie tłumaczy `\\n` na `\\r\\n`,
więc repo aplikacji dostaje CRLF mimo `.gitattributes` z `eol=lf`
i `git status` pokazuje zmiany przy pustym `git diff`. CI biegnie na Linuksie,
gdzie tego nie widać — stąd test statyczny zamiast uruchomienia bootstrapu.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


class TestLfWrites(unittest.TestCase):
    def test_every_write_text_forces_lf(self) -> None:
        offenders = [
            f"{path.name}:{lineno}"
            for path in sorted(SCRIPTS.iterdir())
            if path.suffix in {".py", ".sh"}
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"\.write_text\(", line) and 'newline="\\n"' not in line
        ]
        self.assertEqual(offenders, [], "write_text bez newline=\"\\n\"")


if __name__ == "__main__":
    unittest.main()
