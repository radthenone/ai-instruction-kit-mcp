"""Składanie bundle'i instrukcji na podstawie profilu projektu."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from guides.manifest import BundleRule, Manifest, Mappings, load_manifest
from guides.host_profile import VPS_LIGHTWEIGHT_MODULE, detect_host_profile

CODEGEN_SLOT = "codegen"
AUTH_SLOT = "auth"

TIER_ORDER = ("backend", "web", "mobile")
TIER_NONE = "none"
EXPO_STRIPE_MODULE = "capability:payments:expo-stripe"
API_CONTRACT_BASE = "arch:api-contract"

MIGRATION_NOTICE = (
    "⚠ Stara konfiguracja: brak `.ai/project.profile.yaml` albo start serwera "
    "z `--preset` / `--profile` / `--codegen`. Uruchom `kit-ai reload` — zapisze profil "
    "z Tierami (puste Tiery = sam core)."
)


def normalize_codegen(raw: str | None, manifest: Manifest) -> str:
    """
    Znormalizuj wybór generatora klienta API do wartości znanej manifestowi.

    Manifest jest wymagany — dozwolone wartości są danymi (ADR-0001), a domyślne
    doczytywanie z auto-wykrytego Kit Root odpowiadałoby na inny Kit niż ten,
    z którego rozwiązywany jest profil.

    Args:
        raw: Wartość z CLI/env/profilu YAML (dowolny case, może być ``None``).
        manifest: Manifest z sekcją ``mappings.substitutions.codegen``.

    Returns:
        str: ``orval`` (Orval — schema → `frontend/src/api/generated` + mutatory,
            **default**), ``none`` (tool-agnostyczny wygenerowany klient REST — konkret
            w overlay projektu) albo ``graphql`` (GraphQL zamiast REST — patrz
            `arch:api-contract:graphql`).
    """
    return manifest.mappings.rule(CODEGEN_SLOT).normalize(raw)


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


def language_module_id(language: str, manifest: Manifest) -> str:
    """
    Zwróć ID modułu językowego dla znormalizowanego języka.

    Args:
        language: ``pl`` albo ``en`` (wynik ``normalize_language``).
        manifest: Manifest z sekcją ``mappings.languages``.

    Returns:
        str: ``core:language-en`` albo ``core:language-pl``.
    """
    return manifest.mappings.languages.module_for(language)


def normalize_auth_variant(raw: object | None, manifest: Manifest) -> str:
    """
    Znormalizuj wybór Wariantu auth do wartości znanej manifestowi.

    Args:
        raw: Wartość ``decisions.auth`` z profilu — spodziewany string (dowolny case),
            ale YAML może dać ``None``/bool/int (np. niecudzysłowione ``auth: true``).
        manifest: Manifest z sekcją ``mappings.variants.auth``.

    Returns:
        str: Jedna z wartości Wariantu; ``None``, nie-string albo nierozpoznana
            wartość → wartość domyślna z manifestu (``custom``).
    """
    value = raw if isinstance(raw, str) else None
    return manifest.mappings.rule(AUTH_SLOT).normalize(value)


def normalize_tier_value(raw: object | None, tier: str, mappings: Mappings) -> str:
    """
    Znormalizuj wybór Stacka w Tierze do wartości znanej manifestowi.

    Args:
        raw: Wartość klucza Tieru z profilu (string, ``none``, ``None``).
        tier: ``backend`` / ``web`` / ``mobile``.
        mappings: Mapowania z manifestu (sekcja ``tiers``).

    Returns:
        str: Kanoniczna nazwa Stacka (lowercase, z ewentualnym ``@wariant``),
            ``none`` dla pustego Tieru albo ``none`` dla nierozpoznanej wartości
            (zgłaszanej osobno przez ``profile_tiers`` — ADR-0004).
    """
    if not isinstance(raw, str):
        return TIER_NONE
    key = raw.strip().lower()
    if not key or key == TIER_NONE:
        return TIER_NONE
    if key in mappings.tiers.get(tier, {}):
        return key
    return TIER_NONE


def profile_tiers(
    profile_data: dict[str, Any],
    mappings: Mappings,
) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    """
    Wybór Stacka w każdym Tierze + nierozpoznane wartości (ADR-0004).

    Brak klucza Tieru = ``none`` (cicho — profil bez wyborów daje sam core).

    Args:
        profile_data: Scalone dane profilu.
        mappings: Mapowania z manifestu.

    Returns:
        tuple: ``(tiery, nierozpoznane)`` — Tier → Stack albo ``none``;
            nierozpoznane to pary ``(tier, wartość)``.
    """
    tiers: dict[str, str] = {}
    unknown: list[tuple[str, str]] = []
    for tier in TIER_ORDER:
        raw = profile_data.get(tier)
        tiers[tier] = normalize_tier_value(raw, tier, mappings)
        if isinstance(raw, str):
            key = raw.strip().lower()
            if key and key != TIER_NONE and tiers[tier] == TIER_NONE:
                unknown.append((tier, raw.strip()))
        elif raw is not None:
            unknown.append((tier, str(raw)))
    return tiers, tuple(unknown)


def normalize_module_id(module_id: str, manifest: Manifest) -> str:
    """
    Znormalizuj ID modułu (Aliasy kompatybilności — ADR-0003).

    Args:
        module_id: Surowy identyfikator z profilu / bundle.
        manifest: Manifest z sekcją ``mappings.aliases.modules``.

    Returns:
        str: Kanoniczne ID z manifestu (lub bez zmian, gdy brak Aliasu).
    """
    return manifest.mappings.canonical_module_id(module_id)


def profile_selections(profile_data: dict[str, Any], mappings: Mappings) -> dict[str, str]:
    """
    Wybrana wartość dla każdego Slotu Wariantu i Substytucji.

    Skąd czytamy, zależy od rodzaju Slotu, nie od jego nazwy — dzięki temu nowy wpis
    w manifeście działa bez dotykania Pythona (ADR-0001):

    - **Substytucja** (``codegen``) — klucz najwyższego poziomu profilu.
    - **Wariant** (``auth``) — wartość z sekcji ``decisions``.

    Args:
        profile_data: Scalone dane profilu (po nałożeniu nadpisań CLI/env).
        mappings: Mapowania z manifestu.

    Returns:
        dict[str, str]: Slot → znormalizowana wartość.
    """
    decisions: dict[str, Any] = profile_data.get("decisions") or {}
    selections = {
        slot: rule.normalize(profile_data.get(slot))
        for slot, rule in mappings.substitutions.items()
    }
    selections.update(
        {slot: rule.normalize(decisions.get(slot)) for slot, rule in mappings.variants.items()}
    )
    return selections


def apply_profile_decisions(
    module_ids: list[str],
    *,
    manifest: Manifest,
    language: str,
    selections: dict[str, str],
) -> tuple[str, ...]:
    """
    Jedyny pipeline transformacji Module ID — używany przez `enabled` i przez bundle.

    Kolejność jest własnością tej funkcji, nie jej wywołań (ADR-0002): normalizacja
    Aliasów biegnie **pierwsza**, żeby Alias celujący w moduł bazowy Wariantu
    (``capability:auth``) czy Substytucji (``arch:api-contract``) nie zgubił po cichu
    swojego wariantu.

    Args:
        module_ids: Surowa lista ID z profilu albo z konfiguracji bundle'a.
        manifest: Manifest z mapowaniami.
        language: Znormalizowany język (``pl`` / ``en``).
        selections: Slot → wybrana wartość (wynik ``profile_selections``).

    Returns:
        tuple[str, ...]: Kanoniczne ID bez duplikatów, w kolejności wejściowej.
    """
    mappings = manifest.mappings

    # 1. Aliasy → postać kanoniczna (+ dedup).
    resolved = _merge_unique([], [mappings.canonical_module_id(mid) for mid in module_ids])

    # 2. Moduły językowe scalają się do jednego, na pozycji pierwszego.
    language_target = mappings.languages.module_for(language)
    language_modules = set(mappings.languages.values.values())
    collapsed: list[str] = []
    language_placed = False
    for module_id in resolved:
        if module_id in language_modules:
            if not language_placed:
                collapsed.append(language_target)
                language_placed = True
            continue
        collapsed.append(module_id)

    # 3. Substytucje — podmiana modułu bazowego na Wariant.
    for slot, rule in mappings.substitutions.items():
        target = rule.module_for(selections.get(slot))
        collapsed = [target if mid == rule.base else mid for mid in collapsed]

    # 4. Warianty — wstawienie modułu zaraz po module bazowym.
    for slot, rule in mappings.variants.items():
        target = rule.module_for(selections.get(slot))
        expanded: list[str] = []
        for module_id in collapsed:
            expanded.append(module_id)
            if module_id == rule.base:
                expanded.append(target)
        collapsed = expanded

    return tuple(_merge_unique([], collapsed))


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
    codegen: str
    tiers: dict[str, str]
    notice: str
    kit_root: Path
    profile_path: Path
    workspace_root: Path
    enabled_module_ids: tuple[str, ...]
    bundles: dict[str, ResolvedBundle]
    overlay_content: str
    index_markdown: str
    language_module_id: str
    unrecognised_decisions: tuple[tuple[str, str], ...]
    deprecated_aliases: tuple[tuple[str, str], ...]


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


def _named_module_ids(names: list[str], mapping: dict[str, str], aliases: dict[str, str]) -> list[str]:
    """
    Zmapuj nazwy z profilu (Capability / Domain / Pattern) na Module ID.

    Args:
        names: Nazwy z profilu.
        mapping: Sekcja mapowań z manifestu.
        aliases: Aliasy nazw (ADR-0003) — stara pisownia → kanoniczna.

    Returns:
        list[str]: Module ID dla rozpoznanych nazw; nierozpoznane pomijane.
    """
    module_ids: list[str] = []
    for name in names:
        module_id = mapping.get(aliases.get(name, name))
        if module_id:
            module_ids.append(module_id)
    return module_ids


def _decision_module_ids(decisions: dict[str, Any], mappings: Mappings) -> list[str]:
    """
    Zmapuj Sloty z ``decisions`` na moduły infra.

    Slot ``auth`` leży w ``mappings.variants`` — dokleja Wariant do ``capability:auth``
    w bundle'ach backend/frontend, więc nie wnosi tu własnego modułu.

    Args:
        decisions: Sekcja ``decisions`` profilu.
        mappings: Mapowania z manifestu.

    Returns:
        list[str]: Module ID rozpoznanych Decyzji.
    """
    module_ids: list[str] = []
    for slot, value in decisions.items():
        if not isinstance(value, str):
            continue
        module_id = mappings.slots.get(slot, {}).get(value)
        if module_id:
            module_ids.append(module_id)
    return module_ids


def unrecognised_decisions(
    profile_data: dict[str, Any],
    mappings: Mappings,
) -> tuple[tuple[str, str], ...]:
    """
    Wybory, których manifest nie zna (ADR-0004: raportujemy, nie wywracamy serwera).

    Pokrywa oba źródła wyborów: sekcję ``decisions`` (Slot infra i Wariant) oraz
    klucze najwyższego poziomu sterujące Substytucjami (``codegen``).

    Args:
        profile_data: Scalone dane profilu.
        mappings: Mapowania z manifestu.

    Returns:
        tuple[tuple[str, str], ...]: Pary ``(slot, wartość)`` — nieznany Slot albo
            nieznana wartość znanego Slotu.
    """
    found: list[tuple[str, str]] = []
    decisions: dict[str, Any] = profile_data.get("decisions") or {}

    _, tier_unknown = profile_tiers(profile_data, mappings)
    found.extend(tier_unknown)

    for slot, value in decisions.items():
        name = str(slot)
        if not isinstance(value, str):
            found.append((name, str(value)))
            continue
        if name in mappings.variants:
            if not mappings.variants[name].knows(value):
                found.append((name, value))
        elif name not in mappings.slots:
            found.append((name, value))
        elif value not in mappings.slots[name]:
            found.append((name, value))

    for slot, rule in mappings.substitutions.items():
        raw = profile_data.get(slot)
        if raw is not None and not rule.knows(str(raw)):
            found.append((slot, str(raw)))

    return tuple(found)


def used_aliases(
    profile_data: dict[str, Any],
    mappings: Mappings,
) -> tuple[tuple[str, str], ...]:
    """
    Aliasy faktycznie użyte przez profil (ADR-0003 — do zgłoszenia w indeksie).

    Każdą przestrzeń nazw sprawdzamy tam, gdzie resolver ją naprawdę rozwiązuje:
    Alias Module ID w ``include`` i w ``bundles``, Alias nazwy w sekcjach
    ``capabilities`` / ``domains``. ``patterns`` nie jest aliasowane, więc się go
    nie skanuje — indeks nie może obiecać migracji, której nie było.

    Args:
        profile_data: Scalone dane profilu.
        mappings: Mapowania z manifestu.

    Returns:
        tuple[tuple[str, str], ...]: Pary ``(alias, kanoniczna nazwa)``.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _collect(candidates: list[str], aliases: dict[str, str]) -> None:
        for candidate in candidates:
            target = aliases.get(candidate)
            if target is not None and candidate not in seen:
                seen.add(candidate)
                found.append((candidate, target))

    module_candidates: list[str] = [str(mid) for mid in profile_data.get("include", [])]
    for module_ids in (profile_data.get("bundles") or {}).values():
        module_candidates.extend(str(mid) for mid in module_ids)
    _collect(module_candidates, mappings.module_aliases)

    name_candidates: list[str] = []
    for key in ("capabilities", "domains"):
        name_candidates.extend(str(name) for name in profile_data.get(key, []))
    _collect(name_candidates, mappings.name_aliases)

    return tuple(found)


def _routed_module_ids(
    rule: BundleRule,
    *,
    enabled: list[str],
    tier_ids: set[str],
    tiers: dict[str, str],
    language: str,
    manifest: Manifest,
) -> list[str]:
    """
    Moduły bundle'a z pełnej listy ``enabled`` (kolejność zachowana).

    Skład: stały core, moduły Tierów przypisanych do bundle'a, reszta
    wg przecięcia tagów modułu z selektorem (minus ``exclude_tags``).
    ``tags: ["*"]`` bierze wszystko.
    """
    mappings = manifest.mappings
    wanted: set[str] = set()
    for tier in TIER_ORDER:
        if tier in rule.tiers:
            wanted.update(
                mappings.canonical_module_id(mid)
                for mid in mappings.tiers.get(tier, {}).get(tiers.get(tier, TIER_NONE), [])
            )

    selected: list[str] = []
    for module_id in enabled:
        info = manifest.modules.get(module_id)
        if info is None:
            continue
        if module_id == VPS_LIGHTWEIGHT_MODULE:
            selected.append(module_id)
            continue
        if module_id in wanted:
            selected.append(module_id)
            continue
        if module_id in tier_ids:
            continue
        if "*" in rule.tags:
            selected.append(module_id)
            continue
        tags = set(info.tags)
        if not tags & set(rule.tags):
            continue
        if tags & set(rule.exclude_tags):
            continue
        selected.append(module_id)

    lang_module = mappings.languages.module_for(language)
    core_ids = [
        mid
        for mid in ("core:repo-first", lang_module, "core:external-knowledge", "core:tooling-rtk")
        if mid in manifest.modules
    ]
    return _merge_unique(core_ids, selected)


def _filled_tiers(
    tiers: dict[str, str],
    profile_data: dict[str, Any],
    mappings: Mappings,
) -> set[str]:
    """
    Tiery z wybranym Stackiem — także te wypełnione przez legacy ``stacks:``.

    Legacy Stack liczy się do Tieru, którego moduły zawiera w ``mappings.tiers``
    (np. ``django-drf`` → backend, ``expo-router`` → web i mobile).
    """
    filled = {tier for tier in TIER_ORDER if tiers.get(tier, TIER_NONE) != TIER_NONE}
    stacks: dict[str, Any] = profile_data.get("stacks", {}) or {}
    for stack_name, stack_modules in mappings.stacks.items():
        if not stacks.get(stack_name):
            continue
        for tier in TIER_ORDER:
            tier_modules = {
                mid for mids in mappings.tiers.get(tier, {}).values() for mid in mids
            }
            if tier_modules & set(stack_modules):
                filled.add(tier)
    return filled


def _collect_module_ids(
    profile_data: dict[str, Any],
    manifest: Manifest,
    *,
    language: str,
    selections: dict[str, str],
    tiers: dict[str, str],
    host_profile: str | None = None,
) -> tuple[list[str], set[str]]:
    """
    Zbierz listę modułów włączonych przez profil.

    Tiery rozwijają się z ``mappings.tiers``; stare klucze ``stacks:`` /
    ``patterns:`` oraz ``bundles:`` z profilu czytane są nadal (legacy).

    Args:
        profile_data: Scalone dane profilu.
        manifest: Manifest z rejestrem i mapowaniami.
        language: Znormalizowany język.
        selections: Slot → wybrana wartość (wynik ``profile_selections``).
        tiers: Tier → Stack albo ``none`` (wynik ``profile_tiers``).
        host_profile: ``vps`` / ``local`` albo ``None`` (= wykryj heurystyką
            + ``KIT_HOST_PROFILE``). VPS dokleja ``infra:vps-lightweight``.

    Returns:
        tuple: ``(moduły, moduły_z_tierów)`` — kanoniczne ID istniejących
            w rejestrze modułów oraz podzbiór wniesiony przez Tiery
            (do przypisania bundle'i).
    """
    mappings = manifest.mappings
    module_ids: list[str] = list(profile_data.get("include", []))

    # Legacy: profilowe `bundles:` traktuj jak `include` (routing wg tagów).
    for bundle_ids in (profile_data.get("bundles") or {}).values():
        module_ids.extend(bundle_ids)

    tier_ids: set[str] = set()
    for tier in TIER_ORDER:
        for module_id in mappings.tiers.get(tier, {}).get(tiers.get(tier, TIER_NONE), []):
            module_ids.append(module_id)
            tier_ids.add(mappings.canonical_module_id(module_id))

    stacks: dict[str, Any] = profile_data.get("stacks", {}) or {}
    for stack_name, stack_modules in mappings.stacks.items():
        if stacks.get(stack_name):
            module_ids.extend(stack_modules)

    module_ids.extend(
        _named_module_ids(
            list(profile_data.get("capabilities", [])),
            mappings.capabilities,
            mappings.name_aliases,
        )
    )
    module_ids.extend(
        _named_module_ids(
            list(profile_data.get("domains", [])), mappings.domains, mappings.name_aliases
        )
    )
    for pattern in profile_data.get("patterns", []):
        module_ids.append(mappings.patterns.get(pattern, pattern))

    module_ids.extend(_decision_module_ids(profile_data.get("decisions", {}), mappings))

    # Warunki na stałych osiach Tierów (backend/web/mobile — zbiór zamknięty
    # z CONTEXT, nie otwarte technologie; te żyją w mappings.tiers — ADR-0001).
    filled = _filled_tiers(tiers, profile_data, mappings)
    has_backend = "backend" in filled
    has_client = "web" in filled or "mobile" in filled
    if has_backend:
        module_ids.append("core:typing-python")
    if has_client:
        module_ids.append("core:typing-typescript")
    if has_backend and has_client:
        module_ids.append(API_CONTRACT_BASE)

    has_expo = (
        tiers.get("web") == "expo"
        or tiers.get("mobile") == "expo"
        or bool(stacks.get("expo-router"))
    )
    capabilities = {mappings.canonical_name(str(name)) for name in profile_data.get("capabilities", [])}
    payments_on = "payments" in capabilities or "capability:payments" in module_ids
    if has_expo and payments_on and EXPO_STRIPE_MODULE in manifest.modules:
        module_ids.append(EXPO_STRIPE_MODULE)
    if not has_expo:
        module_ids = [mid for mid in module_ids if mid != EXPO_STRIPE_MODULE]

    # Domyślnie core jeśli profil nie wyłącza
    if profile_data.get("core", True):
        module_ids = _merge_unique(
            [
                "core:repo-first",
                mappings.languages.module_for(language),
                "core:external-knowledge",
                "core:tooling-rtk",
            ],
            module_ids,
        )

    if host_profile is None:
        host_profile = detect_host_profile()
    if host_profile == "vps" and VPS_LIGHTWEIGHT_MODULE in manifest.modules:
        module_ids.append(VPS_LIGHTWEIGHT_MODULE)

    resolved = apply_profile_decisions(
        module_ids,
        manifest=manifest,
        language=language,
        selections=selections,
    )

    # Walidacja — tylko znane moduły
    return [mid for mid in resolved if mid in manifest.modules], tier_ids


def _build_bundle_content(
    bundle_name: str,
    module_ids: list[str],
    manifest: Manifest,
    *,
    notice: str = "",
) -> ResolvedBundle:
    """
    Złóż treść Markdown bundle'a z plików modułów.

    Precondition: ``module_ids`` przeszły już przez ``apply_profile_decisions`` —
    są kanoniczne i odduplikowane. Ta funkcja nie normalizuje ponownie, żeby
    kolejność transformacji miała dokładnie jedno miejsce (ADR-0002).
    """
    parts: list[str] = []
    missing: list[str] = []
    canonical_ids = list(module_ids)

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
    if notice:
        content = f"{notice}\n\n{content}"

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


PROFILE_REL_PATH = Path(".ai/project.profile.yaml")


def resolve_workspace_profile(
    workspace_root: Path,
    kit_root: Path | None = None,
    *,
    extra_overlays: list[Path] | None = None,
    language_override: str | None = None,
    notice: str = "",
    host_profile: str | None = None,
) -> ResolvedProfile:
    """
    Rozwiąż profil workspace'u (``.ai/project.profile.yaml``).

    Brak pliku to nie błąd (ADR-0004): serwer startuje na samym corze,
    a Bundle i indeks niosą ostrzeżenie o migracji przez ``kit-ai reload``.

    Args:
        workspace_root: Root repo aplikacji.
        kit_root: Opcjonalny root instruction-kit.
        extra_overlays: Dodatkowe pliki overlay z CLI.
        language_override: Nadpisanie języka z CLI/env.
        host_profile: ``vps`` / ``local`` albo ``None`` (= wykryj heurystyką).

    Returns:
        ResolvedProfile: Gotowe bundle'e i metadane profilu.
    """
    resolved_workspace = workspace_root.resolve()
    profile_path = resolved_workspace / PROFILE_REL_PATH
    if not profile_path.is_file() and MIGRATION_NOTICE not in notice:
        notice = f"{notice}\n\n{MIGRATION_NOTICE}" if notice else MIGRATION_NOTICE
    return resolve_profile(
        profile_path,
        kit_root,
        workspace_root=resolved_workspace,
        extra_overlays=extra_overlays,
        language_override=language_override,
        notice=notice,
        host_profile=host_profile,
    )


def resolve_profile(
    profile_path: Path,
    kit_root: Path | None = None,
    *,
    workspace_root: Path | None = None,
    extra_overlays: list[Path] | None = None,
    language_override: str | None = None,
    notice: str = "",
    host_profile: str | None = None,
) -> ResolvedProfile:
    """
    Rozwiąż profil projektu do bundle'i i indeksu.

    Args:
        profile_path: Ścieżka do profilu (``.ai/project.profile.yaml``).
            Nieistniejący plik = pusty profil (sam core).
        kit_root: Opcjonalny root instruction-kit.
        workspace_root: Root repo aplikacji (overlay). Gdy brak — ``profile_path.parent.parent``
            dla lokalnego ``.ai/…``, inaczej ``cwd``.
        extra_overlays: Dodatkowe pliki overlay z CLI.
        language_override: Nadpisanie języka z CLI/env (``pl`` / ``en``); ma pierwszeństwo
            przed ``language`` w YAML profilu. Codegen nie ma nadpisania — tylko
            ``codegen:`` w profilu (ADR-0007); bez pary backend + klient (web/mobile)
            efektywny codegen to zawsze ``none``.
        notice: Ostrzeżenie doklejane na początek bundle'i i indeksu
            (np. migracja starej konfiguracji).
        host_profile: ``vps`` / ``local`` albo ``None`` (= wykryj heurystyką
            + ``KIT_HOST_PROFILE``). VPS dokleja ``infra:vps-lightweight``
            do każdego bundle'a.

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
        resolved_workspace = Path.cwd().resolve()

    raw_profile = _read_yaml(profile_path)
    # Stary profil z `extends: profiles/_base.yaml` (usunięte presety) — bez
    # ostrzeżenia straciłby Stacki po cichu (ADR-0004).
    extends = raw_profile.get("extends")
    if extends and MIGRATION_NOTICE not in notice:
        extends_path = Path(extends)
        if not extends_path.is_absolute():
            extends_path = manifest.kit_root / extends_path
        if not extends_path.is_file():
            notice = f"{notice}\n\n{MIGRATION_NOTICE}" if notice else MIGRATION_NOTICE
    profile_data = _resolve_extends(raw_profile, manifest.kit_root)

    language = normalize_language(
        language_override
        if language_override is not None
        else str(profile_data.get("language", "pl"))
    )
    tiers, _ = profile_tiers(profile_data, manifest.mappings)
    filled = _filled_tiers(tiers, profile_data, manifest.mappings)
    if "backend" in filled and ("web" in filled or "mobile" in filled):
        codegen = normalize_codegen(str(profile_data.get("codegen", "orval")), manifest)
    else:
        codegen = "none"
    profile_data = {**profile_data, "language": language, "codegen": codegen}
    selections = profile_selections(profile_data, manifest.mappings)

    def _pipeline(module_ids: list[str]) -> tuple[str, ...]:
        """Jeden seam transformacji — ta sama kolejność dla `enabled` i dla bundle'i."""
        return apply_profile_decisions(
            module_ids,
            manifest=manifest,
            language=language,
            selections=selections,
        )

    enabled_modules, tier_ids = _collect_module_ids(
        profile_data,
        manifest,
        language=language,
        selections=selections,
        tiers=tiers,
        host_profile=host_profile,
    )
    resolved_host = host_profile if host_profile in ("vps", "local") else detect_host_profile()

    bundles: dict[str, ResolvedBundle] = {}
    for bundle_name, rule in manifest.bundles.items():
        routed = _routed_module_ids(
            rule,
            enabled=enabled_modules,
            tier_ids=tier_ids,
            tiers=tiers,
            language=language,
            manifest=manifest,
        )
        bundles[bundle_name] = _build_bundle_content(
            bundle_name, list(_pipeline(routed)), manifest, notice=notice
        )

    overlay_content = _load_overlays(profile_data, resolved_workspace, extra_overlays)
    unknown_decisions = unrecognised_decisions(profile_data, manifest.mappings)
    deprecated_aliases = used_aliases(profile_data, manifest.mappings)
    lang_module = manifest.mappings.languages.module_for(language)

    index_lines = []
    if notice:
        index_lines.extend([notice, ""])
    index_lines.extend(
        [
            f"# Instruction index: {profile_data.get('name', resolved_workspace.name)}",
            "",
            f"- Język: {language}",
            f"- Moduł języka: `{lang_module}`",
            f"- Codegen: {codegen}",
            f"- Tiery: backend=`{tiers['backend']}` web=`{tiers['web']}` mobile=`{tiers['mobile']}`",
            f"- Host: `{resolved_host}`",
            f"- Profil: `{profile_path}`",
            f"- Workspace: `{resolved_workspace}`",
            f"- Kit root: `{manifest.kit_root}`",
            "",
            "## Włączone moduły",
            "",
        ]
    )
    for module_id in enabled_modules:
        info = manifest.modules[module_id]
        index_lines.append(f"- `{module_id}` — {info.title}")

    index_lines.extend(["", "## Bundle'e", ""])
    for name, bundle in bundles.items():
        missing_note = f" (brak: {', '.join(bundle.missing_modules)})" if bundle.missing_modules else ""
        index_lines.append(f"- `{name}` — {len(bundle.module_ids)} modułów{missing_note}")

    if unknown_decisions:
        index_lines.extend(["", "## Nierozpoznane decyzje", ""])
        index_lines.extend(
            f"- `{slot}: {value}` — manifest nie zna tej wartości; moduł nie został włączony"
            for slot, value in unknown_decisions
        )

    if deprecated_aliases:
        index_lines.extend(["", "## Aliasy do migracji", ""])
        index_lines.extend(
            f"- `{alias}` → `{target}` — stara pisownia, działa nadal; zaktualizuj profil"
            for alias, target in deprecated_aliases
        )

    if overlay_content:
        index_lines.extend(["", "## Overlay", "", "Projekt ma lokalny overlay — użyj `guides://overlay`."])

    return ResolvedProfile(
        name=str(profile_data.get("name", resolved_workspace.name)),
        language=language,
        codegen=codegen,
        tiers=tiers,
        notice=notice,
        kit_root=manifest.kit_root,
        profile_path=profile_path,
        workspace_root=resolved_workspace,
        enabled_module_ids=tuple(enabled_modules),
        bundles=bundles,
        overlay_content=overlay_content,
        index_markdown="\n".join(index_lines),
        language_module_id=lang_module,
        unrecognised_decisions=unknown_decisions,
        deprecated_aliases=deprecated_aliases,
    )
