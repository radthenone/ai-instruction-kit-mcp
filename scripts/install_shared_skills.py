#!/usr/bin/env python3
"""
Zainstaluj templates/shared/skills/*/SKILL.md do katalogu klienta.

Użycie:
    install_shared_skills.py CLIENT SRC_DIR DEST_DIR

Cztery klienty czytają skille natywnie (`<nazwa>/SKILL.md` w katalogu skilli) —
dla nich instalacja to kopia całego katalogu razem z `scripts/`, `references/`
i `assets/`. Reszta nie ma formatu skilla, więc skill degraduje się do komendy
`/nazwa` w formacie danego klienta: nadal jest dostępny, ale trzeba go wywołać
ręcznie zamiast liczyć na to, że model sam go załaduje z `description`.

Zasoby obok SKILL.md przy degradacji przepadają — komenda to jeden plik. Skrypt
mówi o tym głośno, bo skill, który w połowie klientów gubi swoje `scripts/`,
jest gorszy niż skill, którego tam po prostu nie ma.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from render_agent_commands import DEST_SUFFIX, RENDERERS

# Klienci z natywnym katalogiem skilli. Dokąd dokładnie trafiają, decyduje
# bootstrap — tutaj liczy się tylko to, że dostają katalog, a nie jeden plik.
NATIVE_CLIENTS = {"claude", "cursor", "antigravity", "codex"}

# Klient bez natywnych skilli → format renderera z render_agent_commands.
# `kiro` czyta surowe pliki agentów, więc nie ma dla niego renderera — kopiujemy
# SKILL.md bez zmian, tak samo jak robi to copy_shared_agents().
DEGRADED_CLIENTS = {
    "vscode": "vscode",
    "kilo": "kilo",
    "opencode": "opencode",
    "kiro": None,
}

# Katalogi, które skill może mieć obok SKILL.md (kolejność jak w dokumentacji).
BUNDLED_DIRS = ("scripts", "references", "assets")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Frontmatter skilla → (pola, treść).

    Własny parser zamiast tego z render_agent_commands, bo skille używają
    składanych bloków YAML (`description: >-` i wcięte linie pod spodem) —
    parser liniowy `key: value` zwróciłby dla nich dosłowne ">-".
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("brak frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("niedomknięty frontmatter")

    meta: dict[str, str] = {}
    key: str | None = None
    folded: list[str] = []
    for line in lines[1:end]:
        stripped = line.strip()
        if key is not None and (line.startswith((" ", "\t")) or not stripped):
            if stripped:
                folded.append(stripped)
            continue
        if key is not None:
            meta[key] = " ".join(folded).strip()
            key, folded = None, []
        if ":" not in line:
            continue
        name, _, val = line.partition(":")
        name, val = name.strip(), val.strip()
        if val in (">", ">-", "|", "|-"):
            key, folded = name, []
        else:
            meta[name] = val
    if key is not None:
        meta[key] = " ".join(folded).strip()

    body = "".join(lines[end + 1 :])
    while body.startswith("\n"):
        body = body[1:]
    return meta, body


def iter_skills(src_dir: Path) -> list[Path]:
    """Katalogi skilli w źródle — po jednym SKILL.md, w kolejności alfabetycznej."""
    return sorted(p.parent for p in src_dir.glob("*/SKILL.md"))


def install_native(skill_dir: Path, dest_dir: Path) -> None:
    dest = dest_dir / skill_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)


def install_degraded(skill_dir: Path, dest_dir: Path, fmt: str | None) -> None:
    src = skill_dir / "SKILL.md"
    text = src.read_text(encoding="utf-8")
    dropped = [name for name in BUNDLED_DIRS if (skill_dir / name).is_dir()]
    if dropped:
        print(
            f"UWAGA: skill {skill_dir.name} traci {', '.join(dropped)} — "
            f"{fmt or 'kiro'} instaluje skille jako komendę, czyli jeden plik",
            file=sys.stderr,
        )

    if fmt is None:
        # kiro: surowa kopia, nazwa pliku od skilla (SKILL.md wszędzie ta sama).
        (dest_dir / f"{skill_dir.name}.md").write_text(text, encoding="utf-8")
        return

    meta, body = parse_frontmatter(text)
    # `name` z frontmatter bywa inne niż katalog; komendę nazywa katalog, bo to on
    # jest jedyną nazwą widoczną we wszystkich klientach naraz.
    meta = {**meta, "name": skill_dir.name}
    out = RENDERERS[fmt](meta, body)
    suffix = DEST_SUFFIX.get(fmt, ".md")
    (dest_dir / f"{skill_dir.name}{suffix}").write_text(out, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 1
    client, src_dir, dest_dir = argv[1], Path(argv[2]), Path(argv[3])

    if client not in NATIVE_CLIENTS and client not in DEGRADED_CLIENTS:
        print(f"Nieznany klient: {client}", file=sys.stderr)
        return 1

    skills = iter_skills(src_dir)
    if not skills:
        # Puste źródło to stan poprawny (kit bez skilli) — nie zakładamy katalogu
        # w projekcie użytkownika tylko po to, żeby został pusty.
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    for skill_dir in skills:
        if client in NATIVE_CLIENTS:
            install_native(skill_dir, dest_dir)
        else:
            install_degraded(skill_dir, dest_dir, DEGRADED_CLIENTS[client])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
