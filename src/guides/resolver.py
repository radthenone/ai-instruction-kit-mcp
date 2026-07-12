"""Składanie bundle'i instrukcji na podstawie profilu projektu."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from guides.manifest import Manifest, load_manifest


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
        "files": "capability:files-storage",
        "files-storage": "capability:files-storage",
        "payments": "capability:payments",
        "storage": "capability:files-storage",
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

    # Domyślnie core jeśli profil nie wyłącza
    if profile_data.get("core", True):
        module_ids = _merge_unique(
            ["core:repo-first", "core:language-pl", "core:external-knowledge"],
            module_ids,
        )

    # Walidacja — tylko znane moduły
    return [mid for mid in _merge_unique([], module_ids) if mid in manifest.modules]


def _build_bundle_content(
    bundle_name: str,
    module_ids: list[str],
    manifest: Manifest,
) -> ResolvedBundle:
    """Złóż treść Markdown bundle'a z plików modułów."""
    parts: list[str] = []
    missing: list[str] = []

    for module_id in module_ids:
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
        module_ids=tuple(module_ids),
        content=content,
        missing_modules=tuple(missing),
    )


def _load_overlays(profile_data: dict[str, Any], workspace_root: Path) -> str:
    """Wczytaj pliki overlay wskazane w profilu."""
    overlay_paths: list[str] = profile_data.get("overlays", [])
    parts: list[str] = []

    for rel in overlay_paths:
        path = Path(rel)
        if not path.is_absolute():
            path = workspace_root / path
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())

    if not parts:
        return ""
    return "# Overlay projektu\n\n" + "\n\n---\n\n".join(parts)


def resolve_profile(
    profile_path: Path,
    kit_root: Path | None = None,
) -> ResolvedProfile:
    """
    Rozwiąż profil projektu do bundle'i i indeksu.

    Args:
        profile_path: Ścieżka do `.ai/project.profile.yaml`.
        kit_root: Opcjonalny root instruction-kit.

    Returns:
        ResolvedProfile: Gotowe bundle'e i metadane profilu.
    """
    profile_path = profile_path.resolve()
    workspace_root = profile_path.parent.parent
    manifest = load_manifest(kit_root)

    raw_profile = _read_yaml(profile_path)
    profile_data = _resolve_extends(raw_profile, manifest.kit_root)

    enabled_modules = _collect_module_ids(profile_data, manifest)

    bundles_config = _merge_bundle_configs(
        manifest.default_bundles,
        profile_data.get("bundles", {}),
    )
    bundles_config = _inject_infra_bundles(bundles_config, profile_data)

    bundles: dict[str, ResolvedBundle] = {}
    for bundle_name, module_ids in bundles_config.items():
        bundles[bundle_name] = _build_bundle_content(bundle_name, module_ids, manifest)

    all_from_bundles: list[str] = []
    for bundle in bundles.values():
        all_from_bundles.extend(list(bundle.module_ids))
    enabled_modules = _merge_unique(enabled_modules, all_from_bundles)
    enabled_modules = [mid for mid in enabled_modules if mid in manifest.modules]

    overlay_content = _load_overlays(profile_data, workspace_root)

    index_lines = [
        f"# Instruction index: {profile_data.get('name', workspace_root.name)}",
        "",
        f"- Język: {profile_data.get('language', 'pl')}",
        f"- Profil: `{profile_path}`",
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
        name=str(profile_data.get("name", workspace_root.name)),
        language=str(profile_data.get("language", "pl")),
        kit_root=manifest.kit_root,
        profile_path=profile_path,
        workspace_root=workspace_root,
        enabled_module_ids=tuple(enabled_modules),
        bundles=bundles,
        overlay_content=overlay_content,
        index_markdown="\n".join(index_lines),
    )
