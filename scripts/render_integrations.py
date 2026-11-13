#!/usr/bin/env python3
"""Cienki wrapper: render plików integracji (orca, coderabbit) (reload / bootstrap) (#459).

Cała logika żyje w `src/guides/integrations.py` (stdlib only). Bootstrap woła ten skrypt
z `PYTHONPATH=$KIT_ROOT/src`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.integrations import main

    raise SystemExit(main(sys.argv, kit_root=kit_root))
