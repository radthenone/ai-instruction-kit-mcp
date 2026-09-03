"""Serwer MCP FastMCP — wystawia instrukcje projektu jako tools i resources."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from guides.bootstrap import BootstrapError, plan_bootstrap, run_bootstrap
from guides.clients import (
    expand_clients,
    format_clients_arg,
    parse_clients,
)
from guides.kit_status import check_kit_updates
from guides.manifest import find_kit_root, load_manifest
from guides.resolver import (
    normalize_codegen,
    normalize_language,
    resolve_preset_path,
    resolve_profile,
)

mcp = FastMCP(
    "project-guides",
    instructions=(
        "Dostarcza modułowe instrukcje architektury i stacku dla projektu. "
        "Przed pracą nad backendem pobierz bundle backend; nad frontendem — frontend; "
        "nad architekturą/infra — architecture. Overlay projektu zawiera unikalne ścieżki i taski. "
        "Język prozy (odpowiedzi, docstringi, body issue/commit) ustawia --language / GUIDES_LANGUAGE; "
        "tytuły issue/PR/branch zawsze po angielsku. Użyj get_language. "
        "Klienci AI (--clients) to metadane instalacji — get_clients; treść bundle bez zmian. "
        "Pliki kita (hooki, agenci, komendy) instaluje bootstrap_workspace — jedyne narzędzie "
        "zapisujące, domyślnie dry_run=True."
    ),
)

_profile_path: Path | None = None
_kit_root: Path | None = None
_workspace_root: Path | None = None
_extra_overlays: list[Path] = []
_language_override: str | None = None
_codegen_override: str | None = None
_clients: list[str] = ["all"]
_preset: str | None = None


def _get_profile_path() -> Path:
    """Zwróć ścieżkę profilu — z CLI, presetu lub env GUIDES_PROFILE."""
    if _profile_path is not None:
        return _profile_path
    env_path = os.environ.get("GUIDES_PROFILE")
    if env_path:
        return Path(env_path).resolve()
    raise RuntimeError(
        "Brak profilu projektu. Uruchom z --profile / --preset albo ustaw GUIDES_PROFILE."
    )


def _get_resolved():
    """Rozwiąż profil (cache per request — profil rzadko się zmienia w sesji)."""
    return resolve_profile(
        _get_profile_path(),
        kit_root=_kit_root,
        workspace_root=_workspace_root,
        extra_overlays=_extra_overlays or None,
        language_override=_language_override,
        codegen_override=_codegen_override,
    )


@mcp.tool()
def list_bundles() -> str:
    """
    Lista dostępnych bundle'i instrukcji dla bieżącego profilu projektu.

    Returns:
        str: Markdown z listą bundle'i i liczbą modułów.
    """
    resolved = _get_resolved()
    lines = [f"# Bundle'e dla `{resolved.name}`", ""]
    for name, bundle in resolved.bundles.items():
        missing = f" ⚠ brak: {', '.join(bundle.missing_modules)}" if bundle.missing_modules else ""
        lines.append(f"- **{name}** — {len(bundle.module_ids)} modułów{missing}")
    return "\n".join(lines)


@mcp.tool()
def get_bundle(name: str) -> str:
    """
    Pobierz pełną treść bundle'a instrukcji.

    Args:
        name: Nazwa bundle'a, np. backend, frontend, architecture, full.

    Returns:
        str: Połączona treść Markdown wszystkich modułów w bundle'u + overlay (jeśli dotyczy).
    """
    resolved = _get_resolved()
    bundle = resolved.bundles.get(name)
    if bundle is None:
        available = ", ".join(sorted(resolved.bundles))
        return f"Nieznany bundle `{name}`. Dostępne: {available}"

    content = bundle.content
    if resolved.overlay_content and name in (
        "backend", "frontend", "architecture", "shop", "payments", "infra", "devops", "full"
    ):
        content += f"\n\n---\n\n{resolved.overlay_content}"
    return content


@mcp.tool()
def get_index() -> str:
    """
    Indeks włączonych modułów i bundle'i dla bieżącego profilu.

    Returns:
        str: Markdown z podsumowaniem konfiguracji profilu.
    """
    return _get_resolved().index_markdown


@mcp.tool()
def get_overlay() -> str:
    """
    Pobierz overlay projektu — unikalne instrukcje tylko dla tego repo.

    Returns:
        str: Treść `.ai/project.md` i innych overlay wskazanych w profilu.
    """
    overlay = _get_resolved().overlay_content
    return overlay if overlay else "_Brak overlay projektu._"


@mcp.tool()
def get_language() -> str:
    """
    Aktualny język instrukcji i polityka tytułów vs prozy.

    Returns:
        str: Markdown z kodem języka, modułem `core:language-*` i regułami EN/PL.
    """
    resolved = _get_resolved()
    lang = resolved.language
    module_id = resolved.language_module_id
    if lang == "en":
        prose = (
            "Agent replies, public docstrings, issue/PR bodies, review comments, "
            "and commit messages — **English**."
        )
        chat = "Chat replies: English (unless user asks otherwise)."
    else:
        prose = (
            "Odpowiedzi agenta, docstringi publiczne, body issue/PR, komentarze review "
            "i komunikaty commitów — **po polsku**."
        )
        chat = "Odpowiedzi w czacie: po polsku (chyba że user prosi inaczej)."

    lines = [
        f"# Language: `{lang}`",
        "",
        f"- Module: `{module_id}`",
        f"- Override CLI/env: `{_language_override or '—'}` "
        f"(GUIDES_LANGUAGE / `--language` wins over profile YAML)",
        "",
        "## Policy",
        "",
        "- **Titles always English**: issue title, PR title, branch slug "
        "(`feat/42-add-cart-coupon`).",
        f"- **Prose follows `{lang}`**: {prose}",
        "- **Code identifiers**: always English.",
        f"- {chat}",
        "",
        "Source of truth for agents: this tool + the language module inside bundles.",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_codegen() -> str:
    """
    Aktualny wybór generatora klienta API (``--codegen`` / `codegen:` w profilu).

    Returns:
        str: Markdown — ``orval`` (schema → `frontend/src/api/generated` + mutatory),
            ``none`` (tool-agnostyczny klient, konkret w overlay projektu) albo
            ``graphql`` (GraphQL zamiast REST, patrz `arch:api-contract:graphql`).
    """
    resolved = _get_resolved()
    codegen = resolved.codegen
    if codegen == "orval":
        detail = (
            "**Orval**: `task orval:generate` (nazwa taska zależy od overlay projektu) "
            "czyta OpenAPI schema i generuje typowanego klienta + mutatory do "
            "`frontend/src/api/generated/`. Nie edytuj wygenerowanych plików ręcznie."
        )
    elif codegen == "graphql":
        detail = (
            "**GraphQL** — zamiast REST+OpenAPI. `graphql-codegen` generuje typy z "
            "`.graphql` query + schema. Osobny pipeline niż Orval — patrz "
            "`arch:api-contract:graphql`."
        )
    else:
        detail = (
            "**Brak Orval** — generyczny/tool-agnostyczny klient API albo typy ręczne. "
            "Konkretne narzędzie i komenda regeneracji — overlay projektu `.ai/project.md`."
        )
    module_suffix = {"orval": "", "none": ":none", "graphql": ":graphql"}[codegen]
    lines = [
        f"# Codegen: `{codegen}`",
        "",
        f"- Override CLI/env: `{_codegen_override or '—'}` "
        f"(GUIDES_CODEGEN / `--codegen` wygrywa z `codegen:` w profilu; domyślnie `orval`)",
        "",
        detail,
        "",
        f"Moduł: `arch:api-contract{module_suffix}`.",
    ]
    return "\n".join(lines)


@mcp.tool()
def check_kit_status() -> str:
    """
    Sprawdź czy kit zmienił się od ostatniego `bootstrap-project.sh` w tym repo.

    Tanie: porównuje commit zapisany w `.ai/.kit-bootstrap.json` z aktualnym HEAD
    kita (git rev-parse/diff --name-only) — nie czyta treści modułów instrukcji.
    Moduły (`modules/*.md`) są i tak czytane live przez `get_bundle`/`get_overlay`,
    więc nigdy nie "gniją" — ten tool dotyczy tylko plików które bootstrap
    **kopiuje** (agents/commands/mcp.json), bo te są statyczną migawką.

    Returns:
        str: Markdown — aktualny / zmienił się (+ lista plików które re-bootstrap
            by nadpisał) / brak stampu / brak lokalnej historii git do porównania.
    """
    resolved = _get_resolved()
    return check_kit_updates(kit_root=resolved.kit_root, workspace_root=resolved.workspace_root)


def _require_workspace() -> Path:
    """Zwróć root repo aplikacji albo wyjaśnij, czego brakuje (nigdy nie zgaduj cwd)."""
    if _workspace_root is None:
        raise BootstrapError(
            "Brak roota repo aplikacji. Uruchom serwer MCP z `--workspace /sciezka/do/repo` "
            "albo ustaw GUIDES_WORKSPACE. Bootstrap nie zapisze do bieżącego katalogu "
            "procesu serwera — to nie musi być twoje repo."
        )
    return _workspace_root


def _bootstrap_kwargs(
    clients: str | None,
    preset: str | None,
    language: str | None,
    codegen: str | None,
) -> dict:
    """Złóż flagi bootstrapu: jawne argumenty narzędzia > ustawienia startowe serwera."""
    resolved = _get_resolved()
    return {
        "kit_root": resolved.kit_root,
        "clients": format_clients_arg(parse_clients(clients) if clients else _clients),
        "preset": preset or _preset or "_base",
        "language": normalize_language(language) if language else resolved.language,
        "codegen": (
            normalize_codegen(codegen, load_manifest(_kit_root)) if codegen else resolved.codegen
        ),
        "from_src": str(resolved.kit_root),
    }


@mcp.tool()
def bootstrap_workspace(
    clients: str | None = None,
    preset: str | None = None,
    language: str | None = None,
    codegen: str | None = None,
    with_overlay: bool = False,
    keep_unselected_clients: bool = False,
    dry_run: bool = True,
) -> str:
    """
    Zainstaluj pliki kita (hooki, agenci, komendy, mcp.json, stamp) w repo aplikacji.

    Jedyne narzędzie MCP, które **zapisuje na dysk** — reszta serwera jest tylko do
    odczytu. Bez tego trzeba sklonować kit lokalnie i ręcznie odpalić
    ``scripts/bootstrap-project.sh``; tu ten sam skrypt uruchamia serwer, który już
    ma wszystkie szablony pod ręką.

    ``dry_run=True`` jest domyślne i nic nie zapisuje: skrypt leci na kopii kitowej
    powierzchni repo w katalogu tymczasowym, a wynikiem jest lista plików, które
    powstałyby, zostałyby nadpisane albo usunięte. Zapis wymaga jawnego
    ``dry_run=False`` — hooki ``PreToolUse`` łapią ``Bash``/``Edit``/``Write``,
    a nie nazwy narzędzi MCP, więc ta domyślka jest tu jedyną bramką.

    Args:
        clients: ``--clients``: all | cursor | claude | codex | vscode | kiro | kilo |
            antigravity | opencode (po przecinku). Domyślnie: wartość startowa serwera.
        preset: Kategoria presetu (``_base``, ``shop``). Domyślnie: preset serwera.
        language: Język prozy ``pl``/``en``. Domyślnie: język bieżącego profilu.
        codegen: ``orval``/``none``/``graphql``. Domyślnie: codegen bieżącego profilu.
        with_overlay: Skopiuj szablon ``.ai/project.md``, jeśli repo go nie ma.
        keep_unselected_clients: Nie usuwaj kitowych plików klientów spoza ``clients``.
        dry_run: ``True`` (domyślnie) — tylko plan. ``False`` — faktyczny zapis.

    Returns:
        str: Markdown — plan zmian (dry run) albo raport z instalacji i stampu.
    """
    try:
        workspace = _require_workspace()
        kwargs = _bootstrap_kwargs(clients, preset, language, codegen)
        if kwargs["kit_root"].resolve() == workspace.resolve():
            raise BootstrapError(
                f"Workspace i kit to ten sam katalog (`{workspace}`). Bootstrap uruchamia się "
                "w repo aplikacji, nie w repo kita."
            )
        kwargs.update(
            with_overlay=with_overlay,
            keep_unselected_clients=keep_unselected_clients,
        )
        flags = (
            f"--preset {kwargs['preset']} --language {kwargs['language']} "
            f"--codegen {kwargs['codegen']} --clients {kwargs['clients']}"
        )
        header = [
            f"- Workspace: `{workspace}`",
            f"- Kit: `{kwargs['kit_root']}`",
            f"- Flagi: `{flags}`",
            "",
        ]

        if dry_run:
            plan = plan_bootstrap(workspace_root=workspace, **kwargs)
            lines = ["# bootstrap_workspace — dry run (nic nie zapisano)", "", *header]
            for title, paths in (
                ("Nowe pliki", plan.created),
                ("Nadpisane", plan.modified),
                ("Usunięte przy sprzątaniu klientów", plan.deleted),
            ):
                if paths:
                    lines.append(f"## {title} ({len(paths)})")
                    lines.append("")
                    lines.extend(f"- `{p}`" for p in paths)
                    lines.append("")
            if plan.unchanged:
                lines.append(f"## Bez zmian ({len(plan.unchanged)})")
                lines.append("")
            if not plan.touches_disk:
                lines.append(
                    "Repo jest już zbootstrapowane tymi flagami — nic by się nie zmieniło."
                )
                lines.append("")
            lines.append(
                "Żeby zastosować: wywołaj ponownie z `dry_run=False`. To jedyne narzędzie "
                "MCP tego serwera, które pisze po repo — hooki kita go nie zatrzymają."
            )
            return "\n".join(lines)

        output = run_bootstrap(target=workspace, **kwargs)
        stamp = workspace / ".ai" / ".kit-bootstrap.json"
        lines = ["# bootstrap_workspace — zainstalowano", "", *header, "```", output, "```", ""]
        stamp_state = "zapisany" if stamp.is_file() else "**BRAK — sprawdź wyjście skryptu**"
        lines.append(f"- Stamp: `{stamp}` — {stamp_state}")
        lines.append("- Zrestartuj IDE w repo aplikacji, żeby wczytało hooki i komendy.")
        return "\n".join(lines)
    except (BootstrapError, ValueError, RuntimeError) as exc:
        return f"# bootstrap_workspace: błąd\n\n{exc}"


@mcp.tool()
def list_modules() -> str:
    """
    Lista wszystkich modułów dostępnych w instruction-kit (manifest).

    Returns:
        str: Markdown z identyfikatorami i tytułami modułów.
    """
    manifest = load_manifest(_kit_root)
    lines = ["# Moduły instruction-kit", ""]
    for module_id, info in sorted(manifest.modules.items()):
        tags = ", ".join(info.tags) if info.tags else "-"
        lines.append(f"- `{module_id}` — {info.title} _(tags: {tags})_")
    return "\n".join(lines)


@mcp.tool()
def get_module(module_id: str) -> str:
    """
    Pobierz pojedynczy moduł instrukcji po identyfikatorze.

    Args:
        module_id: Id modułu z manifestu, np. stack:django-drf:backend-standard.

    Returns:
        str: Treść Markdown modułu.
    """
    manifest = load_manifest(_kit_root)
    info = manifest.modules.get(module_id)
    if info is None:
        return f"Nieznany moduł `{module_id}`."
    if not info.path.is_file():
        return f"Plik modułu nie istnieje: {info.path}"
    return info.path.read_text(encoding="utf-8")


@mcp.tool()
def get_clients() -> str:
    """
    Lista klientów AI skonfigurowanych przy starcie MCP (``--clients`` / GUIDES_CLIENTS).

    Metadane instalacji szablonów — **nie** zmieniają treści bundle.

    Returns:
        str: Markdown z wartością flagi i rozwiniętą listą id klientów.
    """
    flag = format_clients_arg(_clients)
    expanded = expand_clients(_clients)
    lines = [
        "# Clients (MCP metadata)",
        "",
        f"- Flag `--clients`: `{flag}`",
        f"- Expanded: {', '.join(f'`{c}`' for c in expanded)}",
        "",
        "Bundle content is identical for every client. "
        "Use this only to know which IDE packs were intended at bootstrap.",
    ]
    return "\n".join(lines)


@mcp.tool()
def list_presets() -> str:
    """
    Lista dostępnych presetów w instruction-kit (``profiles/*.yaml``).

    Returns:
        str: Markdown z kategoriami (``_base``, ``shop``, …).
    """
    root = _kit_root or find_kit_root()
    profiles_dir = root / "profiles"
    lines = ["# Presety instruction-kit", ""]
    if not profiles_dir.is_dir():
        return "\n".join([*lines, "_Brak katalogu profiles._"])
    for path in sorted(profiles_dir.glob("*.yaml")):
        if path.stem == "_base":
            note = " — fundament stacku (default)"
        elif path.stem == "shop":
            note = " — kategoria e-commerce"
        else:
            note = " — kategoria"
        lines.append(f"- `{path.stem}` — `{path.name}`{note}")
    return "\n".join(lines)


@mcp.resource("guides://index")
def resource_index() -> str:
    """Resource: indeks profilu projektu."""
    return _get_resolved().index_markdown


@mcp.resource("guides://overlay")
def resource_overlay() -> str:
    """Resource: overlay projektu."""
    overlay = _get_resolved().overlay_content
    return overlay if overlay else "_Brak overlay._"


def _register_bundle_resources() -> None:
    """Zarejestruj resources guides://bundle/{name} dynamicznie."""
    resolved = _get_resolved()
    for bundle_name in resolved.bundles:

        def make_handler(name: str):
            def handler() -> str:
                return get_bundle(name)

            handler.__name__ = f"resource_bundle_{name}"
            return handler

        mcp.resource(f"guides://bundle/{bundle_name}")(make_handler(bundle_name))


def main() -> None:
    """Entrypoint CLI serwera MCP."""
    global _profile_path, _kit_root, _workspace_root, _extra_overlays
    global _language_override, _codegen_override, _clients, _preset

    parser = argparse.ArgumentParser(description="Instruction-kit MCP server")
    parser.add_argument(
        "--profile",
        required=False,
        help="Ścieżka do .ai/project.profile.yaml (lokalne nadpisania presetu)",
    )
    parser.add_argument(
        "--preset",
        required=False,
        help="Nazwa kategorii z kita (np. shop; default bootstrapu: _base)",
    )
    parser.add_argument(
        "--workspace",
        required=False,
        help="Root repo aplikacji (overlay .ai/project.md); domyślnie cwd przy --preset",
    )
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="Dodatkowy plik overlay (można podać wielokrotnie)",
    )
    parser.add_argument(
        "--language",
        required=False,
        choices=("pl", "en", "PL", "EN"),
        help="Język prozy instrukcji (pl|en); tytuły issue/PR zawsze EN. Domyślnie: profil lub pl",
    )
    parser.add_argument(
        "--codegen",
        required=False,
        choices=("orval", "none", "graphql", "ORVAL", "NONE", "GRAPHQL"),
        help=(
            "Generator klienta API: orval (schema → frontend/src/api/generated + mutatory) "
            "| none (tool-agnostyczny/ręczny) | graphql (GraphQL zamiast REST). "
            "Domyślnie: codegen: w profilu albo orval"
        ),
    )
    parser.add_argument(
        "--kit-root",
        required=False,
        help="Root repozytorium instruction-kit (domyślnie: auto-detect)",
    )
    parser.add_argument(
        "--clients",
        required=False,
        default=None,
        help=(
            "Metadane klientów AI: all | cursor | claude | codex | vscode | kiro | kilo | "
            "antigravity | opencode (lista po przecinku; alias copilot→vscode). Nie zmienia bundle."
        ),
    )
    args = parser.parse_args()

    if args.kit_root:
        _kit_root = Path(args.kit_root).resolve()
    elif os.environ.get("GUIDES_KIT_ROOT"):
        _kit_root = Path(os.environ["GUIDES_KIT_ROOT"]).resolve()

    if args.workspace:
        _workspace_root = Path(args.workspace).resolve()
    elif os.environ.get("GUIDES_WORKSPACE"):
        _workspace_root = Path(os.environ["GUIDES_WORKSPACE"]).resolve()

    _extra_overlays = [Path(p).resolve() for p in args.overlay]
    if os.environ.get("GUIDES_OVERLAY"):
        _extra_overlays.append(Path(os.environ["GUIDES_OVERLAY"]).resolve())

    lang_cli = args.language or os.environ.get("GUIDES_LANGUAGE")
    if lang_cli:
        _language_override = normalize_language(lang_cli)

    codegen_cli = args.codegen or os.environ.get("GUIDES_CODEGEN")
    if codegen_cli:
        # Dozwolone wartości zna manifest (mappings.substitutions.codegen), nie ten plik.
        _codegen_override = normalize_codegen(codegen_cli, load_manifest(_kit_root))

    clients_raw = args.clients if args.clients is not None else os.environ.get("GUIDES_CLIENTS")
    try:
        _clients = parse_clients(clients_raw)
    except ValueError as exc:
        parser.error(f"--clients: {exc}")

    preset = args.preset or os.environ.get("GUIDES_PRESET")
    _preset = preset
    profile_arg = args.profile
    env_profile = os.environ.get("GUIDES_PROFILE")

    if profile_arg and preset:
        parser.error("Podaj albo --profile, albo --preset — nie oba naraz")

    if profile_arg:
        _profile_path = Path(profile_arg).resolve()
    elif preset:
        kit = _kit_root or find_kit_root()
        _kit_root = kit
        _profile_path = resolve_preset_path(preset, kit)
        if _workspace_root is None:
            _workspace_root = Path.cwd().resolve()
    elif env_profile:
        _profile_path = Path(env_profile).resolve()

    if _profile_path is None:
        parser.error(
            "Wymagany --profile PATH, --preset NAME albo GUIDES_PROFILE / GUIDES_PRESET"
        )

    _register_bundle_resources()
    mcp.run()


if __name__ == "__main__":
    main()
