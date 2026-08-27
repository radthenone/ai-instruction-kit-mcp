#!/usr/bin/env python3
"""
Scal / usuń wpisy guardraili kita w `.claude/settings.json` projektu.

Użycie:
    claude_settings.py install TARGET_SETTINGS TEMPLATE_SETTINGS
    claude_settings.py prune   TARGET_SETTINGS

`.claude/settings.json` należy do użytkownika — trzyma jego `permissions`, `env`,
własne hooki. Kit dokłada tam wyłącznie swoje wpisy `PreToolUse` i tylko je zabiera
przy prune. Rozpoznaje je po ścieżce komendy (`GUARD_MARKERS`), więc reinstalacja
podmienia stare wpisy zamiast je duplikować.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Wpis należy do kita, jeśli jego komenda odwołuje się do któregoś z tych plików.
GUARD_MARKERS: tuple[str, ...] = ("invoke-hook.js", "gate-file-writes.mjs")


def is_kit_entry(entry: dict) -> bool:
    """
    Czy wpis hooka pochodzi z kita?

    Args:
        entry: Pojedynczy wpis z listy zdarzenia (`{"matcher": ..., "hooks": [...]}`).

    Returns:
        bool: ``True`` gdy którakolwiek komenda wskazuje na plik guardraila kita.
    """
    for hook in entry.get("hooks", []):
        command = str(hook.get("command", ""))
        if any(marker in command for marker in GUARD_MARKERS):
            return True
    return False


def load(path: Path) -> dict:
    """
    Wczytaj istniejący `settings.json` albo zwróć pusty obiekt.

    Args:
        path: Ścieżka do pliku ustawień.

    Returns:
        dict: Zawartość pliku; ``{}`` gdy plik nie istnieje albo jest nieczytelny.
    """
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def strip_kit_entries(settings: dict) -> dict:
    """
    Usuń z ustawień wszystkie wpisy hooków należące do kita.

    Puste listy zdarzeń i pusty blok ``hooks`` znikają, żeby nie zostawiać śmieci
    po odznaczeniu klienta.

    Args:
        settings: Ustawienia do oczyszczenia (modyfikowane w miejscu).

    Returns:
        dict: Te same ustawienia, bez wpisów kita.
    """
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings

    for event in list(hooks):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        kept = [e for e in entries if not (isinstance(e, dict) and is_kit_entry(e))]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]

    if not hooks:
        del settings["hooks"]
    return settings


def write(path: Path, settings: dict) -> None:
    """
    Zapisz ustawienia albo usuń plik, gdy nic w nim nie zostało.

    Args:
        path: Ścieżka docelowa.
        settings: Ustawienia do zapisania.
    """
    if not settings:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    mode, target = argv[1], Path(argv[2])
    settings = strip_kit_entries(load(target))

    if mode == "prune":
        write(target, settings)
        return 0

    if mode != "install" or len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2

    template = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    hooks = settings.setdefault("hooks", {})
    for event, entries in template.get("hooks", {}).items():
        hooks.setdefault(event, []).extend(entries)

    write(target, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
