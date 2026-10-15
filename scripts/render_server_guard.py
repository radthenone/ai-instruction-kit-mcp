#!/usr/bin/env python3
"""Cienki wrapper: render `server-guard.json` obok guarda (reload / bootstrap).

Cała logika (parsowanie profilu, Taskfile, package.json, dopasowanie) żyje
w `src/guides/server_guard.py` (stdlib only). Bootstrap woła ten skrypt
z `PYTHONPATH=$KIT_ROOT/src`, tak samo jak przy parsowaniu `--clients`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.server_guard import main

    raise SystemExit(main(sys.argv))
