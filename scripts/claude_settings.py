#!/usr/bin/env python3
"""
Scal / usuń wpisy guardraili kita w `.claude/settings.json` projektu.

Użycie:
    claude_settings.py install     TARGET_SETTINGS TEMPLATE_SETTINGS
    claude_settings.py prune       TARGET_SETTINGS
    claude_settings.py sync-local  TARGET_LOCAL_SETTINGS
    claude_settings.py prune-local TARGET_LOCAL_SETTINGS

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

`env.PONYTAIL_SUBAGENT_MATCHER` (zawężenie pluginu ponytail do agentów kodu, #316) kit trzyma
w `.claude/settings.local.json` — poza gitem, bo lista agentów zależy od wersji kita.
`sync-local` go dopisuje (wartość w postaci kita `^(?!(?:...)$).*` odświeża, ręczną zostawia),
`prune-local` zdejmuje tylko postać kita. Matcher kita, który wcześniej trafił do
`settings.json`, install i prune stamtąd usuwają; ręczna wartość zostaje w obu plikach.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = KIT_ROOT / "templates" / "shared" / "agents"
sys.path.insert(0, str(KIT_ROOT / "src"))
from guides.agent_classes import KIT_MATCHER_RE, MATCHER_KEY, ponytail_matcher  # noqa: E402

# Wpis należy do kita, jeśli jego komenda odwołuje się do któregoś z tych plików.
GUARD_MARKERS: tuple[str, ...] = (
    "git-guard.mjs",
    "bash-guard.mjs",
    "sensitive-files-guard.mjs",
    "server-guard.mjs",
    "linters-guard.mjs",
    "rtk-check.mjs",
    "language-reminder.mjs",
    "kit-doctor-reminder.mjs",
    # Guards v1 — tylko do prune przy reinstalacji.
    "invoke-hook.js",
    "gate-file-writes.mjs",
    "gate-push.sh",
    "gate-destructive.sh",
)



def build_ponytail_matcher(agents_dir: Path | None = None) -> str:
    """Matcher kita dla `PONYTAIL_SUBAGENT_MATCHER` (domyślnie z szablonów agentów kita)."""
    return ponytail_matcher(agents_dir or AGENTS_DIR)


def is_kit_matcher(value: object) -> bool:
    """Czy wartość matchera ma postać wyrenderowaną przez kit (także ze starej listy agentów)?"""
    return isinstance(value, str) and KIT_MATCHER_RE.fullmatch(value) is not None


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


def drop_kit_matcher(settings: dict) -> dict:
    """
    Zdejmij z `env` matcher ponytaila w postaci kita; ręczna wartość zostaje.

    Args:
        settings: Ustawienia (modyfikowane w miejscu).

    Returns:
        dict: Te same ustawienia; pusty `env` znika.
    """
    env = settings.get("env")
    if isinstance(env, dict) and is_kit_matcher(env.get(MATCHER_KEY)):
        del env[MATCHER_KEY]
        if not env:
            del settings["env"]
    return settings


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
    return drop_kit_matcher(settings)


def merge_kit_plugins(settings: dict) -> dict:
    """
    Dołóż wpisy marketplace/pluginów kita bez nadpisywania wartości użytkownika.

    Args:
        settings: Ustawienia (modyfikowane w miejscu).

    Returns:
        dict: Te same ustawienia z wpisami kita.
    """
    drop_kit_matcher(settings)  # matcher żyje w settings.local.json (#316)
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
    Wczytaj istniejący plik ustawień albo zwróć pusty obiekt.

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
    if path.is_file() and load(path) == settings:
        # Ta sama treść (kolejność kluczy bez znaczenia) — bez przepisywania, żeby
        # drugi reload nie zmieniał pliku samą kolejnością (#279).
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def sync_local_settings(target: Path) -> None:
    """
    Dopisz matcher ponytaila kita do `env` w `.claude/settings.local.json`.

    Wartość w postaci kita (także ze starej listy agentów) odświeża; ręczną zostawia.

    Args:
        target: Ścieżka do `.claude/settings.local.json`.
    """
    settings = load(target)
    if not settings and target.is_file() and target.read_text(encoding="utf-8", errors="replace").strip() not in ("", "{}"):
        # Prywatny plik użytkownika (uprawnienia) — nieczytelnego nie nadpisujemy.
        print(f"claude_settings: {target} nieczytelny — matcher ponytaila pominięty", file=sys.stderr)
        return
    env = settings.get("env")
    if not isinstance(env, dict):
        env = settings["env"] = {}
    if MATCHER_KEY not in env or is_kit_matcher(env[MATCHER_KEY]):
        env[MATCHER_KEY] = build_ponytail_matcher()
    write(target, settings)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    mode, target = argv[1], Path(argv[2])

    if mode == "sync-local":
        sync_local_settings(target)
        return 0
    if mode == "prune-local":
        # Zapis tylko po zdjęciu matchera kita — nieczytelny albo cudzy plik zostaje.
        local = load(target)
        env = local.get("env")
        if isinstance(env, dict) and is_kit_matcher(env.get(MATCHER_KEY)):
            write(target, drop_kit_matcher(local))
        return 0

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
