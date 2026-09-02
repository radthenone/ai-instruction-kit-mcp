#!/usr/bin/env python3
"""
Renderuj templates/shared/agents/*.md do natywnego formatu slash-command klienta.

Użycie:
    render_agent_commands.py FORMAT SRC_DIR DEST_DIR [CURATED_DIR]

FORMAT: vscode | kilo | antigravity | opencode | codex

CURATED_DIR (tylko codex): katalog z ręcznie napisanymi *.toml — jeśli agent tam
istnieje, auto-render go pomija (curated ma pierwszeństwo nad wygenerowanym).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines(keepends=True)
    assert lines[0].strip() == "---", "brak frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    body = "".join(lines[end + 1 :])
    while body.startswith("\n"):
        body = body[1:]
    return meta, body


def render_vscode(meta: dict[str, str], body: str) -> str:
    # GitHub Copilot prompt file: .github/prompts/<name>.prompt.md, wywołanie /<name>.
    description = meta.get("description", "").replace('"', "'")
    front = f'---\nmode: "agent"\ndescription: "{description}"\n---\n\n'
    return front + body


def render_kilo(meta: dict[str, str], body: str) -> str:
    # Kilo Code workflow: .kilocode/workflows/<name>.md, wywołanie /<name>, $ARGUMENTS wspierane.
    title = meta.get("name", "")
    description = meta.get("description", "")
    header = f"# {title}\n\n{description}\n\n"
    header += "Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS\n\n"
    return header + body


# Antigravity tnie pliki workflow powyżej 12000 znaków.
ANTIGRAVITY_LIMIT = 12000
ANTIGRAVITY_TRUNCATED = "\n\n(...przycięto, limit 12000 znaków...)\n"


def render_antigravity(meta: dict[str, str], body: str) -> str:
    # Antigravity workflow: .agents/workflows/<name>.md, wywołanie /<name>. Limit 12000 znaków/plik.
    title = meta.get("name", "")
    description = meta.get("description", "")
    header = f"# {title}\n\n{description}\n\n"
    out = header + body
    if len(out) > ANTIGRAVITY_LIMIT:
        # Sufiks też liczy się do limitu — bez odjęcia go wynik wychodził
        # ponad 12000 i przycięcie nie robiło tego, co obiecuje.
        keep = ANTIGRAVITY_LIMIT - len(ANTIGRAVITY_TRUNCATED)
        # Przycięcie leci od końca pliku, a tam agenci trzymają sekcję "Zakazy" —
        # ciche obcięcie zabiera akurat zakazy. Głośny komunikat, bo inaczej
        # okrojony agent instaluje się bez śladu.
        print(
            f"UWAGA: {title} ma {len(out)} znaków (limit antigravity "
            f"{ANTIGRAVITY_LIMIT}) — przycięto {len(out) - keep} znaków z końca pliku",
            file=sys.stderr,
        )
        out = out[:keep] + ANTIGRAVITY_TRUNCATED
    return out


def render_opencode(meta: dict[str, str], body: str) -> str:
    # opencode custom command: .opencode/command/<name>.md, wywołanie /<name>, $ARGUMENTS wspierane.
    description = meta.get("description", "").replace('"', "'")
    front = f'---\ndescription: "{description}"\n---\n\n'
    front += "Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS\n\n"
    return front + body


def _toml_literal(text: str) -> str:
    # TOML multi-line literal string ('''...'''): brak przetwarzania escape'ów,
    # bezpieczne dla backslashy w regexach (np. \s*= w regułach sekretów).
    # Jedyne ograniczenie: treść nie może zawierać sekwencji "'''".
    return text.replace("'''", "'' '")


def render_codex(meta: dict[str, str], body: str) -> str:
    # Auto-wygenerowany Codex custom prompt (TOML) — fallback dla agentów bez ręcznego pliku.
    name = meta.get("name", "").replace("-", "_")
    description = meta.get("description", "").replace('"', "'")
    out = f'name = "{name}"\ndescription = "{description}"\n\n'
    out += f"developer_instructions = '''\n{_toml_literal(body)}\n'''\n"
    return out


RENDERERS = {
    "vscode": render_vscode,
    "kilo": render_kilo,
    "antigravity": render_antigravity,
    "opencode": render_opencode,
    "codex": render_codex,
}

# GitHub Copilot rozpoznaje tylko *.prompt.md; Codex tylko *.toml; reszta zostaje przy *.md.
DEST_SUFFIX = {
    "vscode": ".prompt.md",
    "codex": ".toml",
}


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        return 1
    fmt, src_dir, dest_dir = argv[1], Path(argv[2]), Path(argv[3])
    curated_dir = Path(argv[4]) if len(argv) == 5 else None
    renderer = RENDERERS.get(fmt)
    if renderer is None:
        print(f"Nieznany format: {fmt} (dozwolone: {', '.join(RENDERERS)})", file=sys.stderr)
        return 1

    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = DEST_SUFFIX.get(fmt)
    for src in sorted(src_dir.glob("*.md")):
        dest_name = src.stem + suffix if suffix else src.name
        if curated_dir is not None and (curated_dir / dest_name).is_file():
            continue  # curated wersja skopiowana osobno (patrz install_codex)
        text = src.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        out = renderer(meta, body)
        (dest_dir / dest_name).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
