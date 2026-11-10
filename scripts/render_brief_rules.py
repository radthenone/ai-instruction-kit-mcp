#!/usr/bin/env python3
"""
Renderuj reguły briefu z templates/shared/rules/brief-rules.md (ADR-0010, #355).

Jedno źródło prawdy: templates/shared/rules/brief-rules.md.
Ten skrypt renderuje:
- src/guides/brief_rules.py (moduł Pythona dla serwera MCP — wariant a)
- templates/claude/language-reminder.mjs (szablon hooka Claude)
- .claude/hooks/language-reminder.mjs (kopię hooka repo kita)
- templates/AGENTS.md (szablon AGENTS.md z blokiem kit:brief-rules)

Użycie:
    scripts/render_brief_rules.py [--check]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "src"))

from guides.brief_rules import (
    BRIEF_RULES_EN,
    BRIEF_RULES_PL,
    HOOK_RULES_EN,
    HOOK_RULES_PL,
    render_hook_rules,
    render_mcp_rules,
)
from guides.bugbot_md import extract_brief_rules

TEMPLATE_FILE = KIT_ROOT / "templates" / "shared" / "rules" / "brief-rules.md"
BRIEF_RULES_PY = KIT_ROOT / "src" / "guides" / "brief_rules.py"
HOOK_TEMPLATE = KIT_ROOT / "templates" / "claude" / "language-reminder.mjs"
HOOK_REPO = KIT_ROOT / ".claude" / "hooks" / "language-reminder.mjs"
AGENTS_TEMPLATE = KIT_ROOT / "templates" / "AGENTS.md"

_RULES_PL_RE = re.compile(r"const rulesPl =\s*[\s\S]*?(?=\n\nif \(language === \"en\"\))")
_AGENTS_BRIEF_RULES_RE = re.compile(
    r"<!-- kit:brief-rules -->[\s\S]*?<!-- /kit:brief-rules -->"
)
_BRIEF_RULES_PY_RE = re.compile(
    r"(# Pre-renderowane warianty dla runtime'u MCP \(ADR-0010 wariant a\)\n)[\s\S]*?(?=\n\n\ndef get_brief_rules)"
)


def _hook_rules_block(hook_pl: str, hook_en: str) -> str:
    return (
        f"const rulesPl =\n  {json.dumps(hook_pl, ensure_ascii=False)};\n\n"
        f"const rulesEn =\n  {json.dumps(hook_en, ensure_ascii=False)};"
    )


def check_brief_rules_freshness(kit_root: Path = KIT_ROOT) -> list[str]:
    """Sprawdź świeżość plików wygenerowanych z szablonu brief-rules.md (#359, ADR-0010).

    Poza runtime'em MCP: serwer nie czyta szablonu (ADR-0010 wariant a).
    Stałe ``src/guides/brief_rules.py`` są sprawdzane z zaimportowanego modułu.

    Args:
        kit_root: Katalog główny kita, z którego czytany jest szablon i pliki wygenerowane.

    Returns:
        list[str]: Opisy nieaktualnych plików; pusta lista oznacza pełną świeżość.
    """
    template_file = kit_root / "templates" / "shared" / "rules" / "brief-rules.md"
    if not template_file.is_file():
        return [f"Brak pliku szablonu reguł briefu: {template_file}"]

    template_text = template_file.read_text(encoding="utf-8")
    mcp_pl = render_mcp_rules(template_text, "pl")
    mcp_en = render_mcp_rules(template_text, "en")
    hook_pl = render_hook_rules(template_text, "pl")
    hook_en = render_hook_rules(template_text, "en")

    stale: list[str] = []

    if (
        BRIEF_RULES_PL.strip() != mcp_pl.strip()
        or BRIEF_RULES_EN.strip() != mcp_en.strip()
        or HOOK_RULES_PL.strip() != hook_pl.strip()
        or HOOK_RULES_EN.strip() != hook_en.strip()
    ):
        stale.append("src/guides/brief_rules.py: stałe MCP nie odpowiadają wyrenderowanemu szablonowi")

    agents_template = kit_root / "templates" / "AGENTS.md"
    if agents_template.is_file():
        brief = extract_brief_rules(agents_template.read_text(encoding="utf-8"))
        if brief is None or brief.strip() != mcp_pl.strip():
            stale.append("templates/AGENTS.md: blok kit:brief-rules nie odpowiada wyrenderowanemu szablonowi")
    else:
        stale.append(f"Brak pliku: {agents_template}")

    expected_hook_block = _hook_rules_block(hook_pl, hook_en)
    hook_template = kit_root / "templates" / "claude" / "language-reminder.mjs"
    if hook_template.is_file():
        m = _RULES_PL_RE.search(hook_template.read_text(encoding="utf-8"))
        if not m or m.group(0).strip() != expected_hook_block:
            stale.append("templates/claude/language-reminder.mjs: reguły hooka nie odpowiadają wyrenderowanemu szablonowi")
    else:
        stale.append(f"Brak pliku: {hook_template}")

    hook_repo = kit_root / ".claude" / "hooks" / "language-reminder.mjs"
    if hook_repo.is_file():
        m = _RULES_PL_RE.search(hook_repo.read_text(encoding="utf-8"))
        if not m or m.group(0).strip() != expected_hook_block:
            stale.append(
                ".claude/hooks/language-reminder.mjs: reguły hooka repozytorium nie odpowiadają wyrenderowanemu szablonowi"
            )

    return stale


def render_all(check: bool = False) -> int:
    if check:
        stale = check_brief_rules_freshness(KIT_ROOT)
        if stale:
            for item in stale:
                print(f"  ! {item}", file=sys.stderr)
            print("Pliki wygenerowane z brief-rules.md są nieaktualne!", file=sys.stderr)
            return 1
        return 0
    template_text = TEMPLATE_FILE.read_text(encoding="utf-8")

    mcp_pl = render_mcp_rules(template_text, "pl")
    mcp_en = render_mcp_rules(template_text, "en")
    hook_pl = render_hook_rules(template_text, "pl")
    hook_en = render_hook_rules(template_text, "en")

    # 1. Update templates/claude/language-reminder.mjs
    hook_text = HOOK_TEMPLATE.read_text(encoding="utf-8")
    new_hook_rules = _hook_rules_block(hook_pl, hook_en)
    rendered_hook = _RULES_PL_RE.sub(lambda _: new_hook_rules, hook_text)
    if rendered_hook != hook_text:
        HOOK_TEMPLATE.write_text(rendered_hook, encoding="utf-8", newline="\n")

    # 2. Update .claude/hooks/language-reminder.mjs if exists
    if HOOK_REPO.is_file():
        repo_hook_text = HOOK_REPO.read_text(encoding="utf-8")
        rendered_repo_hook = _RULES_PL_RE.sub(lambda _: new_hook_rules, repo_hook_text)
        if rendered_repo_hook != repo_hook_text:
            HOOK_REPO.write_text(rendered_repo_hook, encoding="utf-8", newline="\n")

    # 3. Update templates/AGENTS.md
    agents_text = AGENTS_TEMPLATE.read_text(encoding="utf-8")
    new_agents_rules = (
        f"<!-- kit:brief-rules -->\n{mcp_pl.strip()}\n<!-- /kit:brief-rules -->"
    )
    rendered_agents = _AGENTS_BRIEF_RULES_RE.sub(lambda _: new_agents_rules, agents_text)
    if rendered_agents != agents_text:
        AGENTS_TEMPLATE.write_text(rendered_agents, encoding="utf-8", newline="\n")

    # 4. Update src/guides/brief_rules.py (pre-rendered constants for the MCP runtime)
    if (
        BRIEF_RULES_PL.strip() != mcp_pl.strip()
        or BRIEF_RULES_EN.strip() != mcp_en.strip()
        or HOOK_RULES_PL.strip() != hook_pl.strip()
        or HOOK_RULES_EN.strip() != hook_en.strip()
    ):
        py_text = BRIEF_RULES_PY.read_text(encoding="utf-8")
        constants = "\n\n".join(
            f"{name} = (\n"
            + "".join(f"    {line!r}\n" for line in value.splitlines(keepends=True))
            + ")"
            for name, value in (
                ("BRIEF_RULES_PL", mcp_pl),
                ("BRIEF_RULES_EN", mcp_en),
                ("HOOK_RULES_PL", hook_pl),
                ("HOOK_RULES_EN", hook_en),
            )
        )
        rendered_py = _BRIEF_RULES_PY_RE.sub(lambda m: m.group(1) + constants, py_text)
        BRIEF_RULES_PY.write_text(rendered_py, encoding="utf-8", newline="\n")

    return 0


if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    raise SystemExit(render_all(check=check_mode))
