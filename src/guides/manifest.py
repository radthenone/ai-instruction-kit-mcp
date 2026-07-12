"""Ładowanie manifest.yaml i metadanych modułów."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModuleInfo:
    """Metadane pojedynczego modułu instrukcji."""

    module_id: str
    path: Path
    title: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    """Zmanifestowana kolekcja modułów i domyślnych bundle'i."""

    kit_root: Path
    modules: dict[str, ModuleInfo]
    default_bundles: dict[str, list[str]]


def find_kit_root(start: Path | None = None) -> Path:
    """
    Znajdź katalog root instruction-kit (zawiera manifest.yaml).

    Args:
        start: Punkt startowy wyszukiwania; domyślnie katalog pakietu guides.

    Returns:
        Path: Absolutna ścieżka do root repozytorium instruction-kit.

    Raises:
        FileNotFoundError: Gdy manifest.yaml nie zostanie znaleziony.
    """
    env_root = os.environ.get("GUIDES_KIT_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # Zainstalowany pakiet (uvx --from git+...)
    pkg_data = Path(__file__).resolve().parent / "_data"
    if (pkg_data / "manifest.yaml").is_file():
        return pkg_data

    current = (start or Path(__file__).resolve()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        manifest_path = candidate / "manifest.yaml"
        if manifest_path.is_file():
            return candidate

    raise FileNotFoundError(
        "Nie znaleziono manifest.yaml — ustaw GUIDES_KIT_ROOT lub użyj uvx z repozytorium git."
    )


def load_manifest(kit_root: Path | None = None) -> Manifest:
    """
    Wczytaj manifest.yaml z instruction-kit.

    Args:
        kit_root: Opcjonalny root kit; gdy brak — wykrywany automatycznie.

    Returns:
        Manifest: Sparsowany manifest z modułami i bundle'ami.
    """
    root = kit_root or find_kit_root()
    manifest_path = root / "manifest.yaml"
    raw: dict[str, Any] = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    modules: dict[str, ModuleInfo] = {}
    for module_id, meta in raw.get("modules", {}).items():
        rel_path = meta["path"]
        modules[module_id] = ModuleInfo(
            module_id=module_id,
            path=root / rel_path,
            title=meta.get("title", module_id),
            tags=tuple(meta.get("tags", [])),
        )

    default_bundles: dict[str, list[str]] = {
        name: list(module_ids)
        for name, module_ids in raw.get("default_bundles", {}).items()
    }

    return Manifest(kit_root=root, modules=modules, default_bundles=default_bundles)
