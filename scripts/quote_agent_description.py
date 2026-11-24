#!/usr/bin/env python3
"""
Zacytuj ``description:`` we frontmatterze kopii agenta Claude (#547).

Użycie:
    quote_agent_description.py FILE

Surowy opis z " #" albo ": " YAML czyta jako komentarz albo błąd, więc Claude dostaje
ucięty opis. ``json.dumps`` daje poprawny skalar YAML, tak jak ``render_claude``
w render_agent_commands.py. Bez PyYAML — bootstrap działa na systemowym Pythonie.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def quote_description(text: str) -> str:
    """
    Zapisz wartość ``description:`` we frontmatterze jako skalar JSON.

    Wartość już zacytowana zostaje bez zmian.

    Args:
        text: Treść pliku agenta z frontmatterem między liniami ``---``.

    Returns:
        str: Ta sama treść z zacytowanym ``description:``; reszta bez zmian.
    """
    lines = text.splitlines(keepends=True)
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    for i in range(1, end):
        if lines[i].startswith("description:"):
            value = lines[i].partition(":")[2].strip()
            if value[:1] not in ('"', "'"):
                lines[i] = f"description: {json.dumps(value, ensure_ascii=False)}\n"
    return "".join(lines)


def main(argv: list[str]) -> int:
    """
    Punkt wejścia CLI: cytuje ``description:`` w pliku na miejscu.

    Args:
        argv: Argumenty z sys.argv: program i FILE.

    Returns:
        int: Kod wyjścia.
    """
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    path = Path(argv[1])
    path.write_text(quote_description(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
