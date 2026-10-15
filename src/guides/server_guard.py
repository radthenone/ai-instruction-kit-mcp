"""Render i dopasowanie server-guarda (VPS) — stdlib only.

Ten moduł jest **jedynym źródłem** domyślnej listy deny kita i logiki
dopasowania po stronie reloadu (rozwijanie wrapperów). Runtime guard
(`templates/shared/guards/server-guard.mjs`) ma wbudowaną kopię tej samej
tabeli na wypadek braku JSON-a; test parzystości porównuje obie implementacje.

Dopasowanie (identyczne w JS i tu):
  - komenda dzielona na segmenty po `&&`, `||`, `;`, `|`, `&`, `(`, `)`,
    plus wnętrza `bash -c` / `sh -c` i `$( … )` jako osobne segmenty,
  - z początku segmentu zdejmowane prefiksy: `sudo` (z flagami), przypisania
    `VAR=…`, `env`, `nice`, `ionice`, `timeout` (z flagami i limitem), `nohup`,
    `time`, `command`, `exec`, `xargs` — pętla aż do stabilizacji,
  - wzorce kotwiczone na początku segmentu (`^\\s*…(\\s|$)`), `allow` wygrywa z `deny`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

GUARD_OFF = "off"
GUARD_AUTO = "auto"

CONFIG_VERSION = 1

KNOWN_SERVER_KEYS = ("guard", "deny", "allow")

# Wzorce w składni wspólnej dla Pythona (`re`) i JS (`RegExp`): kotwica `^\\s*`,
# spacje jako `\\s+`, koniec `(?=\\s|$)`. Bez lookbehind, bez flag inline.
DEFAULTS: tuple[dict[str, str], ...] = (
    # Kontenery — deny wszystko poza kolumną allow.
    {"id": "docker", "kind": "deny", "pattern": r"^\s*docker(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "docker-compose", "kind": "deny", "pattern": r"^\s*docker\s+compose(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "docker-compose-bin", "kind": "deny", "pattern": r"^\s*docker-compose(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "podman", "kind": "deny", "pattern": r"^\s*podman(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "docker-ps", "kind": "allow", "pattern": r"^\s*docker\s+(ps|images|inspect|version|info)(?=\s|$)",
     "reason": "odczyt stanu kontenerów"},
    {"id": "docker-logs", "kind": "allow", "pattern": r"^\s*docker\s+logs(?=\s|$)(?!.*(?:-f|--follow)\b)",
     "reason": "odczyt logów bez follow"},
    {"id": "docker-logs-follow", "kind": "deny", "pattern": r"^\s*docker\s+logs(?=\s|$).*?(?:-f|--follow)\b",
     "reason": "follow logów trzyma proces i strumień — użyj `docker logs` bez `-f`"},
    {"id": "docker-compose-ps", "kind": "deny", "pattern": r"^\s*docker\s+compose\s+config(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "docker-compose-ps-allow", "kind": "allow", "pattern": r"^\s*docker(?:\s+|-)compose\s+ps(?=\s|$)",
     "reason": "odczyt stanu kontenerów"},
    # Paczki — instalacja kompiluje zależności natywne; lockfile zmienia się na PC albo w CI.
    {"id": "uv-sync", "kind": "deny", "pattern": r"^\s*uv\s+(sync|add|remove|lock)(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
    {"id": "uv-pip-install", "kind": "deny", "pattern": r"^\s*uv\s+pip\s+install(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
    {"id": "pip-install", "kind": "deny", "pattern": r"^\s*pip3?\s+install(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — zależności zmieniają się na PC albo w CI"},
    {"id": "uv-run", "kind": "deny", "pattern": r"^\s*uv\s+run(?=\s|$)(?!.*--no-sync)",
     "reason": "`uv run` bez `--no-sync` synchronizuje i kompiluje — użyj `uv run --no-sync` albo `UV_NO_SYNC=1`"},
    {"id": "uv-run-no-sync", "kind": "allow", "pattern": r"^\s*uv\s+run(?=\s|$).*?--no-sync",
     "reason": "uruchomienie bez synchronizacji"},
    {"id": "uvx", "kind": "allow", "pattern": r"^\s*uvx(?=\s|$)",
     "reason": "jednorazowe narzędzia bez instalacji do projektu"},
    {"id": "bun-pkg", "kind": "deny", "pattern": r"^\s*bun\s+(install|add|remove)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "npm-pkg", "kind": "deny", "pattern": r"^\s*npm\s+(install|i|ci)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "pnpm-pkg", "kind": "deny", "pattern": r"^\s*pnpm\s+(install|i|add)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "yarn-pkg", "kind": "deny", "pattern": r"^\s*yarn\s+(install|add)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
    # Buildy produkcyjne — tylko w CI.
    {"id": "next-build", "kind": "deny", "pattern": r"^\s*next\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `tsc --noEmit`"},
    {"id": "expo-build", "kind": "deny", "pattern": r"^\s*expo\s+(prebuild|export)(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "eas-build", "kind": "deny", "pattern": r"^\s*eas\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "vite-build", "kind": "deny", "pattern": r"^\s*vite\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "turbo-build", "kind": "deny", "pattern": r"^\s*turbo\s+(run\s+)?build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `turbo run lint` / `typecheck`"},
    {"id": "turbo-lint", "kind": "allow", "pattern": r"^\s*turbo\s+run\s+(lint|typecheck)(?=\s|$)",
     "reason": "lekkie bramki na VPS"},
    # Przeglądarki / e2e — setki MB na instancję, tylko w CI.
    {"id": "playwright", "kind": "deny", "pattern": r"^\s*(npx\s+|bunx\s+|yarn\s+dlx\s+|pnpm\s+dlx\s+)?playwright(?=\s|$)",
     "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
    {"id": "cypress", "kind": "deny", "pattern": r"^\s*(npx\s+|bunx\s+)?cypress(?=\s|$)",
     "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
    {"id": "maestro", "kind": "deny", "pattern": r"^\s*maestro(?=\s|$)",
     "reason": "testy mobilne tylko w CI"},
    # Mnożenie procesów na słabym CPU.
    {"id": "pytest-xdist", "kind": "deny", "pattern": r"^\s*pytest(?=\s|$).*?(?:-n\b|--numprocesses\b)",
     "reason": "xdist mnoży procesy na słabym CPU — użyj `pytest` bez `-n`"},
)

_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|&()\n]")
_BASH_C = re.compile(r"(?:^|\s)(?:bash|sh)\s+-c\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))")
_SUBSHELL = re.compile(r"\$\(\s*(.*?)\s*\)")

_PREFIXES = (
    re.compile(r"^\s*sudo\b\s*(?:(?:-[ugpCDhrtU]\s+\S+|-\S+)\s+)*"),
    re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+)+"),
    re.compile(r"^\s*env\b\s*"),
    re.compile(r"^\s*(?:nice|ionice|nohup|time|command|exec|xargs)\b\s*(?:-\S+(?:\s+\d+)?\s+)*"),
    re.compile(r"^\s*timeout\b\s*(?:(?:-[^\s]+|[\d.]+[smhd]?)\s+)*"),
)


def warn(message: str) -> None:
    """Ostrzeżenie — nigdy nie przerywa renderu (ADR-0004)."""
    print(f"server-guard: {message}", file=sys.stderr)


def split_segments(command: str) -> list[str]:
    """Podziel komendę na segmenty + wnętrza `bash -c` / `$(…)`."""
    segments = [seg for seg in _SEGMENT_SPLIT.split(command.replace("\r", " ")) if seg.strip()]
    extra: list[str] = []
    for seg in segments:
        for match in _BASH_C.finditer(seg):
            inner = next((g for g in match.groups() if g), "")
            if inner.strip():
                extra.extend(split_segments(inner))
        for match in _SUBSHELL.finditer(seg):
            if match.group(1).strip():
                extra.extend(split_segments(match.group(1)))
    return segments + extra


def strip_prefixes(segment: str) -> str:
    """Zdejmij prefiksy uruchamiające inną komendę (`sudo`, `env`, `timeout`, …)."""
    previous = None
    current = segment
    while previous != current:
        previous = current
        for pattern in _PREFIXES:
            current = pattern.sub("", current, count=1)
    return current


def literal_pattern(command: str) -> str:
    """Wzorzec dosłownego wywołania (wrappery, `server.deny`/`server.allow`)."""
    return r"^\s*" + r"\s+".join(re.escape(tok) for tok in command.split()) + r"(?=\s|$)"


def match_rules(
    segment: str,
    rules: list[dict[str, str]],
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    """Pierwszy pasujący deny i pierwszy pasujący allow w segmencie."""
    stripped = strip_prefixes(segment)
    deny_hit = allow_hit = None
    for rule in rules:
        try:
            matched = re.search(rule["pattern"], stripped) is not None
        except re.error:
            continue
        if not matched:
            continue
        if rule["kind"] == "allow" and allow_hit is None:
            allow_hit = rule
        elif rule["kind"] == "deny" and deny_hit is None:
            deny_hit = rule
    return deny_hit, allow_hit


def check_command(
    command: str,
    rules: list[dict[str, str]],
) -> tuple[bool, dict[str, str] | None, str]:
    """Czy komenda denied? Zwraca `(denied, reguła, segment)` — allow wygrywa z deny."""
    for segment in split_segments(command):
        deny_hit, allow_hit = match_rules(segment, rules)
        if deny_hit is not None and allow_hit is None:
            return True, deny_hit, segment.strip()
    return False, None, ""


# --- Profil (`server:`) -------------------------------------------------------


def parse_server_section(text: str) -> dict:
    """Wyciągnij sekcję `server:` z profilu (tolerancyjny podzbiór YAML).

    Returns:
        dict: `{"guard", "deny", "allow", "warnings"}` — brak sekcji to `guard: auto`.
    """
    result: dict = {"guard": GUARD_AUTO, "deny": [], "allow": [], "warnings": []}
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "server:" and len(line) - len(line.lstrip()) == 0:
            start = i
            break
    if start is None:
        return result

    current_list = None
    for line in lines[start + 1:]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        stripped = line.strip()
        if indent == 2 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key not in KNOWN_SERVER_KEYS:
                result["warnings"].append(f"nieznany klucz `server.{key}` — pominięto")
                current_list = None
            elif key == "guard":
                if value in (GUARD_AUTO, GUARD_OFF):
                    result["guard"] = value
                else:
                    result["warnings"].append(
                        f"zły typ/wartość `server.guard: {value}` — ma być `auto` albo `off`"
                    )
                current_list = None
            elif value:
                result["warnings"].append(f"zły typ `server.{key}: {value}` — ma być listą")
                current_list = None
            else:
                current_list = key
        elif stripped.startswith("-") and current_list:
            item = stripped[1:].strip().strip("'\"")
            if item:
                result[current_list].append(item)
        elif indent == 2:
            current_list = None
    return result


# --- Taskfile / package.json --------------------------------------------------


def collect_taskfile_commands(path: Path, seen: set[Path] | None = None) -> dict[str, list[str]]:
    """Task → komendy shellowe (z `includes`, rekurencyjnie przez `task:`, cyklo-odpornie)."""
    seen = seen if seen is not None else set()
    resolved = path.resolve()
    if resolved in seen or not resolved.is_file():
        return {}
    seen.add(resolved)
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return {}

    section: str | None = None
    current_task: str | None = None
    in_cmds = False
    cmds_indent = 0
    raw: dict[str, list] = {}
    includes: dict[str, str] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped in ("tasks:", "includes:"):
            section = stripped[:-1]
            current_task = None
            in_cmds = False
            continue
        if section == "includes" and indent == 2 and ":" in stripped:
            name, _, value = stripped.partition(":")
            includes[name.strip()] = value.strip().strip("'\"")
        elif section == "tasks" and indent == 2 and stripped.endswith(":"):
            current_task = stripped[:-1].strip()
            raw.setdefault(current_task, [])
            in_cmds = False
        elif section == "tasks" and current_task and indent == 4 and stripped == "cmds:":
            in_cmds = True
            cmds_indent = indent
        elif section == "tasks" and current_task and in_cmds and indent > cmds_indent:
            if stripped.startswith("- "):
                item = stripped[2:].strip().strip("'\"")
                if item.startswith("task:"):
                    raw[current_task].append({"task": item[5:].strip().strip("'\"")})
                else:
                    raw[current_task].append(item)
            elif stripped.startswith("task:"):
                raw[current_task].append({"task": stripped[5:].strip().strip("'\"")})
            elif stripped.startswith("cmd:"):
                raw[current_task].append(stripped[4:].strip().strip("'\""))
        elif indent <= 2:
            in_cmds = False
            if indent == 0:
                section = None

    tasks: dict[str, list[str]] = {}
    base = resolved.parent
    for name, ref in includes.items():
        ref_path = (base / ref).resolve()
        if ref_path.is_dir():
            ref_path = ref_path / "Taskfile.yml"
        for task, cmds in collect_taskfile_commands(ref_path, seen).items():
            tasks[f"{name}:{task}"] = cmds

    local: dict[str, tuple[list[str], list[str]]] = {}
    for task, items in raw.items():
        shell = [i for i in items if isinstance(i, str)]
        refs = [i["task"] for i in items if isinstance(i, dict)]
        local[task] = (shell, refs)

    def expand(task: str, stack: tuple = ()) -> list[str]:
        if task in stack:
            return []
        shell, refs = local.get(task, ([], []))
        out = list(shell)
        for ref in refs:
            out.extend(expand(ref, (*stack, task)))
        return out

    for task in raw:
        tasks[task] = expand(task)
    return tasks


def collect_package_scripts(workspace: Path) -> dict[str, dict[str, str]]:
    """Relatywna ścieżka `package.json` → `{skrypt: komenda}` (poza `node_modules`)."""
    found: dict[str, dict[str, str]] = {}
    for path in workspace.rglob("package.json"):
        if "node_modules" in path.parts:
            continue
        try:
            rel = path.relative_to(workspace).as_posix()
        except ValueError:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            found[rel] = {k: str(v) for k, v in scripts.items() if isinstance(v, str)}
    return found


_TURBO_RUN = re.compile(r"turbo\s+run\s+([A-Za-z0-9_:@#/-]+)")


def expand_turbo(command: str, packages: dict[str, dict[str, str]]) -> list[str]:
    """Rozwiń `turbo run <x>` do skryptów `<x>` ze wszystkich pakietów workspace."""
    names = _TURBO_RUN.findall(command)
    if not names:
        return [command]
    # Skrypty pakietów przed samą komendą — łańcuch odmowy dochodzi do `next build`,
    # a nie kończy się na `turbo run build`.
    expanded = []
    for name in names:
        for scripts in packages.values():
            # Pomijamy skrypt-orkiestrator (root `build: turbo run build`) — to nie liść.
            if name in scripts and not _TURBO_RUN.search(scripts[name]):
                expanded.append(scripts[name])
    return [*expanded, command]


# --- Render -------------------------------------------------------------------


def render_config(
    tasks: dict[str, list[str]],
    packages: dict[str, dict[str, str]],
    server: dict,
) -> dict:
    """Złóż JSON guarda: lista kita + rozwinięte wrappery + sekcja `server` z Profilu."""
    project_deny = [str(x) for x in server.get("deny", []) if str(x).strip()]
    project_allow = [str(x) for x in server.get("allow", []) if str(x).strip()]

    rules: list[dict[str, str]] = [dict(r) for r in DEFAULTS]
    for item in project_deny:
        rules.append({"id": f"project-deny:{item}", "kind": "deny",
                      "pattern": literal_pattern(item),
                      "reason": f"dodatkowy deny projektu (`server.deny`: {item})"})
    for item in project_allow:
        rules.append({"id": f"project-allow:{item}", "kind": "allow",
                      "pattern": literal_pattern(item),
                      "reason": f"wyjątek projektu (`server.allow`: {item})"})

    by_pattern: dict[str, dict[str, str]] = {}

    def add_wrapper(pattern: str, reason: str, chain: str, rule_id: str) -> None:
        # `rule` pozwala guardowi przepuścić wrapper z `uv run`, gdy `UV_NO_SYNC=1` —
        # dlatego inna ciężka reguła w tym samym wrapperze nadpisuje `uv-run`.
        known = by_pattern.get(pattern)
        if known is None or (known["rule"] == "uv-run" and rule_id != "uv-run"):
            by_pattern[pattern] = {"pattern": pattern, "reason": reason, "chain": chain, "rule": rule_id}

    for task, cmds in tasks.items():
        for cmd in cmds:
            for expanded in expand_turbo(cmd, packages):
                denied, rule, _ = check_command(expanded, rules)
                if denied and rule is not None:
                    pattern = literal_pattern(f"task {task}")
                    chain = f"task {task} → {cmd}" if expanded == cmd else f"task {task} → {cmd} → {expanded}"
                    add_wrapper(pattern, rule["reason"], f"{chain} (reguła: {rule['id']})", rule["id"])
                    break

    for scripts in packages.values():
        for name, cmd in scripts.items():
            for expanded in expand_turbo(cmd, packages):
                denied, rule, _ = check_command(expanded, rules)
                if denied and rule is not None:
                    chain_mid = f" → {cmd}" if expanded != cmd else ""
                    base_chain = f"{expanded} (reguła: {rule['id']})"
                    for form in (f"bun run {name}", f"npm run {name}",
                                 f"pnpm {name}", f"yarn {name}"):
                        add_wrapper(literal_pattern(form), rule["reason"],
                                    f"{form}{chain_mid} → {base_chain}", rule["id"])
                    break

    return {
        "version": CONFIG_VERSION,
        "guard": server.get("guard", GUARD_AUTO),
        "defaults": [dict(r) for r in DEFAULTS],
        "project_deny": project_deny,
        "project_allow": project_allow,
        "wrappers": list(by_pattern.values()),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Użycie: render_server_guard.py WORKSPACE HOOKS_DIR PROFILE", file=sys.stderr)
        return 2
    workspace = Path(argv[1])
    hooks_dir = Path(argv[2])
    profile = Path(argv[3])

    server = {"guard": GUARD_AUTO, "deny": [], "allow": [], "warnings": []}
    if profile.is_file():
        try:
            server = parse_server_section(profile.read_text(encoding="utf-8"))
        except OSError as exc:
            warn(f"nie czytam profilu: {exc}")
    for message in server["warnings"]:
        warn(message)

    try:
        tasks = collect_taskfile_commands(workspace / "Taskfile.yml")
    except OSError as exc:
        warn(f"nie czytam Taskfile: {exc}")
        tasks = {}
    try:
        packages = collect_package_scripts(workspace)
    except OSError as exc:
        warn(f"nie czytam package.json: {exc}")
        packages = {}

    config = render_config(tasks=tasks, packages=packages, server=server)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "server-guard.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(f"  + {hooks_dir}/server-guard.json (server-guard: {len(config['wrappers'])} wrapperów)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
