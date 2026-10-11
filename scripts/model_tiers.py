#!/usr/bin/env python3
"""
Model tiers agentów kita: `model-tier:` w template, `models:` i `agents:` w Profilu.

Użycie:
    model_tiers.py sync PROFILE AGENTS_DIR
    model_tiers.py apply CLIENT PROFILE DEST_DIR

`sync` waliduje Profil i dopasowuje blok `agents:` do agentów kita (przepisuje tylko
ten blok, raport na stdout). `apply` dopisuje `model:` do frontmattera plików
`DEST_DIR/<agent>.md`, gdy Profil mapuje tier agenta na model klienta.

Bez PyYAML — bootstrap leci na systemowym Pythonie, a oba bloki to płaskie mapy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TIERS = ("light", "standard", "heavy")
_ALLOWED = ", ".join(TIERS)


class ProfileError(ValueError):
    """Profil ma niepoprawne `models:` albo `agents:`."""


def template_tiers(agents_dir: Path) -> dict[str, str]:
    """Agent → `model-tier:` z frontmattera template."""
    tiers: dict[str, str] = {}
    for src in sorted(agents_dir.glob("*.md")):
        lines = src.read_text(encoding="utf-8").splitlines()
        end = lines.index("---", 1)
        for line in lines[1:end]:
            if line.startswith("model-tier:"):
                tiers[src.stem] = line.partition(":")[2].strip()
    return tiers


def _block_range(lines: list[str], key: str) -> tuple[int, int] | None:
    """Zakres linii bloku `key:` najwyższego poziomu, bez pustych linii na końcu."""
    start = next((i for i, line in enumerate(lines) if re.match(rf"{key}:\s*(#.*)?$", line)), None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t"):
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return start, end


def _entries(lines: list[str]) -> list[tuple[int, str, str]]:
    """(wcięcie, klucz, wartość) z linii bloku; komentarze wycięte."""
    found = []
    for line in lines:
        line = re.sub(r"(^|\s)#.*$", "", line.rstrip("\n"))
        if not line.strip():
            continue
        key, _, value = line.strip().partition(":")
        found.append((len(line) - len(line.lstrip()), key.strip(), value.strip().strip("'\"")))
    return found


def parse_profile(text: str) -> tuple[dict[str, dict[str, str]], dict[str, list[str]] | None]:
    """
    `models:` i `agents:` z Profilu, zwalidowane.

    Returns:
        tuple: ``(models[client][tier] = model, agents[tier] = [nazwy] albo None bez bloku)``.

    Raises:
        ProfileError: Nieznany tier albo agent w dwóch tierach.
    """
    lines = text.splitlines(keepends=True)
    models: dict[str, dict[str, str]] = {}
    span = _block_range(lines, "models")
    if span:
        client, client_name = None, ""
        for indent, key, value in _entries(lines[span[0] + 1 : span[1]]):
            if not value:
                client = models.setdefault(key, {})
                client_name = key
                continue
            if client is None:
                raise ProfileError(f"Profil: `models.{key}` bez klienta. Wzór: models.claude.light: haiku")
            if key not in TIERS:
                raise ProfileError(
                    f"Profil: nieznany tier `models.{client_name}.{key}`. Dozwolone: {_ALLOWED}."
                )
            client[key] = value

    span = _block_range(lines, "agents")
    if span is None:
        return models, None
    agents: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for _, tier, value in _entries(lines[span[0] + 1 : span[1]]):
        if tier not in TIERS:
            raise ProfileError(
                f"Profil: nieznany tier `agents.{tier}`. Dozwolone: {_ALLOWED} — "
                "przenieś jego agentów do jednego z nich."
            )
        names = [n.strip().strip("'\"") for n in value.strip("[]").split(",") if n.strip()]
        for name in names:
            if name in seen:
                raise ProfileError(
                    f"Profil: agent `{name}` jest w dwóch tierach (`agents.{seen[name]}` "
                    f"i `agents.{tier}`). Zostaw go w jednym."
                )
            seen[name] = tier
        agents[tier] = names
    return models, agents


def sync_agents(text: str, template: dict[str, str]) -> tuple[str, list[str]]:
    """
    Dopasuj blok `agents:` do agentów kita. Profil wygrywa nad template.

    Returns:
        tuple: ``(nowy tekst Profilu, raport zmian)``; bez zmian — tekst bez dotykania.
    """
    _, agents = parse_profile(text)
    report: list[str] = []
    synced: dict[str, list[str]] = {tier: [] for tier in TIERS}
    for tier, names in (agents or {}).items():
        for name in names:
            if name in template:
                synced[tier].append(name)
            else:
                report.append(f"- agents.{tier}: {name} (nie ma takiego agenta w kicie)")
    assigned = {name for names in synced.values() for name in names}
    for name in sorted(template):
        if name not in assigned:
            synced[template[name]].append(name)
            report.append(f"+ agents.{template[name]}: {name}")
    if agents is not None and not report:
        return text, []

    block = ["agents:\n"] + [f"  {tier}: {','.join(names)}\n" for tier, names in synced.items() if names]
    lines = text.splitlines(keepends=True)
    span = _block_range(lines, "agents")
    if span:
        lines[span[0] : span[1]] = block
        return "".join(lines), report
    if text and not text.endswith("\n"):
        text += "\n"
    return text + ("\n" if text.strip() else "") + "".join(block), report


def apply_models(client: str, profile_text: str, dest_dir: Path) -> None:
    """Dopisz `model:` agentom, których tier klient mapuje w `models:`."""
    models, agents = parse_profile(profile_text)
    mapping = models.get(client, {})
    for tier, names in (agents or {}).items():
        model = mapping.get(tier)
        if not model:
            continue
        for name in names:
            path = dest_dir / f"{name}.md"
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            lines.insert(end, f"model: {model}\n")
            path.write_text("".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 4 and argv[1] == "sync":
            profile, agents_dir = Path(argv[2]), Path(argv[3])
            text = profile.read_text(encoding="utf-8") if profile.is_file() else ""
            synced, report = sync_agents(text, template_tiers(agents_dir))
            if synced != text:
                profile.write_text(synced, encoding="utf-8", newline="\n")
            for line in report:
                print(f"  {line}")
            return 0
        if len(argv) == 5 and argv[1] == "apply":
            profile = Path(argv[3])
            text = profile.read_text(encoding="utf-8") if profile.is_file() else ""
            apply_models(argv[2], text, Path(argv[4]))
            return 0
    except ProfileError as exc:
        print(f"{exc} (plik: .ai/project.profile.yaml)", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
