"""
Pomocnicze funkcje dla suit, które odpalają bash / node jako podproces.

Nie jest modułem testowym (nie pasuje do `test_*.py`), więc discovery go pomija;
importują go `test_bootstrap.py`, `test_generated_artifacts.py`, `test_shell_suites.py`.
"""

from __future__ import annotations

import os
from pathlib import Path


def is_ci() -> bool:
    """
    Czy działamy na CI (GitHub Actions ustawia ``CI=true``)?

    Na CI brak wymaganego narzędzia jest błędem, nie skipem — cichy skip odtworzyłby
    lukę, przez którą te suity latami nie wykonywały się w pipeline.

    Returns:
        bool: ``True`` gdy ``CI`` ustawione na coś innego niż ``0`` / ``false``.
    """
    value = os.environ.get("CI", "").strip().lower()
    return value not in ("", "0", "false")


def posix_path(path: Path) -> str:
    """
    Ścieżka w formie akceptowanej przez bash także na Windows (Git Bash).

    Args:
        path: Ścieżka do skryptu.

    Returns:
        str: Ścieżka z ukośnikami ``/``.
    """
    return str(path).replace("\\", "/")


def resolve_bash() -> str | None:
    """
    Znajdź bash do testów: na Windows preferuj Git Bash, inaczej PATH.

    Returns:
        str | None: Ścieżka do bash albo ``None`` gdy niedostępny.
    """
    if os.name == "nt":
        candidates = [
            Path(r"C:/Program Files/Git/bin/bash.exe"),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Git"
            / "bin"
            / "bash.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    found = shutil.which("bash")
    return found
