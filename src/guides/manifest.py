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
class VariantRule:
    """Reguła wariantu/substytucji: moduł bazowy + dozwolone wartości."""

    base: str
    default: str
    values: dict[str, str]

    def module_for(self, value: str | None) -> str:
        """
        Moduł dla wartości Decyzji, z fallbackiem na domyślną.

        Pusta reguła (Kit Root ze starym manifestem, bez sekcji ``mappings``) zwraca
        moduł bazowy — Substytucja i Wariant stają się wtedy tożsamością zamiast
        wywracać serwer.

        Args:
            value: Wartość z profilu (dowolny case) albo ``None``.

        Returns:
            str: ID modułu wariantu albo moduł bazowy, gdy reguła jest pusta.
        """
        key = value.strip().lower() if isinstance(value, str) else ""
        return self.values.get(key) or self.values.get(self.default) or self.base

    def normalize(self, value: str | None) -> str:
        """
        Znormalizuj wartość Decyzji do jednej z dozwolonych.

        Args:
            value: Wartość z profilu, CLI albo env.

        Returns:
            str: Rozpoznana wartość albo ``default``.
        """
        key = value.strip().lower() if isinstance(value, str) else ""
        return key if key in self.values else self.default

    def knows(self, value: str | None) -> bool:
        """
        Czy reguła zna tę wartość?

        Args:
            value: Wartość z profilu.

        Returns:
            bool: ``True`` gdy wartość jest na liście dozwolonych.
        """
        key = value.strip().lower() if isinstance(value, str) else ""
        return key in self.values


_EMPTY_RULE = VariantRule(base="", default="", values={})


@dataclass(frozen=True)
class Mappings:
    """
    Reguły przekładu Profilu na Module ID (ADR-0001).

    Jedyne źródło wiedzy o tym, jakie technologie Kit zna — `resolver` ich nie duplikuje.
    """

    stacks: dict[str, list[str]]
    capabilities: dict[str, str]
    domains: dict[str, str]
    patterns: dict[str, str]
    slots: dict[str, dict[str, str]]
    variants: dict[str, VariantRule]
    substitutions: dict[str, VariantRule]
    languages: VariantRule
    module_aliases: dict[str, str]
    name_aliases: dict[str, str]

    def rule(self, slot: str) -> VariantRule:
        """
        Reguła Wariantu albo Substytucji dla Slotu.

        Args:
            slot: Nazwa Slotu (np. ``auth``, ``codegen``).

        Returns:
            VariantRule: Reguła; pusta, gdy manifest jej nie zna.
        """
        return self.variants.get(slot) or self.substitutions.get(slot) or _EMPTY_RULE

    def all_module_ids(self) -> set[str]:
        """
        Wszystkie Module ID występujące po prawej stronie mapowań.

        Returns:
            set[str]: ID do sprawdzenia względem rejestru modułów.
        """
        found: set[str] = set()
        for modules in self.stacks.values():
            found.update(modules)
        for simple in (self.capabilities, self.domains, self.patterns):
            found.update(simple.values())
        for slot in self.slots.values():
            found.update(slot.values())
        for rule in (*self.variants.values(), *self.substitutions.values(), self.languages):
            found.add(rule.base)
            found.update(rule.values.values())
        found.update(self.module_aliases.values())
        found.discard("")
        return found

    def canonical_module_id(self, module_id: str) -> str:
        """
        Rozwiń Alias Module ID do postaci kanonicznej.

        Args:
            module_id: Surowe ID z profilu albo bundle'a.

        Returns:
            str: Kanoniczne ID (bez zmian, gdy nie jest Aliasem).
        """
        return self.module_aliases.get(module_id, module_id)

    def canonical_name(self, name: str) -> str:
        """
        Rozwiń Alias nazwy sekcji profilu (Capability / Domain / Pattern).

        Args:
            name: Nazwa z profilu.

        Returns:
            str: Kanoniczna nazwa (bez zmian, gdy nie jest Aliasem).
        """
        return self.name_aliases.get(name, name)


@dataclass(frozen=True)
class Manifest:
    """Zmanifestowana kolekcja modułów, domyślnych bundle'i i mapowań."""

    kit_root: Path
    modules: dict[str, ModuleInfo]
    default_bundles: dict[str, list[str]]
    mappings: Mappings


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

    return Manifest(
        kit_root=root,
        modules=modules,
        default_bundles=default_bundles,
        mappings=_load_mappings(raw.get("mappings", {})),
    )


def _variant_rule(raw: dict[str, Any]) -> VariantRule:
    """
    Zbuduj ``VariantRule`` z sekcji manifestu.

    Args:
        raw: Fragment YAML z kluczami ``base`` / ``default`` / ``values``.

    Returns:
        VariantRule: Reguła wariantu albo substytucji.
    """
    values = {str(key): str(value) for key, value in raw.get("values", {}).items()}
    default = str(raw.get("default", ""))
    if default not in values:
        default = next(iter(values), "")
    return VariantRule(base=str(raw.get("base", "")), default=default, values=values)


def _load_mappings(raw: dict[str, Any]) -> Mappings:
    """
    Wczytaj sekcję ``mappings`` manifestu.

    Args:
        raw: Zawartość klucza ``mappings`` (pusty dict gdy brak).

    Returns:
        Mappings: Reguły przekładu Profilu na Module ID.
    """
    return Mappings(
        stacks={
            str(name): [str(mid) for mid in modules]
            for name, modules in raw.get("stacks", {}).items()
        },
        capabilities={str(k): str(v) for k, v in raw.get("capabilities", {}).items()},
        domains={str(k): str(v) for k, v in raw.get("domains", {}).items()},
        patterns={str(k): str(v) for k, v in raw.get("patterns", {}).items()},
        slots={
            str(slot): {str(value): str(mid) for value, mid in values.items()}
            for slot, values in raw.get("slots", {}).items()
        },
        variants={
            str(name): _variant_rule(rule) for name, rule in raw.get("variants", {}).items()
        },
        substitutions={
            str(name): _variant_rule(rule) for name, rule in raw.get("substitutions", {}).items()
        },
        languages=_variant_rule(raw.get("languages", {})),
        module_aliases={
            str(k): str(v) for k, v in raw.get("aliases", {}).get("modules", {}).items()
        },
        name_aliases={
            str(k): str(v) for k, v in raw.get("aliases", {}).get("names", {}).items()
        },
    )
