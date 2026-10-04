"""CLI ``kit-ai`` — instalacja, odświeżenie, usunięcie i status kita w repo aplikacji.

Konfiguracja projektu żyje wyłącznie w Profilu (`.ai/project.profile.yaml`, ADR-0007).
``install`` zakłada Profil i robi Bootstrap, ``reload`` robi Bootstrap z istniejącego
Profilu. Logika siedzi w funkcjach, które woła też serwer MCP (``reload_workspace``),
żeby CLI i narzędzie nie rozjechały się w tym, co zapisują.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from guides.bootstrap import BootstrapError, BootstrapPlan, plan_bootstrap, run_bootstrap
from guides.clients import KNOWN_CLIENTS, expand_clients, format_clients_arg, parse_clients
from guides.kit_status import STAMP_REL_PATH, check_kit_updates, direct_url_info
from guides.manifest import find_kit_root
from guides.resolver import PROFILE_REL_PATH, normalize_language

DEFAULT_GIT_SOURCE = "git+https://github.com/radthenone/ai-instruction-kit-mcp.git"
SERVER_NAME = "project-guides"

# Gdzie Bootstrap kładzie konfigurację MCP każdego klienta.
CLIENT_MCP_FILES: dict[str, str] = {
    "cursor": ".cursor/mcp.json",
    "claude": ".mcp.json",
    "codex": ".codex/config.toml",
    "vscode": ".vscode/mcp.json",
    "kiro": ".kiro/settings/mcp.json",
    "kilo": ".kilocode/mcp.json",
    "antigravity": ".agents/mcp_config.json",
    "opencode": "opencode.json",
}

# Zacommitowany plik kita, po którym poznać klienta bez Profilu i stampu (stamp jest
# w .gitignore, więc świeży klon i worktree go nie mają). Ścieżki jak w
# `prune_tier_agents` w bootstrap-project.sh.
CLIENT_KIT_MARKERS: dict[str, str] = {
    "cursor": ".cursor/agents/git-start.md",
    "claude": ".claude/agents/git-start.md",
    "codex": ".codex/skills/git-start/SKILL.md",
    "vscode": ".github/prompts/git-start.prompt.md",
    "kiro": ".kiro/agents/git-start.md",
    "kilo": ".kilocode/workflows/git-start.md",
    "antigravity": ".agents/workflows/git-start.md",
    "opencode": ".opencode/command/git-start.md",
}


class SetupError(RuntimeError):
    """Instalacja albo odświeżenie kita nie może się wykonać."""


@dataclass(frozen=True)
class KitSource:
    """Skąd klient MCP ma uruchamiać serwer: lokalny klon albo URL gita."""

    value: str
    is_clone: bool


@dataclass(frozen=True)
class WorkspaceSettings:
    """Ustawienia instalacji czytane z Profilu (albo ze starego stampu)."""

    language: str
    clients: str
    migrated: bool = False


def kit_source(kit_root: Path) -> KitSource:
    """
    Ustal źródło kita dla konfiguracji klienta.

    Klon (katalog z ``.git``) → ``uv run --project <klon>``. Pakiet z koła → URL gita
    z metadanych instalacji (``direct_url.json``) z przypiętym ref-em, a gdy ich brak —
    domyślne repo kita.

    Args:
        kit_root: Root kita, z którego działa CLI.

    Returns:
        KitSource: Wartość dla ``--from`` w Bootstrapie i tryb.
    """
    if (kit_root / ".git").exists():
        return KitSource(value=str(kit_root), is_clone=True)
    info = direct_url_info()
    vcs = info.get("vcs_info") or {}
    url = str(info.get("url") or "")
    if vcs.get("vcs") == "git" and url:
        ref = vcs.get("requested_revision") or vcs.get("commit_id")
        source = f"git+{url}" if not url.startswith("git+") else url
        return KitSource(value=f"{source}@{ref}" if ref else source, is_clone=False)
    return KitSource(value=DEFAULT_GIT_SOURCE, is_clone=False)


def mcp_server_entry(source: KitSource, *, language: str, clients: str, workspace: Path) -> dict:
    """
    Wpis serwera MCP do wklejenia w konfigurację klienta (format ``mcpServers``).

    Bez Stacków i codegenu — te serwer czyta z Profilu, więc zmiana Profilu nie
    wymaga zmiany konfiguracji klienta.

    Args:
        source: Źródło kita (wynik :func:`kit_source`).
        language: Język prozy.
        clients: Wartość ``--clients``.
        workspace: Absolutna ścieżka repo aplikacji.

    Returns:
        dict: ``{"command": …, "args": [...]}``.
    """
    tail = ["--language", language, "--clients", clients]
    if source.is_clone:
        args = ["run", "--project", source.value, "guides-mcp", *tail, "--kit-root", source.value]
        command = "uv"
    else:
        args = ["--from", source.value, "guides-mcp", *tail]
        command = "uvx"
    return {"command": command, "args": [*args, "--workspace", workspace.as_posix()]}


def to_path(raw: str, *, windows: bool = os.name == "nt") -> Path:
    """
    Ścieżka z linii poleceń: ``M:/…``, Git Bash ``/m/…`` albo linuksowa.

    Python na Windows nie zna konwencji MSYS — ``/m/projects`` byłoby katalogiem
    ``\\m\\projects`` na bieżącym dysku, więc literę dysku odtwarzamy sami.
    """
    match = re.match(r"^/([a-zA-Z])(/.*)?$", raw)
    if windows and match:
        raw = f"{match.group(1).upper()}:{match.group(2) or '/'}"
    return Path(raw).expanduser()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _clients_value(raw: object) -> str:
    """Klienci z Profilu (string albo lista YAML) jako wartość ``--clients``."""
    if isinstance(raw, list):
        raw = ",".join(str(item) for item in raw)
    return format_clients_arg(parse_clients(str(raw) if raw else None))


def _committed_clients(workspace: Path) -> list[str]:
    return [cid for cid, rel in CLIENT_KIT_MARKERS.items() if (workspace / rel).is_file()]


def _has_kit(workspace: Path) -> bool:
    return (
        (workspace / PROFILE_REL_PATH).is_file()
        or (workspace / STAMP_REL_PATH).is_file()
        or bool(_committed_clients(workspace))
    )


def write_profile(workspace: Path, kit_root: Path, *, language: str, clients: str) -> Path:
    """
    Zapisz Profil z szablonu kita: wszystkie Tiery ``none`` (sam core).

    Args:
        workspace: Repo aplikacji.
        kit_root: Root kita (szablon ``templates/project.profile.yaml``).
        language: Język prozy.
        clients: Wartość ``--clients``.

    Returns:
        Path: Ścieżka zapisanego Profilu.
    """
    lines = []
    template = (kit_root / "templates" / "project.profile.yaml").read_text(encoding="utf-8")
    for line in template.splitlines():
        if line.startswith("name: "):
            line = f"name: {workspace.name}"
        elif line.startswith("language: "):
            line = f"language: {language}"
        elif line.startswith("clients: "):
            line = f"clients: {clients}"
        lines.append(line)
    path = workspace / PROFILE_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def workspace_settings(workspace: Path) -> WorkspaceSettings:
    """
    Język i klienci istniejącej instalacji.

    Profil wygrywa. Bez Profilu — stara konfiguracja (stamp z czasów presetów):
    język i klienci ze stampu, ``migrated=True``. Bez stampu (świeży klon) — klienci
    z zacommitowanych plików kita, język ``pl``.

    Args:
        workspace: Repo aplikacji.

    Returns:
        WorkspaceSettings: Ustawienia do Bootstrapu.

    Raises:
        SetupError: Repo bez Profilu i bez stampu — kit nie był instalowany.
    """
    profile_path = workspace / PROFILE_REL_PATH
    stamp_path = workspace / STAMP_REL_PATH
    profile = _read_yaml(profile_path) if profile_path.is_file() else None
    # Profil sprzed `kit-ai` nie ma `clients:`, a jego `language:` to zawsze `pl` z szablonu
    # — prawdziwe wartości są wtedy tylko w stampie.
    if profile is not None and ("clients" in profile or not stamp_path.is_file()):
        return WorkspaceSettings(
            language=normalize_language(str(profile.get("language") or "pl")),
            clients=_clients_value(profile.get("clients")),
        )
    if stamp_path.is_file():
        try:
            stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stamp = {}
        stamp = stamp if isinstance(stamp, dict) else {}
        return WorkspaceSettings(
            language=normalize_language(str(stamp.get("language") or "pl")),
            clients=_clients_value(stamp.get("clients")),
            migrated=profile is None,
        )
    # Świeży klon: tylko zacommitowane pliki kita. Języka nie ma skąd wziąć — `pl` jak w install.
    clients = _committed_clients(workspace)
    if clients:
        return WorkspaceSettings(language="pl", clients=_clients_value(clients), migrated=True)
    raise SetupError(
        f"`{workspace}` nie ma kita (brak `{PROFILE_REL_PATH.as_posix()}`, `{STAMP_REL_PATH}` "
        f"i plików kita klientów). Zainstaluj: kit-ai install {workspace}"
    )


def reload_workspace(
    workspace: Path,
    kit_root: Path,
    *,
    dry_run: bool = False,
) -> tuple[WorkspaceSettings, BootstrapPlan | str]:
    """
    Bootstrap z istniejącego Profilu — wspólny kod ``kit-ai reload`` i MCP.

    Nie rusza ``.ai/project.md``. Stara konfiguracja (stamp z presetem, brak Profilu)
    dostaje Profil core + none z językiem i klientami ze stampu.

    Args:
        workspace: Repo aplikacji.
        kit_root: Root kita.
        dry_run: ``True`` — tylko plan z sandboxu, nic nie zapisuje.

    Returns:
        tuple: ``(ustawienia, plan albo stdout Bootstrapu)``.

    Raises:
        SetupError: Brak kita w repo albo repo to sam kit.
        BootstrapError: Skrypt Bootstrapu się nie wykonał.
    """
    workspace = workspace.resolve()
    if workspace == kit_root.resolve():
        raise SetupError(f"`{workspace}` to repo kita — reload działa w repo aplikacji.")
    settings = workspace_settings(workspace)
    kwargs = {
        "kit_root": kit_root,
        "clients": settings.clients,
        "language": settings.language,
        "from_src": kit_source(kit_root).value,
    }
    if dry_run:
        return settings, plan_bootstrap(workspace_root=workspace, **kwargs)
    if settings.migrated:
        write_profile(workspace, kit_root, language=settings.language, clients=settings.clients)
    return settings, run_bootstrap(target=workspace, **kwargs)


def install_workspace(
    workspace: Path,
    kit_root: Path,
    *,
    language: str,
    clients: str,
) -> str:
    """
    Pierwsza instalacja: Profil core + none, Bootstrap, szablon overlayu.

    Args:
        workspace: Repo aplikacji (zostanie utworzone, gdy go brak).
        kit_root: Root kita.
        language: Język prozy (już znormalizowany).
        clients: Wartość ``--clients`` (już zwalidowana).

    Returns:
        str: Stdout Bootstrapu.

    Raises:
        SetupError: Repo już ma kita albo to repo samego kita.
        BootstrapError: Skrypt Bootstrapu się nie wykonał.
    """
    workspace = workspace.resolve()
    if workspace == kit_root.resolve():
        raise SetupError(f"`{workspace}` to repo kita — instaluj w repo aplikacji.")
    if _has_kit(workspace):
        raise SetupError(
            f"`{workspace}` ma już kita. Zmień język/klientów/Stacki w "
            f"`{PROFILE_REL_PATH.as_posix()}` i uruchom: kit-ai reload {workspace}"
        )
    workspace.mkdir(parents=True, exist_ok=True)
    write_profile(workspace, kit_root, language=language, clients=clients)
    return run_bootstrap(
        target=workspace,
        kit_root=kit_root,
        clients=clients,
        language=language,
        from_src=kit_source(kit_root).value,
        with_overlay=True,
    )


def remove_workspace(workspace: Path, kit_root: Path, *, dry_run: bool = False) -> BootstrapPlan | str:
    """
    Usuń z repo pliki kita (``bootstrap-project.sh --remove``).

    Zostają ``.ai/project.md``, pliki użytkownika i pliki tworzone raz, które
    różnią się od szablonu kita.

    Args:
        workspace: Repo aplikacji.
        kit_root: Root kita.
        dry_run: ``True`` — tylko plan z sandboxu, nic nie usuwa.

    Returns:
        BootstrapPlan | str: Plan (dry-run) albo stdout skryptu.

    Raises:
        SetupError: Repo bez kita albo repo to sam kit.
        BootstrapError: Skrypt się nie wykonał.
    """
    workspace = workspace.resolve()
    if workspace == kit_root.resolve():
        raise SetupError(f"`{workspace}` to repo kita — remove działa w repo aplikacji.")
    if not _has_kit(workspace):
        raise SetupError(f"`{workspace}` nie ma kita — nie ma czego usuwać.")
    if dry_run:
        return plan_bootstrap(workspace_root=workspace, kit_root=kit_root, remove=True)
    return run_bootstrap(target=workspace, kit_root=kit_root, remove=True)


def install_summary(workspace: Path, kit_root: Path, *, language: str, clients: str) -> str:
    """Podsumowanie po instalacji: JSON serwera MCP i gdzie leży per klient."""
    entry = mcp_server_entry(
        kit_source(kit_root), language=language, clients=clients, workspace=workspace.resolve()
    )
    snippet = json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2)
    lines = [
        "",
        "Serwer MCP (JSON do konfiguracji klienta):",
        "",
        snippet,
        "",
        "Gdzie (Bootstrap już to zapisał w repo; wklej ręcznie tylko do konfiguracji globalnej):",
    ]
    lines.extend(
        f"  - {client}: {CLIENT_MCP_FILES[client]}"
        for client in expand_clients(parse_clients(clients))
    )
    lines.extend(
        [
            "",
            "Dalej (przeładuj okno klienta):",
            "  1. Superpowers — Claude Code zaproponuje sam (wpis w .claude/settings.json);",
            "     w pozostałych klientach albo gdy pytanie nie padło:",
            "       /plugin marketplace add obra/superpowers-marketplace",
            "       /plugin install superpowers@superpowers-marketplace",
            "  2. /kit-project-begin — konfiguracja projektu (Stacki, codegen, .ai/project.md)",
        ]
    )
    return "\n".join(lines)


def _ask(prompt: str, default: str, valid: Callable[[str], bool], input_fn: Callable[[str], str]) -> str:
    """Zadaj pytanie, aż odpowiedź będzie poprawna; puste = domyślna."""
    while True:
        answer = input_fn(f"{prompt} ({default}): ").strip() or default
        if valid(answer):
            return answer
        print(f"  Nieprawidłowa wartość: {answer}")


def _valid_clients(value: str) -> bool:
    try:
        parse_clients(value)
    except ValueError:
        return False
    return True


def ask_settings(
    language: str | None,
    clients: str | None,
    *,
    interactive: bool,
    input_fn: Callable[[str], str] = input,
) -> tuple[str, str]:
    """
    Uzupełnij język i klientów: flagi wygrywają, bez TTY — domyślne bez pytań.

    Returns:
        tuple[str, str]: ``(język, wartość --clients)``.
    """
    if language is None and interactive:
        print("1. Język [pl/en]")
        language = _ask("   Język", "pl", lambda v: v.lower() in {"pl", "en"}, input_fn)
        print()
    if clients is None and interactive:
        print(f"2. Klienci ({', '.join(('all', *KNOWN_CLIENTS))} — po przecinku)")
        clients = _ask("   Klienci", "all", _valid_clients, input_fn)
        print()
    return normalize_language(language or "pl"), format_clients_arg(parse_clients(clients))


def _plan_report(plan: BootstrapPlan) -> str:
    lines = ["Dry run — nic nie zapisano."]
    for title, paths in (
        ("Nowe", plan.created),
        ("Nadpisane", plan.modified),
        ("Usunięte", plan.deleted),
    ):
        if paths:
            lines.append(f"{title} ({len(paths)}):")
            lines.extend(f"  - {path}" for path in paths)
    if not plan.touches_disk:
        lines.append("Nic by się nie zmieniło.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint ``kit-ai``."""
    # Windows bez konsoli (potok, agent) pisze w cp1252 i wywraca się na `→` z Bootstrapu.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser =argparse.ArgumentParser(prog="kit-ai", description="Instalacja kita w repo aplikacji")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="Pierwsza instalacja kita w repo")
    install.add_argument(
        "path", nargs="?", default=".", help="Repo aplikacji (M:/…, /m/…, linuksowa; domyślnie: .)"
    )
    install.add_argument("--language", choices=("pl", "en", "PL", "EN"))
    install.add_argument("--clients", help="all | " + " | ".join(KNOWN_CLIENTS) + " (po przecinku)")

    reload = sub.add_parser("reload", help="Odśwież pliki kita z Profilu repo")
    reload.add_argument("path", nargs="?", default=".", help="Repo aplikacji (domyślnie: .)")
    reload.add_argument("--dry-run", action="store_true", help="Pokaż plan, nic nie zapisuj")

    remove = sub.add_parser("remove", help="Usuń pliki kita z repo (własne pliki zostają)")
    remove.add_argument("path", nargs="?", default=".", help="Repo aplikacji (domyślnie: .)")
    remove.add_argument("--dry-run", action="store_true", help="Pokaż, co zniknie, nic nie usuwaj")

    status = sub.add_parser("status", help="Czy kit zmienił się od ostatniego Bootstrapu")
    status.add_argument("path", nargs="?", default=".", help="Repo aplikacji (domyślnie: .)")

    args = parser.parse_args(argv)
    kit_root = find_kit_root()
    workspace = to_path(args.path).resolve()

    try:
        if args.command == "install":
            language, clients = ask_settings(
                args.language, args.clients, interactive=sys.stdin.isatty()
            )
            print(install_workspace(workspace, kit_root, language=language, clients=clients))
            print(install_summary(workspace, kit_root, language=language, clients=clients))
        elif args.command == "reload":
            settings, result = reload_workspace(workspace, kit_root, dry_run=args.dry_run)
            if settings.migrated:
                print("Stara konfiguracja (preset) → Profil core + none, nowy mcp.json.")
            print(_plan_report(result) if isinstance(result, BootstrapPlan) else result)
        elif args.command == "remove":
            result = remove_workspace(workspace, kit_root, dry_run=args.dry_run)
            print(_plan_report(result) if isinstance(result, BootstrapPlan) else result)
        else:
            print(check_kit_updates(kit_root=kit_root, workspace_root=workspace))
    except (SetupError, BootstrapError, ValueError) as exc:
        print(f"kit-ai: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
