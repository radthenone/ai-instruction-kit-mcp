#!/usr/bin/env python3
"""
Renderuj templates/shared/agents/*.md do natywnego formatu slash-command klienta.

Użycie:
    render_agent_commands.py FORMAT SRC_DIR DEST_DIR

FORMAT: vscode | kilo | opencode (zarazem nazwa celu w command_prefixes, #525)
        | claude (plugin skills-dir ``kit-ai``, #526)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from command_prefix import read_values, resolve

MANIFEST = Path(__file__).resolve().parents[1] / "manifest.yaml"
ARGUMENTS_LINE = "Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS\n\n"
PLUGIN = {"name": "kit-ai", "description": "Komendy instruction-kit jako /kit-ai:<nazwa>."}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines(keepends=True)
    assert lines[0].strip() == "---", "brak frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    meta: dict[str, str] = {}
    key: str | None = None
    for line in lines[1:end]:
        s = line.strip()
        if key and (line.startswith((" ", "\t")) or not s):
            meta[key] = f"{meta[key]} {s}".strip() if s else meta[key]
            continue
        key = None
        if ":" in line:
            name, _, val = line.partition(":")
            name, val = name.strip(), val.strip()
            key = name if name == "description" and val in (">", ">-", "|", "|-") else None
            meta[name] = "" if key else val
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


def render_opencode(meta: dict[str, str], body: str) -> str:
    # opencode custom command: .opencode/command/<name>.md, wywołanie /<name>, $ARGUMENTS wspierane.
    description = meta.get("description", "").replace('"', "'")
    front = f'---\ndescription: "{description}"\n---\n\n'
    front += "Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS\n\n"
    return front + body


def render_claude(meta: dict[str, str], body: str) -> str:
    # Skill pluginu skills-dir: .claude/skills/kit-ai/skills/<name>/SKILL.md,
    # wywołanie /kit-ai:<name>. `readonly:` to pole subagentów, nie skilli.
    kept = "".join(f"{key}: {value}\n" for key, value in meta.items() if key != "readonly")
    return f"---\n{kept}---\n\n" + ARGUMENTS_LINE + body


RENDERERS = {
    "vscode": render_vscode,
    "kilo": render_kilo,
    "opencode": render_opencode,
    "claude": render_claude,
}

# GitHub Copilot rozpoznaje tylko *.prompt.md; reszta zostaje przy *.md.
DEST_SUFFIX = {
    "vscode": ".prompt.md",
}


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 1
    fmt, src_dir, dest_dir = argv[1], Path(argv[2]), Path(argv[3])
    renderer = RENDERERS.get(fmt)
    if renderer is None:
        print(f"Nieznany format: {fmt} (dozwolone: {', '.join(RENDERERS)})", file=sys.stderr)
        return 1
    try:
        sigil, namespace, name_prefix = read_values(MANIFEST, fmt)
    except ValueError as exc:
        print(f"render_agent_commands: {exc}", file=sys.stderr)
        return 1

    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = DEST_SUFFIX.get(fmt)
    if fmt == "claude":
        (dest_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (dest_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(PLUGIN, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    for src in sorted(src_dir.glob("*.md")):
        if fmt == "claude":
            dest = dest_dir / "skills" / src.stem / "SKILL.md"
        else:
            dest = dest_dir / (src.stem + suffix if suffix else src.name)
        text = resolve(
            src.read_text(encoding="utf-8"), sigil=sigil, namespace=namespace, name_prefix=name_prefix
        )
        meta, body = parse_frontmatter(text)
        out = renderer(meta, body)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
