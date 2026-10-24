#!/usr/bin/env python3
"""Cienki wrapper: odśwież ``BUGBOT.md`` z zachowaniem bloku ``project:rules``.

Cała logika (render Tierów, zachowanie bloku, migracja po historii szablonu) żyje
w ``src/guides/bugbot_md.py``. Bootstrap woła ten skrypt tak samo jak
``render_server_guard.py`` — z ``KIT_ROOT`` w środowisku.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.bugbot_md import main

    raise SystemExit(main())
