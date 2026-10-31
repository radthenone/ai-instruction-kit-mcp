#!/usr/bin/env python3
"""
Scal / usuń wpisy guardraili kita w `.claude/settings.json` projektu.

Użycie:
    claude_settings.py install    TARGET_SETTINGS TEMPLATE_SETTINGS
    claude_settings.py prune      TARGET_SETTINGS
    claude_settings.py sync-local TARGET_LOCAL_SETTINGS [HOST_PROFILE]

`.claude/settings.json` należy do użytkownika — trzyma jego `permissions`, `env`,
własne hooki. Kit dokłada tam wyłącznie swoje wpisy hooków (PreToolUse, PostToolUse,
SessionStart) i tylko je zabiera przy prune. Rozpoznaje je po ścieżce komendy
(`GUARD_MARKERS`), więc reinstalacja podmienia stare wpisy zamiast je duplikować.
Markery starych Guardów (`gate-*`, `invoke-hook.js`) zostają, żeby reinstalacja
sprzątała wpisy z Workspace'ów bootstrapowanych przed Guards v2.

Poza hookami kit dokłada marketplace i plugin Superpowers (`get_kit_plugin_settings`), żeby
Claude Code sam zaproponował instalację przy otwarciu repo, oraz `env.MCP_TIMEOUT` — przy
zimnym cache uvx build guides-mcp trwa dłużej niż domyślne 30 s startu serwera MCP — a także
`env.PONYTAIL_SUBAGENT_MATCHER` zawężający plugin ponytail do agentów kodu. Wpis, który użytkownik już ma
(np. `false` w `enabledPlugins` lub własny matcher), zostaje; prune zabiera tylko wpisy równe kitowym.
Matcher w postaci kita (`^(?!(?:...)$).*`) to wpis kita także ze starej listy agentów: install go
odświeża, prune zdejmuje.

`sync-local` obsługuje `.claude/settings.local.json`: na hoście VPS dodaje `PONYTAIL_DEFAULT_MODE=off`
ze znacznikiem `KIT_MANAGED_PONYTAIL_DEFAULT_MODE`, a na local zdejmuje tylko wpis ze znacznikiem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = KIT_ROOT / "templates" / "shared" / "agents"
sys.path.insert(0, str(KIT_ROOT / "src"))
from guides.agent_classes import KIT_MATCHER_RE, ponytail_matcher  # noqa: E402

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


MATCHER_KEY = "PONYTAIL_SUBAGENT_MATCHER"


def build_ponytail_matcher(agents_dir: Path | None = None) -> str:
    """Matcher kita dla `PONYTAIL_SUBAGENT_MATCHER` (domyślnie z szablonów agentów kita)."""
    return ponytail_matcher(agents_dir or AGENTS_DIR)


def is_kit_matcher(value: object) -> bool:
    """Czy wartość matchera ma postać wyrenderowaną przez kit (także ze starej listy agentów)?"""
    return isinstance(value, str) and KIT_MATCHER_RE.fullmatch(value) is not None


def get_kit_plugin_settings(agents_dir: Path | None = None) -> dict[str, dict]:
    """
    Zwróć słownik ustawień wstrzykiwanych przez kita (pluginy, env).

    Args:
        agents_dir: Opcjonalna ścieżka do szablonów agentów.

    Returns:
        dict[str, dict]: Mapa klucz -> ustawienia kita.
    """
    return {
        "extraKnownMarketplaces": {
            "superpowers-marketplace": {
                "source": {"source": "github", "repo": "obra/superpowers-marketplace"}
            }
        },
        "enabledPlugins": {"superpowers@superpowers-marketplace": True},
        "env": {
            "MCP_TIMEOUT": "90000",
            "PONYTAIL_SUBAGENT_MATCHER": build_ponytail_matcher(agents_dir),
        },
    }


def strip_kit_plugins(settings: dict, agents_dir: Path | None = None) -> dict:
    """
    Usuń wpisy marketplace/pluginów kita, o ile użytkownik ich nie zmienił.

    Args:
        settings: Ustawienia do oczyszczenia (modyfikowane w miejscu).
        agents_dir: Opcjonalny katalog szablonów agentów.

    Returns:
        dict: Te same ustawienia; pusty blok po usunięciu znika.
    """
    plugin_settings = get_kit_plugin_settings(agents_dir)
    for key, entries in plugin_settings.items():
        block = settings.get(key)
        if not isinstance(block, dict):
            continue
        for name, value in entries.items():
            current = block.get(name)
            if current == value or (name == MATCHER_KEY and is_kit_matcher(current)):
                del block[name]
        if not block:
            del settings[key]
    return settings


def merge_kit_plugins(settings: dict, agents_dir: Path | None = None) -> dict:
    """
    Dołóż wpisy marketplace/pluginów kita bez nadpisywania wartości użytkownika.

    Args:
        settings: Ustawienia (modyfikowane w miejscu).
        agents_dir: Opcjonalny katalog szablonów agentów.

    Returns:
        dict: Te same ustawienia z wpisami kita.
    """
    plugin_settings = get_kit_plugin_settings(agents_dir)
    for key, entries in plugin_settings.items():
        block = settings.get(key)
        if not isinstance(block, dict):
            block = settings[key] = {}
        for name, value in entries.items():
            if name == MATCHER_KEY and is_kit_matcher(block.get(name)):
                block[name] = value  # stara wartość kita → odśwież; ręczna zostaje
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


MODE_KEY = "PONYTAIL_DEFAULT_MODE"
# Znacznik pochodzenia: obecny = `PONYTAIL_DEFAULT_MODE` wpisał kit, więc kit może go zdjąć.
MODE_MARKER_KEY = "KIT_MANAGED_PONYTAIL_DEFAULT_MODE"


def sync_local_settings(target: Path, host_profile: str | None = None) -> None:
    """
    Zsynchronizuj `.claude/settings.local.json` zależnie od profilu hosta (vps / local).

    Na VPS: dopisuje `PONYTAIL_DEFAULT_MODE=off` i znacznik kita, gdy użytkownik nie ustawił
    trybu sam. Na local: zdejmuje tryb tylko razem ze znacznikiem kita — ręczny wpis zostaje.
    Brak modułu wykrywania hosta: plik bez zmian i ostrzeżenie na stderr.

    Args:
        target: Ścieżka do .claude/settings.local.json.
        host_profile: 'vps' | 'local' albo None (autodetekcja).
    """
    if host_profile is None:
        try:
            from guides.host_profile import detect_host_profile
        except ImportError as exc:
            print(f"claude_settings: nie wykryto hosta ({exc}) — {target} bez zmian", file=sys.stderr)
            return
        host_profile = detect_host_profile()

    settings = load(target)
    env = settings.get("env")
    if not isinstance(env, dict):
        env = {}
    if host_profile == "vps":
        if MODE_KEY not in env:
            env[MODE_KEY] = "off"
            env[MODE_MARKER_KEY] = "1"
    elif env.pop(MODE_MARKER_KEY, None) is not None:
        env.pop(MODE_KEY, None)
    if env:
        settings["env"] = env
    else:
        settings.pop("env", None)
    write(target, settings)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    mode, target = argv[1], Path(argv[2])

    if mode == "sync-local":
        host_profile = argv[3] if len(argv) > 3 else None
        sync_local_settings(target, host_profile)
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
