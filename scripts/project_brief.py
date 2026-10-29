#!/usr/bin/env python3
"""Render the project brief from the Profil and overlay (#307).

Thin wrapper: the whole logic lives in ``guides.resolver.render_project_brief``, so
``AGENTS.md`` and the MCP server instructions consume exactly the same values.
Bootstrap calls this with ``WORKSPACE`` (real repo) and ``LANGUAGE`` in the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    kit_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(kit_root / "src"))
    from guides.resolver import resolve_workspace_profile

    workspace = Path(os.environ["WORKSPACE"])
    resolved = resolve_workspace_profile(
        workspace,
        kit_root=kit_root,
        language_override=os.environ.get("LANGUAGE") or None,
    )
    sys.stdout.write(resolved.project_brief.rstrip("\n") + "\n")
