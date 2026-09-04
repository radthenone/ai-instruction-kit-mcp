#!/usr/bin/env python3
"""
Zainstaluj templates/shared/agents/*.md jako natywne skille Codexa.

Użycie:
    install_agent_skills.py SRC_DIR DEST_DIR

Codex nie ma formatu custom prompts (.codex/agents/*.toml) — został wycofany
w Codex CLI. Natywny mechanizm Codexa to skille: katalog <nazwa>/SKILL.md.
Ten skrypt zamienia płaskie pliki agentów (frontmatter + treść) na katalogi
skilli; treść zostaje nietknięta (SKILL.md == plik źródłowy bajt w bajt).

Nazwa skilla = stem pliku (kebab-case), spójnie z nazwą komendy /nazwa
u klientów, którzy mają slash commands (Cursor, Claude).
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    src_dir, dest_dir = Path(argv[1]), Path(argv[2])
    if not src_dir.is_dir():
        print(f"Brak katalogu {src_dir}", file=sys.stderr)
        return 1
    files = sorted(src_dir.glob("*.md"))
    if not files:
        # Puste źródło to poprawny stan (kit bez agentów) — jak w install_shared_skills.
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for md in files:
        skill_dir = dest_dir / md.stem
        skill_dir.mkdir(parents=True, exist_ok=True)
        # Kopia bajt w bajt — dogfood test porównuje ze źródłem.
        (skill_dir / "SKILL.md").write_bytes(md.read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
