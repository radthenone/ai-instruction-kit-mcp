"""Składanie bundle'i instrukcji na podstawie profilu projektu."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from guides.manifest import Manifest, load_manifest

LANGUAGE_MODULE_IDS: frozenset[str] = frozenset(
    {"core:language-pl", "core:language-en"}
)


def normalize_language(raw: str | None) -> str:
    """
    Znormalizuj kod języka instrukcji do ``pl`` albo ``en``.

    Args:
        raw: Surowa wartość z profilu, CLI albo env (np. ``PL``, ``en-US``, ``english``).

    Returns:
        str: ``en`` dla angielskiego (tag ``en`` / ``eng`` / ``english``), inaczej ``pl``.
    """
    code = (raw or "pl").strip().lower().replace("_", "-")
    if not code:
        return "pl"
    primary = code.split("-", 1)[0]
    if code in {"en", "eng", "english"} or primary in {"en", "eng"}:
        return "en"
    if code in {"pl", "pol", "polish", "polski"} or primary in {"pl", "pol"}:
        return "pl"
    return "pl"


def language_module_id(language: str) -> str:
    """
    Zwróć ID modułu językowego dla znormalizowanego języka.

    Args:
        language: ``pl`` albo ``en`` (wynik ``normalize_language``).

    Returns:
        str: ``core:language-en`` albo ``core:language-pl``.
    """
    return "core:language-en" if language == "en" else "core:language-pl"


def _remap_language_modules(module_ids: list[str], language: str) -> list[str]:
    """
    Zastąp wszystkie moduły ``core:language-*`` jednym właściwym dla ``language``.

    Args:
        module_ids: Lista ID modułów (kolejność zachowana poza scaleniem language).
        language: Znormalizowany język (``pl`` / ``en``).

    Returns:
        list[str]: Lista bez duplikatów language; pierwszy slot language → docelowy moduł.
    """
    target = language_module_id(language)
    result: list[str] = []
    language_placed = False
    for module_id in module_ids:
        if module_id in LANGUAGE_MODULE_IDS:
            if not language_placed:
                result.append(target)
                language_placed = True
            continue
        result.append(module_id)
    return result


# Alias ID w bundle/include (stare nazwy → kanoniczne z manifestu).
_MODULE_ID_ALIASES: dict[str, str] = {
    "capability:files-storage": "capability:files",
}


def normalize_module_id(module_id: str) -> str:
    """
    Znormalizuj ID modułu (aliasy kompatybilności).

    Args:
        module_id: Surowy identyfikator z profilu / bundle.

    Returns:
        str: Kanoniczne ID z manifestu (lub bez zmian, gdy brak aliasu).
    """
    return _MODULE_ID_ALIASES.get(module_id, module_id)


def _normalize_module_ids(module_ids: list[str]) -> list[str]:
    """Zastosuj ``normalize_module_id`` z zachowaniem kolejności i bez duplikatów."""
    return _merge_unique([], [normalize_module_id(mid) for mid in module_ids])


@dataclass(frozen=True)
class ResolvedBundle:
    """Gotowy bundle — lista modułów i połączona treść Markdown."""

    name: str
    module_ids: tuple[str, ...]
    content: str
    missing_modules: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedProfile:
    """Wynik rozwiązania profilu projektu."""

    name: str
    language: str
    kit_root: Path
    profile_path: Path
    workspace_root: Path
    enabled_module_ids: tuple[str, ...]
    bundles: dict[str, ResolvedBundle]
    overlay_content: str
    index_markdown: str


def _read_yaml(path: Path) -> dict[str, Any]:
    """Wczytaj plik YAML; pusty plik → pusty dict."""
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _merge_unique(base: list[str], extra: list[str]) -> list[str]:
    """Połącz listy modułów zachowując kolejność i unikalność."""
    seen: set[str] = set()
    result: list[str] = []
    for item in [*base, *extra]:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_bundle_configs(
    base: dict[str, list[str]],
    extra: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Scal konfiguracje bundle'ów — moduły z extra dopisują do base, nie zastępują."""
    result: dict[str, list[str]] = {key: list(modules) for key, modules in base.items()}
    for key, modules in extra.items():
        result[key] = _merge_unique(result.get(key, []), list(modules))
    return result


def _resolve_extends(
    profile_data: dict[str, Any],
    kit_root: Path,
    visited: set[Path] | None = None,
) -> dict[str, Any]:
    """
    Rozwiąż łańcuch `extends` w profilu (preset → profil projektu).

    Args:
        profile_data: Dane bieżącego profilu.
        kit_root: Root instruction-kit.
        visited: Ścieżki już odwiedzone (ochrona przed cyklami).

    Returns:
        dict: Scalone dane profilu (extends + nadpisania).
    """
    visited = visited or set()
    extends = profile_data.get("extends")
    if not extends:
        return profile_data

    extends_path = Path(extends)
    if not extends_path.is_absolute():
        extends_path = kit_root / extends_path

    extends_path = extends_path.resolve()
    if extends_path in visited:
        raise ValueError(f"Cykliczne extends w profilu: {extends_path}")

    visited.add(extends_path)
    base_data = _resolve_extends(_read_yaml(extends_path), kit_root, visited)

    merged: dict[str, Any] = {**base_data, **profile_data}
    merged.pop("extends", None)

    if "bundles" in base_data or "bundles" in profile_data:
        merged_bundles: dict[str, list[str]] = {}
        for key in set(base_data.get("bundles", {})) | set(profile_data.get("bundles", {})):
            base_modules = base_data.get("bundles", {}).get(key, [])
            profile_modules = profile_data.get("bundles", {}).get(key, [])
            merged_bundles[key] = _merge_unique(list(base_modules), list(profile_modules))
        merged["bundles"] = merged_bundles

    if "include" in base_data or "include" in profile_data:
        merged["include"] = _merge_unique(
            list(base_data.get("include", [])),
            list(profile_data.get("include", [])),
        )

    if "decisions" in base_data or "decisions" in profile_data:
        merged_decisions = dict(base_data.get("decisions", {}))
        merged_decisions.update(profile_data.get("decisions", {}))
        merged["decisions"] = merged_decisions

    if "capabilities" in base_data or "capabilities" in profile_data:
        merged["capabilities"] = _merge_unique(
            list(base_data.get("capabilities", [])),
            list(profile_data.get("capabilities", [])),
        )

    if "domains" in base_data or "domains" in profile_data:
        merged["domains"] = _merge_unique(
            list(base_data.get("domains", [])),
            list(profile_data.get("domains", [])),
        )

    if "patterns" in base_data or "patterns" in profile_data:
        merged["patterns"] = _merge_unique(
            list(base_data.get("patterns", [])),
            list(profile_data.get("patterns", [])),
        )

    return merged


def _capability_module_ids(capabilities: list[str]) -> list[str]:
    """Zmapuj listę capabilities z profilu na ID modułów."""
    mapping = {
        "auth": "capability:auth",
        "files": "capability:files",
        "files-storage": "capability:files",  # alias kompat
        "payments": "capability:payments",
        "storage": "capability:files",
    }
    return [mapping[c] for c in capabilities if c in mapping]


def _domain_module_ids(domains: list[str]) -> list[str]:
    """Zmapuj listę domains z profilu na ID modułów."""
    mapping = {
        "shop": "domain:shop",
        "ecommerce": "domain:shop",
    }
    return [mapping[d] for d in domains if d in mapping]


def _decision_module_ids(decisions: dict[str, Any]) -> list[str]:
    """
    Zmapuj sloty decisions z profilu na moduły infra:*.

    Sloty:
        database, cache, queue, storage, tasks
    """
    slot_mapping: dict[str, dict[str, str]] = {
        "database": {
            "postgres": "infra:database:postgres",
        },
        "cache": {
            "redis": "infra:cache:redis",
        },
        "queue": {
            "redis": "infra:queue:redis",
            "rabbitmq": "infra:queue:rabbitmq",
        },
        "storage": {
            "s3": "infra:storage:s3",
            "minio": "infra:storage:s3",
            "aws": "infra:storage:s3",
        },
        "tasks": {
            "celery": "infra:tasks:celery",
        },
    }
    module_ids: list[str] = []
    for slot, value in decisions.items():
        if not isinstance(value, str):
            continue
        module_id = slot_mapping.get(slot, {}).get(value)
        if module_id:
            module_ids.append(module_id)
    return module_ids


def _inject_infra_bundles(
    bundles_config: dict[str, list[str]],
    profile_data: dict[str, Any],
) -> dict[str, list[str]]:
    """Dopisz moduły infra:* do bundle infra i devops na podstawie decisions."""
    infra_modules = _decision_module_ids(profile_data.get("decisions", {}))
    if not infra_modules:
        return bundles_config

    return _merge_bundle_configs(
        bundles_config,
        {
            "infra": infra_modules,
            "devops": _merge_unique(["arch:ci-cd"], infra_modules),
            "full": infra_modules,
        },
    )


def _collect_module_ids(profile_data: dict[str, Any], manifest: Manifest) -> list[str]:
    """Zbierz pełną listę modułów włączonych przez profil."""
    module_ids: list[str] = list(profile_data.get("include", []))

    stacks: dict[str, Any] = profile_data.get("stacks", {})
    if stacks.get("django-drf"):
        module_ids.extend(
            [
                "stack:django-drf",
                "stack:django-drf:structure",
                "stack:django-drf:backend-standard",
                "stack:django-drf:backend-instructions",
            ]
        )
    if stacks.get("expo-router"):
        module_ids.extend(
            [
                "stack:expo-router",
                "stack:expo-router:structure",
                "stack:expo-router:frontend-instructions",
            ]
        )

    module_ids.extend(_capability_module_ids(profile_data.get("capabilities", [])))
    module_ids.extend(_domain_module_ids(profile_data.get("domains", [])))

    patterns: list[str] = profile_data.get("patterns", [])
    pattern_map = {
        "capability-provider": "pattern:capability-provider",
        "capability-overview": "pattern:capability-overview",
        "providers-and-settings": "pattern:providers-and-settings",
        "gateway-nginx": "pattern:gateway-nginx",
        "microservices-auth": "pattern:microservices-auth",
        "repo-first": "core:repo-first",
    }
    for pattern in patterns:
        mapped = pattern_map.get(pattern, pattern)
        module_ids.append(mapped)

    module_ids.extend(_decision_module_ids(profile_data.get("decisions", {})))

    language = normalize_language(str(profile_data.get("language", "pl")))
    lang_module = language_module_id(language)

    # Domyślnie core jeśli profil nie wyłącza
    if profile_data.get("core", True):
        module_ids = _merge_unique(
            ["core:repo-first", lang_module, "core:external-knowledge"],
            module_ids,
        )

    module_ids = _remap_language_modules(module_ids, language)
    module_ids = _normalize_module_ids(module_ids)

    # Walidacja — tylko znane moduły
    return [mid for mid in module_ids if mid in manifest.modules]


def _build_bundle_content(
    bundle_name: str,
    module_ids: list[str],
    manifest: Manifest,
) -> ResolvedBundle:
    """Złóż treść Markdown bundle'a z plików modułów."""
    parts: list[str] = []
    missing: list[str] = []
    canonical_ids = _normalize_module_ids(module_ids)

    for module_id in canonical_ids:
        info = manifest.modules.get(module_id)
        if info is None:
            missing.append(module_id)
            continue
        if not info.path.is_file():
            missing.append(module_id)
            continue

        body = info.path.read_text(encoding="utf-8").strip()
        parts.append(f"<!-- module:{module_id} -->\n\n{body}")

    header = f"# Bundle: {bundle_name}\n\n"
    content = header + "\n\n---\n\n".join(parts) if parts else header + "_Brak modułów._"

    return ResolvedBundle(
        name=bundle_name,
        module_ids=tuple(canonical_ids),
        content=content,
        missing_modules=tuple(missing),
    )


def _load_overlays(
    profile_data: dict[str, Any],
    workspace_root: Path,
    extra_overlays: list[Path] | None = None,
) -> str:
    """
    Wczytaj pliki overlay wskazane w profilu oraz dodatkowe ścieżki CLI.

    Args:
        profile_data: Dane profilu (klucz ``overlays``).
        workspace_root: Root repo aplikacji (ścieżki względne).
        extra_overlays: Dodatkowe pliki z ``--overlay`` (opcjonalne).

    Returns:
        str: Połączona treść overlay albo pusty string.
    """
    overlay_paths: list[str] = list(profile_data.get("overlays", []))
    parts: list[str] = []
    seen: set[Path] = set()

    def _append(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            return
        seen.add(resolved)
        parts.append(resolved.read_text(encoding="utf-8").strip())

    for rel in overlay_paths:
        path = Path(rel)
        if not path.is_absolute():
            path = workspace_root / path
        _append(path)

    for path in extra_overlays or []:
        _append(path)

    # Zero-file preset: domyślny overlay projektu, jeśli istnieje.
    default_overlay = workspace_root / ".ai" / "project.md"
    _append(default_overlay)

    if not parts:
        return ""
    return "# Overlay projektu\n\n" + "\n\n---\n\n".join(parts)


def resolve_preset_path(preset: str, kit_root: Path) -> Path:
    """
    Znajdź plik presetu w instruction-kit.

    Args:
        preset: Nazwa kategorii (np. ``shop``) albo względna ścieżka ``profiles/….yaml``.
        kit_root: Root kita (repo albo ``guides/_data`` w wheel).

    Returns:
        Path: Absolutna ścieżka do pliku YAML presetu.

    Raises:
        FileNotFoundError: Gdy preset nie istnieje.
    """
    raw = preset.strip().removesuffix(".yaml").removesuffix(".yml")
    candidates: list[Path] = []
    if raw.startswith("profiles/"):
        candidates.append(kit_root / f"{raw}.yaml")
    else:
        candidates.append(kit_root / "profiles" / f"{raw}.yaml")
        candidates.append(kit_root / f"{raw}.yaml")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    available = sorted(p.stem for p in (kit_root / "profiles").glob("*.yaml"))
    hint = ", ".join(available) if available else "(brak profiles/*.yaml)"
    raise FileNotFoundError(
        f"Nie znaleziono presetu `{preset}` w `{kit_root}`. Dostępne: {hint}"
    )


def resolve_profile(
    profile_path: Path,
    kit_root: Path | None = None,
    *,
    workspace_root: Path | None = None,
    extra_overlays: list[Path] | None = None,
    language_override: str | None = None,
) -> ResolvedProfile:
    """
    Rozwiąż profil projektu do bundle'i i indeksu.

    Args:
        profile_path: Ścieżka do profilu (``.ai/project.profile.yaml`` albo preset kita).
        kit_root: Opcjonalny root instruction-kit.
        workspace_root: Root repo aplikacji (overlay). Gdy brak — ``profile_path.parent.parent``
            dla lokalnego ``.ai/…``, inaczej ``cwd``.
        extra_overlays: Dodatkowe pliki overlay z CLI.
        language_override: Nadpisanie języka z CLI/env (``pl`` / ``en``); ma pierwszeństwo
            przed ``language`` w YAML profilu.

    Returns:
        ResolvedProfile: Gotowe bundle'e i metadane profilu.
    """
    profile_path = profile_path.resolve()
    manifest = load_manifest(kit_root)

    if workspace_root is not None:
        resolved_workspace = workspace_root.resolve()
    elif profile_path.parent.name == ".ai":
        resolved_workspace = profile_path.parent.parent
    else:
        # Preset z kita — workspace to katalog roboczy konsumenta.
        resolved_workspace = Path.cwd().resolve()

    raw_profile = _read_yaml(profile_path)
    profile_data = _resolve_extends(raw_profile, manifest.kit_root)

    language = normalize_language(
        language_override
        if language_override is not None
        else str(profile_data.get("language", "pl"))
    )
    profile_data = {**profile_data, "language": language}

    enabled_modules = _collect_module_ids(profile_data, manifest)

    bundles_config = _merge_bundle_configs(
        manifest.default_bundles,
        profile_data.get("bundles", {}),
    )
    bundles_config = _inject_infra_bundles(bundles_config, profile_data)
    bundles_config = {
        name: _remap_language_modules(list(module_ids), language)
        for name, module_ids in bundles_config.items()
    }

    bundles: dict[str, ResolvedBundle] = {}
    for bundle_name, module_ids in bundles_config.items():
        bundles[bundle_name] = _build_bundle_content(bundle_name, module_ids, manifest)

    all_from_bundles: list[str] = []
    for bundle in bundles.values():
        all_from_bundles.extend(list(bundle.module_ids))
    enabled_modules = _merge_unique(enabled_modules, all_from_bundles)
    enabled_modules = _remap_language_modules(enabled_modules, language)
    enabled_modules = [mid for mid in enabled_modules if mid in manifest.modules]

    overlay_content = _load_overlays(profile_data, resolved_workspace, extra_overlays)

    index_lines = [
        f"# Instruction index: {profile_data.get('name', resolved_workspace.name)}",
        "",
        f"- Język: {language}",
        f"- Moduł języka: `{language_module_id(language)}`",
        f"- Profil: `{profile_path}`",
        f"- Workspace: `{resolved_workspace}`",
        f"- Kit root: `{manifest.kit_root}`",
        "",
        "## Włączone moduły",
        "",
    ]
    for module_id in enabled_modules:
        info = manifest.modules[module_id]
        index_lines.append(f"- `{module_id}` — {info.title}")

    index_lines.extend(["", "## Bundle'e", ""])
    for name, bundle in bundles.items():
        missing_note = f" (brak: {', '.join(bundle.missing_modules)})" if bundle.missing_modules else ""
        index_lines.append(f"- `{name}` — {len(bundle.module_ids)} modułów{missing_note}")

    if overlay_content:
        index_lines.extend(["", "## Overlay", "", "Projekt ma lokalny overlay — użyj `guides://overlay`."])

    return ResolvedProfile(
        name=str(profile_data.get("name", resolved_workspace.name)),
        language=language,
        kit_root=manifest.kit_root,
        profile_path=profile_path,
        workspace_root=resolved_workspace,
        enabled_module_ids=tuple(enabled_modules),
        bundles=bundles,
        overlay_content=overlay_content,
        index_markdown="\n".join(index_lines),
    )
