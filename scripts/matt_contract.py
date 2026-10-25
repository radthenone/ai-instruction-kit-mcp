#!/usr/bin/env python3
"""Cienki wrapper: kontrakt skilli Matta i ``CODING_STANDARDS.md`` (#241).

Cała logika żyje w ``src/guides/matt_contract.py``. Bootstrap woła ten skrypt
tak samo jak ``bugbot_md.py`` — z ``KIT_ROOT`` i ``TARGET`` w argumentach.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.matt_contract import main

    raise SystemExit(main())
