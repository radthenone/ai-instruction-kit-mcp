#!/usr/bin/env python3
"""Cienki wrapper: render `.ai/worktree.json` (reload / bootstrap).

Cała logika żyje w `src/guides/worktree.py` (stdlib only). Bootstrap woła ten skrypt
z `PYTHONPATH=$KIT_ROOT/src`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.worktree import main

    raise SystemExit(main(sys.argv))
