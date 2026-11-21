#!/usr/bin/env python3
"""
Zainstaluj templates/shared/agents/*.md jako natywne skille Codexa lub Antigravity.

Użycie:
    install_agent_skills.py SRC_DIR DEST_DIR [TARGET]

Natywny mechanizm Codexa i Antigravity to skille: katalog <nazwa>/SKILL.md.
Podstawia placeholdery prefiksu (@KIT_CMD_PREFIX@, @KIT_NAME_PREFIX@) per cel (#525, #529).
"""

from __future__ import annotations

import sys
from pathlib import Path

from command_prefix import copy_template

MANIFEST = Path(__file__).resolve().parents[1] / "manifest.yaml"


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 1
    src_dir, dest_dir = Path(argv[1]), Path(argv[2])
    resolved_parts = dest_dir.resolve().parts
    target = argv[3] if len(argv) == 4 else ("codex" if ".codex" in resolved_parts else ("antigravity" if ".agents" in resolved_parts else ("antigravity" if "agents" in resolved_parts else "codex")))
    if not src_dir.is_dir():
        print(f"Brak katalogu {src_dir}", file=sys.stderr)
        return 1
    files = sorted(src_dir.glob("*.md"))
    if not files:
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for md in files:
        skill_dir = dest_dir / md.stem
        skill_dir.mkdir(parents=True, exist_ok=True)
        copy_template(MANIFEST, target, md, skill_dir / "SKILL.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
