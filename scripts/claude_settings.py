#!/usr/bin/env python3
"""
Scal / usuń wpisy guardraili kita w `.claude/settings.json` projektu.

Użycie:
    claude_settings.py install TARGET_SETTINGS TEMPLATE_SETTINGS
    claude_settings.py prune   TARGET_SETTINGS

`.claude/settings.json` należy do użytkownika — trzyma jego `permissions`, `env`,
własne hooki. Kit dokłada tam wyłącznie swoje wpisy hooków (PreToolUse, PostToolUse,
SessionStart) i tylko je zabiera przy prune. Rozpoznaje je po ścieżce komendy
(`GUARD_MARKERS`), więc reinstalacja podmienia stare wpisy zamiast je duplikować.
Markery starych Guardów (`gate-*`, `invoke-hook.js`) zostają, żeby reinstalacja
sprzątała wpisy z Workspace'ów bootstrapowanych przed Guards v2.

Poza hookami kit dokłada marketplace i plugin Superpowers (`KIT_PLUGIN_SETTINGS`), żeby
Claude Code sam zaproponował instalację przy otwarciu repo, oraz `env.MCP_TIMEOUT` — przy
zimnym cache uvx build guides-mcp trwa dłużej niż domyślne 30 s startu serwera MCP. Wpis, który użytkownik już ma
(np. `false` w `enabledPlugins`), zostaje; prune zabiera tylko wpisy równe kitowym.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Wpis należy do kita, jeśli jego komenda odwołuje się do któregoś z tych plików.
GUARD_MARKERS: tuple[str, ...] = (
    "git-guard.mjs",
    "bash-guard.mjs",
    "sensitive-files-guard.mjs",
    "linters-guard.mjs",
    "rtk-check.mjs",
    # Guards v1 — tylko do prune przy reinstalacji.
    "invoke-hook.js",
    "gate-file-writes.mjs",
    "gate-push.sh",
    "gate-destructive.sh",
)


# Klucze ustawień Claude Code dokładane obok hooków — nazwa → wartość kita.
KIT_PLUGIN_SETTINGS: dict[str, dict] = {
    "extraKnownMarketplaces": {
        "superpowers-marketplace": {
            "source": {"source": "github", "repo": "obra/superpowers-marketplace"}
        }
    },
    "enabledPlugins": {"superpowers@superpowers-marketplace": True},
    "env": {"MCP_TIMEOUT": "90000"},
}


def strip_kit_plugins(settings: dict) -> dict:
    """
    Usuń wpisy marketplace/pluginów kita, o ile użytkownik ich nie zmienił.

    Args:
        settings: Ustawienia do oczyszczenia (modyfikowane w miejscu).

    Returns:
        dict: Te same ustawienia; pusty blok po usunięciu znika.
    """
    for key, entries in KIT_PLUGIN_SETTINGS.items():
        block = settings.get(key)
        if not isinstance(block, dict):
            continue
        for name, value in entries.items():
            if block.get(name) == value:
                del block[name]
        if not block:
            del settings[key]
    return settings


def merge_kit_plugins(settings: dict) -> dict:
    """
    Dołóż wpisy marketplace/pluginów kita bez nadpisywania wartości użytkownika.

    Args:
        settings: Ustawienia (modyfikowane w miejscu).

    Returns:
        dict: Te same ustawienia z wpisami kita.
    """
    for key, entries in KIT_PLUGIN_SETTINGS.items():
        block = settings.get(key)
        if not isinstance(block, dict):
            block = settings[key] = {}
        for name, value in entries.items():
            block.setdefault(name, value)
    return settings


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
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    mode, target = argv[1], Path(argv[2])
    settings = strip_kit_entries(load(target))

    if mode == "prune":
        write(target, strip_kit_plugins(settings))
        return 0

    if mode != "install" or len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2

    template = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    hooks = settings.setdefault("hooks", {})
    for event, entries in template.get("hooks", {}).items():
        hooks.setdefault(event, []).extend(entries)

    write(target, merge_kit_plugins(settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
