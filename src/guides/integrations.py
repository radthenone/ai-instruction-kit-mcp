"""
Parsowanie, walidacja i renderowanie zewnętrznych integracji (#459).

Obsługuje listę `integrations:` w Profilu (`.ai/project.profile.yaml`).
Na start:
  - `orca` → `orca.yaml`
  - `coderabbit` → `.coderabbit.yaml`
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple


@dataclass(frozen=True)
class IntegrationDef:
    """Definicja zewnętrznej integracji."""

    name: str
    target_file: str
    template_name: str


INTEGRATIONS_MAP: dict[str, IntegrationDef] = {
    "orca": IntegrationDef(
        name="orca",
        target_file="orca.yaml",
        template_name="orca.yaml",
    ),
    "coderabbit": IntegrationDef(
        name="coderabbit",
        target_file=".coderabbit.yaml",
        template_name=".coderabbit.yaml",
    ),
}

KNOWN_INTEGRATIONS: tuple[str, ...] = tuple(INTEGRATIONS_MAP.keys())


def integration_target_file(name: str) -> str | None:
    """Zwróć ścieżkę pliku docelowego integracji w workspace konsumenta."""
    item = INTEGRATIONS_MAP.get(name.strip().lower())
    return item.target_file if item else None


def integration_template(name: str) -> str | None:
    """Zwróć nazwę szablonu integracji w repo kita."""
    item = INTEGRATIONS_MAP.get(name.strip().lower())
    return item.template_name if item else None


def coderabbit_language(language: str | None) -> str:
    """
    Mapuj język profilu na kod języka CodeRabbit (np. pl -> pl-PL, en -> en-US).

    Args:
        language: Kod języka z profilu (np. ``pl``, ``en``).

    Returns:
        str: Kod języka w formacie CodeRabbit (``pl-PL`` albo ``en-US``).
    """
    raw = (language or "pl").strip().lower().replace("_", "-")
    primary = raw.split("-", 1)[0]
    if raw in {"en", "eng", "english"} or primary in {"en", "eng"}:
        return "en-US"
    return "pl-PL"


class ParsedIntegrations(NamedTuple):
    """Wynik parsowania sekcji ``integrations:``."""

    integrations: list[str]
    warnings: list[str]

    @property
    def names(self) -> list[str]:
        """Alias dla pola integrations."""
        return self.integrations


def parse_integrations(raw: object) -> ParsedIntegrations:
    """
    Parsuj i waliduj wartość ``integrations:`` z Profilu.

    Nieznane nazwy są pomijane z ostrzeżeniem w stylu ``worktree.*`` (#459).

    Args:
        raw: Lista YAML, string po przecinku, pojedyncza nazwa lub None.

    Returns:
        ParsedIntegrations: (znane_nazwy, ostrzeżenia).
    """
    if raw is None:
        return ParsedIntegrations([], [])

    tokens: list[str] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            tokens.append(str(item))
    elif isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return ParsedIntegrations([], [])
        tokens = [p for p in cleaned.split(",")]
    else:
        tokens = [str(raw)]

    seen: set[str] = set()
    ordered: list[str] = []
    warnings: list[str] = []

    for token in tokens:
        name = token.strip().lower()
        if not name:
            continue
        if name in KNOWN_INTEGRATIONS:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        else:
            warnings.append(f"nieznana integracja `{token.strip()}` — pominięto")

    return ParsedIntegrations(ordered, warnings)


def _read_profile_integrations(profile_path: Path) -> tuple[list[str], str]:
    """Wczytaj integrations i language z pliku profilu YAML bez twardej zależności od PyYAML."""
    if not profile_path.is_file():
        return [], "pl"
    text = profile_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            raw_int = data.get("integrations")
            lang = str(data.get("language") or "pl")
            parsed = parse_integrations(raw_int)
            return parsed.integrations, lang
    except Exception:
        pass

    # Awaryjny parser linijkowy
    integrations: list[str] = []
    language = "pl"
    in_integrations = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("language:"):
            _, _, val = line.partition(":")
            language = val.strip().strip("'\"")
            continue
        if line.startswith("integrations:"):
            _, _, val = line.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                items = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
                return parse_integrations(items).integrations, language
            in_integrations = True
            continue
        if in_integrations:
            if line.startswith(" ") or line.startswith("\t"):
                if stripped.startswith("-"):
                    item = stripped[1:].strip().strip("'\"")
                    integrations.append(item)
            else:
                break
    return parse_integrations(integrations).integrations, language


def render_integrations(
    workspace_root: Path,
    kit_root: Path,
    profile_data: dict[str, Any] | Path | None = None,
    *,
    integrations: list[str] | None = None,
    remove: bool = False,
    language: str | None = None,
) -> list[str]:
    """
    Renderuj lub usuń pliki integracji w repozytorium konsumenta.

    Args:
        workspace_root: Root repo konsumenta.
        kit_root: Root instruction-kit (źródło szablonów).
        profile_data: Opcjonalny słownik profilu lub ścieżka do profilu.
        integrations: Bezpośrednia lista integracji (nadpisuje profile_data).
        remove: Gdy True, usuwa pliki własne integracji.
        language: Kod języka z profilu (np. pl, en).

    Returns:
        list[str]: Względne ścieżki utworzonych lub usuniętych plików.
    """
    workspace_root = workspace_root.resolve()
    kit_root = kit_root.resolve()

    if remove:
        removed: list[str] = []
        for info in INTEGRATIONS_MAP.values():
            target = workspace_root / info.target_file
            if target.is_file():
                target.unlink()
                removed.append(info.target_file)
        return removed

    selected_integrations: list[str] = []
    resolved_lang = language or "pl"

    if integrations is not None:
        selected_integrations = parse_integrations(integrations).integrations
    elif isinstance(profile_data, dict):
        selected_integrations = parse_integrations(profile_data.get("integrations")).integrations
        if not language:
            resolved_lang = str(profile_data.get("language") or "pl")
    elif isinstance(profile_data, Path):
        selected_integrations, file_lang = _read_profile_integrations(profile_data)
        if not language:
            resolved_lang = file_lang
    else:
        profile_path = workspace_root / ".ai" / "project.profile.yaml"
        if profile_path.is_file():
            selected_integrations, file_lang = _read_profile_integrations(profile_path)
            if not language:
                resolved_lang = file_lang

    created: list[str] = []
    if not selected_integrations:
        return created

    for name in selected_integrations:
        info = INTEGRATIONS_MAP.get(name)
        if not info:
            continue
        template_candidates = [
            kit_root / "templates" / info.template_name,
            kit_root / "templates" / "shared" / info.template_name,
            kit_root / info.template_name,
        ]
        template_path = next((p for p in template_candidates if p.is_file()), None)
        if template_path is None:
            continue

        content = template_path.read_text(encoding="utf-8")
        if name == "coderabbit":
            lang_code = coderabbit_language(resolved_lang)
            content = content.replace("{{language}}", lang_code)
            content = content.replace('language: "pl-PL"', f'language: "{lang_code}"')

        target = workspace_root / info.target_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(info.target_file)

    return created


def main(argv: list[str] | None = None, kit_root: Path | None = None) -> int:
    """CLI dla skryptów render_integrations.py."""
    raw_args = sys.argv if argv is None else argv
    args = list(raw_args[1:])
    remove = False
    if "--remove" in args:
        remove = True
        args.remove("--remove")

    if not args:
        print("Użycie: render_integrations.py [--remove] <workspace> [profile_path] [kit_root]", file=sys.stderr)
        return 1

    workspace = Path(args[0]).resolve()
    profile_path = Path(args[1]).resolve() if len(args) > 1 else workspace / ".ai" / "project.profile.yaml"
    resolved_kit_root = (
        Path(args[2]).resolve()
        if len(args) > 2
        else (kit_root or Path(__file__).resolve().parents[2])
    )

    result = render_integrations(
        workspace_root=workspace,
        kit_root=resolved_kit_root,
        profile_data=profile_path,
        remove=remove,
    )
    for path in result:
        print(f"  {' -' if remove else ' +'} {path}")
    return 0
