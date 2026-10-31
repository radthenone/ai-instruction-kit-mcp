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
  - wzorce kotwiczone na początku segmentu (`^\\s*…(\\s|$)`); precedencja:
    `server.allow` > `server.deny` > allow kita > deny kita.
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
    {"id": "docker-ps", "kind": "allow", "pattern": r"^\s*(?:docker|podman)\s+(?:ps|images|inspect|version|info)(?=\s|$)",
     "reason": "odczyt stanu kontenerów"},
    {"id": "docker-logs", "kind": "allow", "pattern": r"^\s*(?:docker|podman)\s+logs(?=\s|$)(?!.*\s(?:-[a-zA-Z]*f[a-zA-Z]*|--follow)(?=\s|$))",
     "reason": "odczyt logów bez follow"},
    {"id": "docker-logs-follow", "kind": "deny", "pattern": r"^\s*(?:docker|podman)\s+logs(?=\s|$).*\s(?:-[a-zA-Z]*f[a-zA-Z]*|--follow)(?=\s|$)",
     "reason": "follow logów trzyma proces i strumień — użyj `docker logs` bez `-f`"},
    {"id": "docker-compose-config", "kind": "deny", "pattern": r"^\s*docker\s+compose\s+config(?=\s|$)",
     "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
    {"id": "docker-compose-ps", "kind": "allow", "pattern": r"^\s*(?:docker|podman)(?:\s+|-)compose\s+ps(?=\s|$)",
     "reason": "odczyt stanu kontenerów"},
    # Paczki — instalacja kompiluje zależności natywne; lockfile zmienia się na PC albo w CI.
    # #317: wyjątek „tylko lockfile” (allow niżej) — rozwiązanie wersji bez instalacji i builda.
    {"id": "uv-sync", "kind": "deny", "pattern": r"^\s*uv\s+sync(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
    {"id": "uv-add", "kind": "deny", "pattern": r"^\s*uv\s+(?:add|remove)(?=\s|$)",
     "reason": "`uv add`/`uv remove` instaluje i kompiluje — tylko `uv add|remove <pkg> --no-sync --no-build` zmienia sam lockfile; inaczej zależności zmieniają się na PC albo w CI"},
    {"id": "uv-lock", "kind": "deny", "pattern": r"^\s*uv\s+lock(?=\s|$)",
     "reason": "`uv lock` bez `--no-build` buduje projekt — dozwolone tylko `uv lock --no-build`; inaczej lockfile zmienia się na PC albo w CI"},
    {"id": "uv-add-lock-only", "kind": "allow",
     "pattern": r"^\s*uv\s+(?:add|remove)(?=\s|$)(?=.*\s--no-sync(?=\s|$))(?=.*\s--no-build(?=\s|$))",
     "reason": "zmiana zależności tylko w lockfile — bez synchronizacji i bez builda"},
    {"id": "uv-lock-only", "kind": "allow",
     "pattern": r"^\s*uv\s+lock(?=\s|$).*\s--no-build(?=\s|$)",
     "reason": "rozwiązanie wersji tylko do lockfile — bez builda"},
    {"id": "uv-pip-install", "kind": "deny", "pattern": r"^\s*uv\s+pip\s+(?:install|sync)(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
    {"id": "uv-tool-install", "kind": "deny", "pattern": r"^\s*uv\s+tool\s+install(?=\s|$)",
     "reason": "`uv tool install` pobiera paczkę z sieci — narzędzia instaluj na PC albo w CI"},
    {"id": "pip-install", "kind": "deny", "pattern": r"^\s*pip(?:3(?:\.\d+)?)?\s+install(?=\s|$)",
     "reason": "instalacja kompiluje zależności natywne — zależności zmieniają się na PC albo w CI"},
    {"id": "uv-run", "kind": "deny",
     "pattern": r"^\s*uv\s+run(?=\s|$)(?!.*--no-sync)(?!.*--with(?:-requirements|-editable)?(?=[\s=]|$))",
     "reason": "`uv run` bez `--no-sync` synchronizuje i kompiluje — użyj `uv run --no-sync` albo `UV_NO_SYNC=1`"},
    {"id": "uv-run-no-sync", "kind": "allow",
     "pattern": r"^\s*uv\s+run(?=\s|$)(?!.*--with(?:-requirements|-editable)?(?=[\s=]|$)).*?--no-sync",
     "reason": "uruchomienie bez synchronizacji"},
    {"id": "uv-run-with", "kind": "deny",
     "pattern": r"^\s*uv\s+run(?=\s|$).*--with(?:-requirements|-editable)?(?=[\s=]|$)",
     "reason": "`uv run --with` pobiera paczkę z sieci, także z `--no-sync` — zależności instaluj na PC albo w CI"},
    {"id": "uvx", "kind": "deny", "pattern": r"^\s*uvx(?=\s|$)(?!(?:\s+-\S+)*\s+--offline(?=\s|$))",
     "reason": "`uvx` pobiera narzędzie z sieci — użyj `uvx --offline` / `UV_OFFLINE=1` albo `uv run --no-sync python -m …`"},
    {"id": "bun-pkg", "kind": "deny", "pattern": r"^\s*bun\s+(?:install|add|remove|rm|i|a|update|up|upgrade)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — tylko `bun install --lockfile-only --ignore-scripts`, inaczej zależności zmieniają się na PC albo w CI"},
    {"id": "bun-install-lock-only", "kind": "allow",
     "pattern": r"^\s*bun\s+install(?=\s|$)(?=.*\s--lockfile-only(?=\s|$))(?=.*\s--ignore-scripts(?=\s|$))",
     "reason": "aktualizacja tylko `bun.lock` — bez instalacji i bez skryptów"},
    {"id": "npm-pkg", "kind": "deny",
     "pattern": r"^\s*npm\s+(?:install|i|ci|cit|install-ci-test|add|it|install-test|update|up|upgrade|remove|uninstall|un|rm|r)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — tylko `npm install --package-lock-only --ignore-scripts`, inaczej zależności zmieniają się na PC albo w CI"},
    {"id": "npm-install-lock-only", "kind": "allow",
     "pattern": r"^\s*npm\s+(?:install|i)(?=\s|$)(?=.*\s--package-lock-only(?=\s|$))(?=.*\s--ignore-scripts(?=\s|$))",
     "reason": "aktualizacja tylko `package-lock.json` — bez instalacji i bez skryptów"},
    {"id": "pnpm-pkg", "kind": "deny", "pattern": r"^\s*pnpm\s+(?:install|i|add|update|up|upgrade|remove|rm)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — tylko `pnpm install --lockfile-only --ignore-scripts`, inaczej zależności zmieniają się na PC albo w CI"},
    {"id": "pnpm-install-lock-only", "kind": "allow",
     "pattern": r"^\s*pnpm\s+(?:install|i)(?=\s|$)(?=.*\s--lockfile-only(?=\s|$))(?=.*\s--ignore-scripts(?=\s|$))",
     "reason": "aktualizacja tylko `pnpm-lock.yaml` — bez instalacji i bez skryptów"},
    {"id": "yarn-pkg", "kind": "deny", "pattern": r"^\s*yarn\s+(?:global\s+add|install|add|update|up|upgrade|remove)(?=\s|$)",
     "reason": "instalacja paczek na serwerze — Yarn nie ma trybu „tylko lockfile” bez skryptów, więc zależności zmieniają się na PC albo w CI"},
    # Goły `yarn` (także z flagami instalacji: `--frozen-lockfile`, `--cwd app`) instaluje; flagi
    # informacyjne (`--version`, `--help`, `-v`, `-h`) zostają.
    {"id": "yarn-bare", "kind": "deny",
     "pattern": r"^\s*yarn(?=(?:\s+(?:--cwd(?:=|\s+)\S+|-\S+))*\s*$)(?!.*\s(?:-v|--version|-h|--help)(?=\s|$))",
     "reason": "goły `yarn` instaluje zależności — instalacja tylko na PC albo w CI"},
    # CLI, które same instalują paczki (init/add) — poza skryptami projektu.
    {"id": "shadcn", "kind": "deny", "pattern": r"^\s*shadcn(?:@\S+)?\s+(?:init|add)(?=\s|$)",
     "reason": "`shadcn init|add` instaluje paczki sam — instalacja tylko na PC albo w CI"},
    {"id": "expo-install", "kind": "deny", "pattern": r"^\s*expo(?:@\S+)?\s+install(?=\s|$)",
     "reason": "`expo install` zmienia zależności — instalacja tylko na PC albo w CI"},
    # Inne ekosystemy — ta sama zasada: nic nie instalujemy na serwerze.
    {"id": "cargo-install", "kind": "deny", "pattern": r"^\s*cargo\s+install(?=\s|$)",
     "reason": "instalacja na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "go-install", "kind": "deny", "pattern": r"^\s*go\s+install(?=\s|$)",
     "reason": "instalacja na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "apt-install", "kind": "deny", "pattern": r"^\s*apt(?:-get)?(?:\s+-\S+)*\s+install(?=\s|$)",
     "reason": "instalacja na serwerze — zależności zmieniają się na PC albo w CI"},
    {"id": "corepack-enable", "kind": "deny", "pattern": r"^\s*corepack\s+enable(?=\s|$)",
     "reason": "instalacja na serwerze — zależności zmieniają się na PC albo w CI"},
    # Buildy produkcyjne — tylko w CI.
    {"id": "next-build", "kind": "deny", "pattern": r"^\s*next\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `tsc --noEmit`"},
    {"id": "expo-build", "kind": "deny", "pattern": r"^\s*expo(?:@\S+)?\s+(prebuild|export)(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "eas-build", "kind": "deny", "pattern": r"^\s*eas\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "vite-build", "kind": "deny", "pattern": r"^\s*vite\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "nuxt-build", "kind": "deny", "pattern": r"^\s*nuxt\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "astro-build", "kind": "deny", "pattern": r"^\s*astro\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI"},
    {"id": "tsup", "kind": "deny", "pattern": r"^\s*tsup(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `tsc --noEmit`"},
    {"id": "webpack", "kind": "deny", "pattern": r"^\s*webpack(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `tsc --noEmit`"},
    {"id": "cargo-build", "kind": "deny", "pattern": r"^\s*cargo\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `cargo check`"},
    {"id": "turbo-build", "kind": "deny", "pattern": r"^\s*turbo(?:\s+run)?(?:\s+[^-\s]\S*)*?\s+build(?=\s|$)",
     "reason": "build produkcyjny tylko w CI — na VPS `turbo run lint` / `typecheck`"},
    {"id": "turbo-lint", "kind": "allow", "pattern": r"^\s*turbo\s+run(?:\s+(?:lint|typecheck))+(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s*$",
     "reason": "lekkie bramki na VPS"},
    # Launchery JS, które domyślnie pobierają paczkę z sieci.
    # Wyjątki (allow) działają tylko dla flag PRZED nazwą narzędzia: `(?:\s+-\S+)*` nie
    # przechodzi przez token niebędący flagą, więc `npx cowsay --no` zostaje denied.
    {"id": "npx-launcher", "kind": "deny", "pattern": r"^\s*(?:npx|npm\s+(?:exec|x))(?=\s|$)",
     "reason": "`npx` / `npm exec` pobiera paczkę z sieci — użyj `npx --no <bin>`, `bunx --no-install <bin>` albo skryptu projektu (`bun run typecheck`)"},
    {"id": "npx-no", "kind": "allow",
     "pattern": r"^\s*(?:npx|npm\s+(?:exec|x))(?=(?:\s+-\S+)*\s+--no(?=\s|$))(?!(?:\s+-\S+)*\s+(?:-y|--yes)(?=\s|$))",
     "reason": "`--no` przed nazwą: tylko pakiet już w node_modules/.bin, bez pobierania"},
    {"id": "bunx-launcher", "kind": "deny", "pattern": r"^\s*(?:bunx|bun\s+x)(?=\s|$)",
     "reason": "`bunx` pobiera paczkę z sieci — użyj `bunx --no-install <bin>` albo skryptu projektu (`bun run typecheck`)"},
    {"id": "bunx-no-install", "kind": "allow",
     "pattern": r"^\s*(?:bunx|bun\s+x)(?=(?:\s+-\S+)*\s+--no-install(?=\s|$))",
     "reason": "`--no-install` przed nazwą: tylko pakiet już zainstalowany"},
    {"id": "dlx-launcher", "kind": "deny", "pattern": r"^\s*(?:pnpm\s+dlx|yarn\s+dlx|pnpx)(?=\s|$)",
     "reason": "`pnpm dlx` / `yarn dlx` / `pnpx` zawsze pobiera paczkę — użyj skryptu projektu (`bun run typecheck`) albo `npx --no <bin>`"},
    # Przeglądarki / e2e — setki MB na instancję, tylko w CI.
    {"id": "playwright", "kind": "deny", "pattern": r"^\s*(npx\s+|bunx\s+|yarn\s+dlx\s+|pnpm\s+dlx\s+)?playwright(?=\s|$)",
     "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
    {"id": "cypress", "kind": "deny", "pattern": r"^\s*(npx\s+|bunx\s+)?cypress(?=\s|$)",
     "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
    {"id": "maestro", "kind": "deny", "pattern": r"^\s*maestro(?=\s|$)",
     "reason": "testy mobilne tylko w CI"},
    # Mnożenie procesów na słabym CPU.
    {"id": "pytest-xdist", "kind": "deny",
     "pattern": r"^\s*pytest(?=\s|$).*\s(?:-n(?:=?[a-zA-Z0-9]+)?|--numprocesses(?:=\S+)?)(?=\s|$)",
     "reason": "xdist mnoży procesy na słabym CPU — użyj `pytest` bez `-n`"},
)

_HEREDOC = re.compile(r"<<(?!<)(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_SHELL_C = re.compile(
    r"(?:^|\s)(?:\S*/)?(?:bash|sh|zsh|dash)\s+(?:-[a-zA-Z]+\s+)*-[a-zA-Z]*c[a-zA-Z]*\s+"
    r"(?:\"([^\"]*)\"|'([^']*)'|(\S+))"
)
_SUBSHELL = re.compile(r"\$\(\s*(.*?)\s*\)")
_BACKTICK = re.compile(r"`([^`]*)`")
_ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S*)\s+")
_LOOKUP_FLAG = re.compile(r"^\s*(?:\S*/)?command\s+-[a-zA-Z]*[vV]")

_PREFIXES = (
    re.compile(r"^\s*(?:\S*/)?sudo\b\s*(?:(?:-[ugpCDhrtU]\s+\S+|-\S+)\s+)*"),
    re.compile(r"^\s*(?:\S*/)?env(?:\s+(?:-[uC]\s+\S+|-\S+))*\s+"),
    re.compile(r"^\s*(?:\S*/)?(?:nice|ionice|nohup|time|command|exec|xargs|eval)\b\s*(?:-\S+(?:\s+\d+)?\s+)*"),
    re.compile(r"^\s*(?:\S*/)?timeout(?:\s+(?:-[sk]\s+\S+|-\S+))*\s+[\d.]+[smhd]?\s+"),
    re.compile(r"^\s*[\"']+"),
    re.compile(r"^(\s*)(?:[^\s/'\"]*/)+(?=\S)"),
)

# Opcje z argumentem — reszta po `run` / launcherze to właściwa komenda.
_UV_GLOBAL_ARG = frozenset(("--directory", "--project", "--config-file", "--cache-dir", "--python", "-p"))
_UV_RUN_ARG = frozenset((
    "--with", "--with-requirements", "--python", "-p", "--package", "--env-file", "--group",
    "--extra", "--directory", "--project", "--index", "--index-url",
))
_JS_PM_ARG = frozenset(("--filter", "-F", "--cwd", "-C", "--workspace", "--prefix", "--dir"))
_NPX_ARG = frozenset(("-p", "--package"))
_PYTHON = re.compile(r"python(?:\d+(?:\.\d+)?)?")
# `rtk` to globalna wtyczka przepisująca komendę (opencode/Claude/Codex/Cursor):
# `bun install` → `rtk bun install`, `next build` → `rtk next`. Traktujemy go jak
# launcher, bo przepisana komenda nie zawiera już słów, na których stoją reguły.
_RTK_LAUNCHER = frozenset(("proxy", "err", "test", "summary", "run"))
# Głębsze zagnieżdżenie launcherów (`rtk rtk rtk …`) to atak na stos — deny, nie crash.
_MAX_DEPTH = 16
_TOO_DEEP = {"id": "nesting", "kind": "deny", "reason": "zbyt głębokie zagnieżdżenie launcherów"}


class _TooDeep(Exception):
    pass


def _drop_tokens(text: str, n: int) -> str:
    """Tekst bez pierwszych `n` słów (zachowuje cudzysłowy reszty)."""
    return re.sub(r"^\s*(?:\S+\s*){%d}" % n, "", text)


def warn(message: str) -> None:
    """Ostrzeżenie — nigdy nie przerywa renderu (ADR-0004)."""
    print(f"server-guard: {message}", file=sys.stderr)


def _skip_heredocs(command: str, i: int, pending: list[tuple[bool, str]]) -> int:
    """Przeskocz treść heredoców od pozycji ``i`` (początek linii) do ich ograniczników."""
    for strip_tabs, delim in pending:
        while i < len(command):
            end = command.find("\n", i)
            line = command[i:] if end < 0 else command[i:end]
            i = len(command) if end < 0 else end + 1
            if (line.lstrip("\t") if strip_tabs else line).strip() == delim:
                break
    return i


def _mask_single_quotes(text: str) -> str:
    """Zamień treść pojedynczych apostrofów na spacje (ta sama długość).

    Bash nie wykonuje w nich podstawień `` `…` `` ani ``$( … )`` (#206), więc
    dopasowania tych wzorców liczone na zamaskowanym tekście wskazują oryginał.
    """
    out: list[str] = []
    quote = ""
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote in ("'", "$'"):
            # W `$'…'` backslash escapuje także apostrof (`$'it\'s'`).
            if quote == "$'" and c == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
                continue
            out.append(" ")
            if c == "'":
                quote = ""
            i += 1
            continue
        if quote == '"':
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                quote = ""
            i += 1
            continue
        if c == "$" and text[i + 1 : i + 2] == "'":
            quote = "$'"
            out.append("  ")
            i += 2
            continue
        if c == "'":
            quote = "'"
            out.append(" ")
            i += 1
            continue
        if c == '"':
            quote = '"'
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i : i + 2])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def split_segments(command: str) -> list[str]:
    """Podziel komendę na segmenty + wnętrza `bash -c` / `$(…)` / backticków.

    Separatory (`&&`, `||`, `;`, `|`, `&`, `(`, `)`, nowa linia) liczą się tylko poza
    cudzysłowami; treść heredoca jest pomijana — to dane, nie komendy. Podstawienia
    `` `…` `` / ``$( … )`` w pojedynczych apostrofach też są danymi (#206); w `bash -c '…'`
    czytamy surowy segment, bo pojedyncze apostrofy `-c` to wykonywany skrypt.
    """
    segments: list[str] = []
    buf: list[str] = []
    pending: list[tuple[bool, str]] = []
    quote = ""
    i = 0
    n = len(command)

    def flush() -> None:
        seg = "".join(buf)
        if seg.strip():
            segments.append(seg)
        buf.clear()

    while i < n:
        c = command[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(command[i + 1])
                i += 1
            elif c == quote:
                quote = ""
            i += 1
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(" " if command[i + 1] == "\n" else command[i : i + 2])
            i += 2
            continue
        heredoc = _HEREDOC.match(command, i)
        if heredoc:
            pending.append((heredoc.group(1) == "-", heredoc.group(3)))
            buf.append(heredoc.group(0))
            i = heredoc.end()
            continue
        if c == "\n":
            flush()
            i = _skip_heredocs(command, i + 1, pending)
            pending = []
            continue
        if command.startswith(("&&", "||"), i):
            flush()
            i += 2
            continue
        if c in ";|&()\r":
            flush()
            i += 1
            continue
        buf.append(c)
        i += 1
    flush()

    extra: list[str] = []
    for seg in segments:
        for match in _SHELL_C.finditer(seg):
            inner = next((g for g in match.groups() if g), "")
            if inner.strip():
                extra.extend(split_segments(inner))
        code = _mask_single_quotes(seg)
        for regex in (_SUBSHELL, _BACKTICK):
            for match in regex.finditer(code):
                if match.group(1).strip():
                    extra.extend(split_segments(match.group(1)))
    return segments + extra


def strip_prefixes(segment: str) -> tuple[str, dict[str, str]]:
    """Zdejmij prefiksy uruchamiające inną komendę i ścieżkę binarki.

    Returns:
        tuple: ``(komenda, przypisania VAR=… z linii)``. Sprawdzenie dostępności
            (`command -v docker`) zwraca pustą komendę — niczego nie uruchamia.
    """
    assigns: dict[str, str] = {}
    previous = None
    current = segment
    while previous != current:
        previous = current
        if _LOOKUP_FLAG.match(current):
            return "", assigns
        match = _ASSIGN.match(current)
        if match:
            assigns[match.group(1)] = match.group(2).strip("'\"")
            current = current[match.end():]
            continue
        for pattern in _PREFIXES:
            current = pattern.sub(r"\1" if pattern.groups else "", current, count=1)
    return current, assigns


def _skip_flags(toks: list[str], i: int, with_arg: frozenset[str]) -> int:
    while i < len(toks) and toks[i].startswith("-"):
        i += 2 if toks[i] in with_arg else 1
    return i


def command_forms(segment: str, depth: int = 0) -> tuple[list[str], dict[str, str]]:
    """Formy segmentu do dopasowania: sama komenda + to, co uruchamia launcher.

    `uv [opcje] run [flagi] X`, `npx`/`bunx X`, `pnpm|yarn|npm dlx|exec X`, `python -m X`
    dokładają formę `X`; opcje `uv` przed podkomendą i `--filter`/`--cwd` menedżerów JS
    są zdejmowane, żeby wzorce (`uv run`, wrappery `bun run x`) widziały komendę wprost.
    `rtk` jest launcherem wykonania: `rtk X …` daje `X …`, `rtk proxy|err|test|summary X`
    daje `X`, a `rtk run -c "…"` oceniamy jak `sh -c`. Tabela znaczeń dokłada formy,
    w których rtk zgubił słowo: `rtk next` → `next build`, `rtk npm X` → `npm run X`.
    """
    if depth > _MAX_DEPTH:
        raise _TooDeep
    command, assigns = strip_prefixes(segment)
    toks = command.split()
    if not toks:
        return [], assigns
    head = toks[0]
    forms = [command]
    rest: list[str] = []
    if head == "uv":
        i = _skip_flags(toks, 1, _UV_GLOBAL_ARG)
        toks = ["uv", *toks[i:]]
        forms = [" ".join(toks)]
        if len(toks) > 1 and toks[1] == "run":
            rest = toks[_skip_flags(toks, 2, _UV_RUN_ARG):]
    elif head in ("npx", "bunx"):
        rest = toks[_skip_flags(toks, 1, _NPX_ARG):]
    elif head in ("bun", "npm", "pnpm", "yarn"):
        i = _skip_flags(toks, 1, _JS_PM_ARG)
        sub = toks[i:i + 1]
        if sub in (["run"], ["run-script"]):
            toks = [head, sub[0], *toks[_skip_flags(toks, i + 1, _JS_PM_ARG):]]
            forms = [" ".join(toks)]
        elif i < len(toks):
            # Same flagi (`yarn --version`) to nie uruchomienie skryptu — zostaw oryginał.
            toks = [head, *toks[i:]]
            forms = [" ".join(toks)]
        if len(toks) > 1 and toks[1] in ("dlx", "exec", "x"):
            rest = toks[_skip_flags(toks, 2, _NPX_ARG):]
    elif _PYTHON.fullmatch(head) and len(toks) > 2 and toks[1] == "-m":
        rest = toks[2:]
    elif head == "rtk":
        i = _skip_flags(toks, 1, frozenset())
        sub = toks[i] if i < len(toks) else ""
        tail = _drop_tokens(command, i + 1)
        toks = ["rtk", *toks[i:]]
        forms = [" ".join(toks)]
        if sub in _RTK_LAUNCHER:
            # Flagi rtk i `--` po podkomendzie; `run -c|--command` oraz cytowany argument
            # rtk uruchamia przez `sh -c`, a argumenty run|err|test|summary skleja w jedną
            # linię powłoki (cudzysłów w argumencie nie chroni separatora). `proxy` to argv.
            words = tail.split()
            skipped = 0
            script = None
            while skipped < len(words) and words[skipped].startswith("-"):
                if sub == "run" and re.match(r"-c|--command(?:=|$)", words[skipped]):
                    script = re.sub(r"^(?:--command|-c)(?:=|\s*)", "", _drop_tokens(tail, skipped))
                    break
                skipped += 1
                if words[skipped - 1] == "--":
                    break
            if script is None:
                script = _drop_tokens(tail, skipped)
                if sub == "proxy" and script[:1] not in ("'", '"'):
                    rest = script.split()
                    script = None
            if script is not None:
                script = script.strip()
                lines = [f"sh -c {script}" if script[:1] in ("'", '"') else script]
                if sub != "proxy":
                    lines.append(re.sub(r"['\"]", "", script))
                for line in lines:
                    for inner_segment in split_segments(line):
                        inner_forms, inner_assigns = command_forms(inner_segment, depth + 1)
                        forms.extend(inner_forms)
                        assigns.update(inner_assigns)
        elif sub:
            rest = toks[1:]
        # `rtk next X` zawsze uruchamia `next build X` (poza `--help`).
        if sub == "next" and not {"-h", "--help"} & set(toks[2:]):
            forms.append(" ".join(["next", "build", *toks[2:]]))
        elif sub == "npm" and len(toks) > 2 and toks[2] not in ("run", "run-script"):
            # `rtk npm X` uruchamia `npm X`, ale wrapper w package.json to `npm run X`.
            inner_forms, inner_assigns = command_forms("npm run " + " ".join(toks[2:]), depth + 1)
            forms.extend(inner_forms)
            assigns.update(inner_assigns)
    if rest:
        inner, inner_assigns = command_forms(" ".join(rest), depth + 1)
        forms.extend(inner)
        assigns.update(inner_assigns)
    return forms, assigns


def literal_pattern(command: str) -> str:
    """Wzorzec dosłownego wywołania (wrappery, `server.deny`/`server.allow`)."""
    return r"^\s*" + r"\s+".join(re.escape(tok) for tok in command.split()) + r"(?=\s|$)"


def rule_origin(rule: dict[str, str]) -> str:
    """Reguła kita, od której pochodzi odmowa (dla wrappera — reguła z jego wnętrza)."""
    return rule.get("rule") or rule["id"]


def check_command(
    command: str,
    rules: list[dict[str, str]],
    no_sync: bool = False,
    offline: bool = False,
) -> tuple[bool, dict[str, str] | None, str]:
    """Czy komenda denied? Zwraca `(denied, reguła, segment)` — `server.allow` > `server.deny`
    > allow kita > deny kita.

    `uv-run` (także wrapper z `uv run` w środku) odpada przy `UV_NO_SYNC=1` z env
    albo z przypisania w linii. Gdy pasuje kilka odmów, inna reguła wygrywa z `uv-run`
    — `UV_NO_SYNC` nie może przepuścić `docker` z tego samego wrappera. Analogicznie
    `UV_OFFLINE=1` (env albo przypisanie) zdejmuje deny `uvx`.
    """
    fallback: tuple[bool, dict[str, str] | None, str] = (False, None, "")
    for segment in split_segments(command):
        try:
            forms, assigns = command_forms(segment)
        except _TooDeep:
            return True, dict(_TOO_DEEP), segment.strip()
        segment_no_sync = no_sync or assigns.get("UV_NO_SYNC") == "1"
        segment_offline = offline or assigns.get("UV_OFFLINE") == "1"
        for form in forms:
            allow_hit = project_allow_hit = project_deny_hit = deny_hit = None
            for rule in rules:
                if segment_no_sync and rule_origin(rule) == "uv-run":
                    continue
                if segment_offline and rule_origin(rule) == "uvx":
                    continue
                try:
                    matched = re.search(rule["pattern"], form) is not None
                except re.error:
                    continue
                if not matched:
                    continue
                if rule["kind"] == "allow":
                    if rule["id"].startswith("project-allow:"):
                        project_allow_hit = project_allow_hit or rule
                    else:
                        allow_hit = allow_hit or rule
                elif rule["id"].startswith("project-deny:"):
                    project_deny_hit = project_deny_hit or rule
                elif deny_hit is None:
                    deny_hit = rule
            # `server.allow` > `server.deny` > allow kita > deny kita (#317: `server.deny`
            # musi móc zablokować domyślną formę lock-only).
            hit = project_allow_hit or project_deny_hit or allow_hit or deny_hit
            if hit is None or hit["kind"] == "allow":
                continue
            if rule_origin(hit) != "uv-run":
                return True, hit, segment.strip()
            if not fallback[0]:
                fallback = (True, hit, segment.strip())
    return fallback


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

_TASKFILE_NAMES = ("Taskfile.yml", "Taskfile.yaml", "taskfile.yml", "taskfile.yaml")
_BLOCK_SCALAR = frozenset(("|", "|-", "|+", ">", ">-", ">+"))


def _unquote(value: str) -> str:
    return value.strip().strip("'\"").strip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_taskfile(path: Path) -> Path:
    """Katalog → pierwszy istniejący `Taskfile.yml` / `.yaml` w nim; plik bez zmian."""
    if path.is_dir():
        for name in _TASKFILE_NAMES:
            if (path / name).is_file():
                return path / name
    return path


def collect_taskfile_commands(
    path: Path, seen: set[Path] | None = None, namespace: str = ""
) -> dict[str, list[str]]:
    """Task → komendy shellowe; `task:` i `deps:` jako `task <pełna nazwa>`.

    Tolerancyjny podzbiór YAML Taskfile v3: `includes` (krótkie, `{taskfile: …}`
    i blok z kluczem `taskfile:`), `cmds` jako napisy, `- cmd: …`, `- task: …`
    i block scalar (`- |`), `deps` jako lista albo `[a, b]`. Odwołania z dołączonego
    pliku dostają jego przestrzeń nazw (`:x` = task z roota). Cykle w includes pomijane.
    """
    seen = seen if seen is not None else set()
    resolved = find_taskfile(path).resolve()
    if resolved in seen or not resolved.is_file():
        return {}
    seen.add(resolved)
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    def full(name: str) -> str:
        if name.startswith(":"):
            return name[1:]
        return f"{namespace}:{name}" if namespace else name

    tasks: dict[str, list[str]] = {}
    includes: dict[str, str] = {}
    section = task = include = None
    block = ""  # `cmds` albo `deps`
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent(line)
        if indent == 0:
            section = stripped[:-1] if stripped in ("tasks:", "includes:") else None
            task = include = None
            block = ""
            continue
        if section == "includes":
            if indent == 2:
                include, _, value = (part.strip() for part in stripped.partition(":"))
                if value.startswith("{"):
                    match = re.search(r"taskfile\s*:\s*([^,}]+)", value)
                    value = match.group(1) if match else ""
                includes[include] = _unquote(value)
            elif include and stripped.startswith("taskfile:"):
                includes[include] = _unquote(stripped[len("taskfile:"):])
            continue
        if section != "tasks":
            continue
        if indent == 2:
            task = _unquote(stripped[:-1]) if stripped.endswith(":") else None
            if task is not None:
                tasks.setdefault(full(task), [])
            block = ""
            continue
        if task is None:
            continue
        cmds = tasks[full(task)]
        if indent == 4:
            key, _, value = (part.strip() for part in stripped.partition(":"))
            block = key if key in ("cmds", "deps") else ""
            if block == "deps" and value.startswith("["):
                cmds.extend(f"task {full(_unquote(d))}" for d in value.strip("[]").split(",") if d.strip())
            continue
        if not block:
            continue
        if stripped.startswith("-"):
            item = stripped[1:].strip()
        elif stripped.startswith(("cmd:", "task:")):
            item = stripped
        else:
            continue
        if block == "deps":
            if item and not item.startswith(("task:", "vars:")):
                cmds.append(f"task {full(_unquote(item))}")
        if item.startswith("task:"):
            cmds.append(f"task {full(_unquote(item[len('task:'):]))}")
            continue
        if block == "deps":
            continue
        if item.startswith("cmd:"):
            item = item[len("cmd:"):].strip()
        if item in _BLOCK_SCALAR:
            while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > indent):
                if lines[i].strip():
                    cmds.append(lines[i].strip())
                i += 1
            continue
        if item:
            cmds.append(_unquote(item))

    base = resolved.parent
    for name, ref in includes.items():
        if ref:
            tasks.update(collect_taskfile_commands(base / ref, seen, full(name)))
    return tasks


def collect_package_scripts(workspace: Path) -> dict[str, dict[str, str]]:
    """Relatywna ścieżka `package.json` → `{skrypt: komenda}`.

    Pomija `node_modules` i katalogi z kropką (`.ai/headless-runs`, `.worktrees`, …) —
    to nie skrypty projektu, a różnią się między maszynami.
    """
    found: dict[str, dict[str, str]] = {}
    for path in sorted(workspace.rglob("package.json")):
        dirs = path.relative_to(workspace).parts[:-1]
        if "node_modules" in dirs or any(part.startswith(".") for part in dirs):
            continue
        try:
            rel = path.relative_to(workspace).as_posix()
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scripts = data.get("scripts") if isinstance(data, dict) else None
        if isinstance(scripts, dict):
            found[rel] = {k: str(v) for k, v in scripts.items() if isinstance(v, str)}
    return found


# --- Render -------------------------------------------------------------------

_NPM_SHORT = frozenset(("test", "start", "stop", "restart"))


def _script_forms(name: str) -> list[tuple[str, str]]:
    """Wywołania skryptu `package.json` przez menedżery JS → `(forma, wzorzec)`."""
    forms = [f"bun run {name}", f"npm run {name}", f"npm run-script {name}",
             f"pnpm {name}", f"pnpm run {name}", f"yarn {name}", f"yarn run {name}"]
    if name in _NPM_SHORT:
        forms.append(f"npm {name}")
    return [(form, literal_pattern(form)) for form in forms]


def _turbo_pattern(name: str) -> str:
    """`turbo run a b …` z `name` wśród zadań."""
    return r"^\s*turbo\s+run\s+(?:\S+\s+)*" + re.escape(name) + r"(?=\s|$)"


def render_config(
    tasks: dict[str, list[str]],
    packages: dict[str, dict[str, str]],
    server: dict,
) -> dict:
    """Złóż JSON guarda: lista kita + rozwinięte wrappery + sekcja `server` z Profilu.

    Wrappery (`task x`, `bun run x`, `turbo run x`, …) to też reguły, więc rozwijanie
    iteruje do stabilizacji: `ci: bun run build` → `turbo run build` → `next build`
    wychodzi z łańcuchem. Odmowa z `uv-run` przegrywa z każdą inną.
    """
    project_deny = [str(x) for x in server.get("deny", []) if str(x).strip()]
    project_allow = [str(x) for x in server.get("allow", []) if str(x).strip()]

    base: list[dict[str, str]] = [dict(r) for r in DEFAULTS]
    for item in project_deny:
        base.append({"id": f"project-deny:{item}", "kind": "deny",
                     "pattern": literal_pattern(item),
                     "reason": f"dodatkowy deny projektu (`server.deny`: {item})"})
    for item in project_allow:
        base.append({"id": f"project-allow:{item}", "kind": "allow",
                     "pattern": literal_pattern(item),
                     "reason": f"wyjątek projektu (`server.allow`: {item})"})

    # Źródło wrappera: (wywołania jako (forma, wzorzec), komendy w środku).
    sources: list[tuple[list[tuple[str, str]], list[str]]] = [
        ([(f"task {name}", literal_pattern(f"task {name}"))], cmds) for name, cmds in tasks.items()
    ]
    names: dict[str, list[str]] = {}
    for scripts in packages.values():
        for name, cmd in scripts.items():
            sources.append((_script_forms(name), [cmd]))
            names.setdefault(name, []).append(cmd)
    for name, cmds in names.items():
        sources.append(([(f"turbo run {name}", _turbo_pattern(name))], cmds))

    wrappers: dict[str, dict[str, str]] = {}
    scores: dict[str, tuple[bool, int]] = {}

    def links(rule: dict[str, str]) -> list[str]:
        return rule["chain"].split(" → ") if rule.get("chain") else []

    def score(rule: dict[str, str]) -> tuple[bool, int]:
        # Lepsza odmowa: nie `uv-run`, potem dłuższy łańcuch (do liścia, np. `next build`).
        return rule_origin(rule) != "uv-run", len(links(rule))

    # Punkt stały: wrapper może wejść w łańcuch innego dopiero po swoim rozwinięciu.
    # Łańcuch nie zawiera własnej formy (cykle `task a ↔ task b`), więc długości są
    # ograniczone, a wynik rośnie ściśle — pętla się kończy.
    changed = True
    while changed:
        changed = False
        rules = [*wrappers.values(), *base]
        for forms, cmds in sources:
            own_forms = {form for form, _ in forms}
            own_rules = [
                r for r in rules
                if r["pattern"] not in {pattern for _, pattern in forms} and not own_forms & set(links(r))
            ]
            best: tuple[dict[str, str], str] | None = None
            for cmd in cmds:
                denied, rule, _ = check_command(cmd, own_rules)
                if denied and rule is not None and (best is None or score(rule) > score(best[0])):
                    best = (rule, cmd)
            if best is None:
                continue
            rule, cmd = best
            tail = links(rule)
            inner = tail if tail and tail[0] == cmd.strip() else [cmd.strip(), *tail]
            for form, pattern in forms:
                if pattern in scores and score(rule) <= scores[pattern]:
                    continue
                scores[pattern] = score(rule)
                wrappers[pattern] = {
                    "id": "wrapper",
                    "kind": "deny",
                    "pattern": pattern,
                    "reason": rule["reason"],
                    "chain": " → ".join([form, *inner]),
                    "rule": rule_origin(rule),
                }
                changed = True

    return {
        "version": CONFIG_VERSION,
        "guard": server.get("guard", GUARD_AUTO),
        "defaults": [dict(r) for r in DEFAULTS],
        "project_deny": project_deny,
        "project_allow": project_allow,
        "wrappers": list(wrappers.values()),
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
        tasks = collect_taskfile_commands(workspace)
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
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n",
    )
    print(f"  + {hooks_dir}/server-guard.json (server-guard: {len(config['wrappers'])} wrapperów)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
