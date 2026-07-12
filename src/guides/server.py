"""Serwer MCP FastMCP — wystawia instrukcje projektu jako tools i resources."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from guides.manifest import load_manifest
from guides.resolver import resolve_profile

mcp = FastMCP(
    "project-guides",
    instructions=(
        "Dostarcza modułowe instrukcje architektury i stacku dla projektu. "
        "Przed pracą nad backendem pobierz bundle backend; nad frontendem — frontend; "
        "nad architekturą/infra — architecture. Overlay projektu zawiera unikalne ścieżki i taski."
    ),
)

_profile_path: Path | None = None
_kit_root: Path | None = None


def _get_profile_path() -> Path:
    """Zwróć ścieżkę profilu — z CLI lub env GUIDES_PROFILE."""
    if _profile_path is not None:
        return _profile_path
    env_path = os.environ.get("GUIDES_PROFILE")
    if env_path:
        return Path(env_path).resolve()
    raise RuntimeError(
        "Brak profilu projektu. Uruchom z --profile <ścieżka> lub ustaw GUIDES_PROFILE."
    )


def _get_resolved():
    """Rozwiąż profil (cache per request — profil rzadko się zmienia w sesji)."""
    return resolve_profile(_get_profile_path(), kit_root=_kit_root)


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
    resolved = resolve_profile(_get_profile_path(), kit_root=_kit_root)
    for bundle_name in resolved.bundles:

        def make_handler(name: str):
            def handler() -> str:
                return get_bundle(name)

            handler.__name__ = f"resource_bundle_{name}"
            return handler

        mcp.resource(f"guides://bundle/{bundle_name}")(make_handler(bundle_name))


def main() -> None:
    """Entrypoint CLI serwera MCP."""
    global _profile_path, _kit_root

    parser = argparse.ArgumentParser(description="Instruction-kit MCP server")
    parser.add_argument(
        "--profile",
        required=False,
        help="Ścieżka do .ai/project.profile.yaml projektu",
    )
    parser.add_argument(
        "--kit-root",
        required=False,
        help="Root repozytorium instruction-kit (domyślnie: auto-detect)",
    )
    args = parser.parse_args()

    if args.kit_root:
        _kit_root = Path(args.kit_root).resolve()
    elif os.environ.get("GUIDES_KIT_ROOT"):
        _kit_root = Path(os.environ["GUIDES_KIT_ROOT"]).resolve()

    if args.profile:
        _profile_path = Path(args.profile).resolve()
    elif os.environ.get("GUIDES_PROFILE"):
        _profile_path = Path(os.environ["GUIDES_PROFILE"]).resolve()

    if _profile_path is None:
        parser.error("Wymagany argument --profile lub zmienna GUIDES_PROFILE")

    _register_bundle_resources()
    mcp.run()


if __name__ == "__main__":
    main()
