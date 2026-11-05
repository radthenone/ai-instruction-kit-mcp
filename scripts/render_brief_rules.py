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
    render_hook_rules,
    render_mcp_rules,
)

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


def render_all(check: bool = False) -> int:
    template_text = TEMPLATE_FILE.read_text(encoding="utf-8")

    mcp_pl = render_mcp_rules(template_text, "pl")
    mcp_en = render_mcp_rules(template_text, "en")
    hook_pl = render_hook_rules(template_text, "pl")
    hook_en = render_hook_rules(template_text, "en")

    dirty = False

    # 1. Update templates/claude/language-reminder.mjs
    hook_text = HOOK_TEMPLATE.read_text(encoding="utf-8")
    new_hook_rules = (
        f"const rulesPl =\n  {json.dumps(hook_pl, ensure_ascii=False)};\n\n"
        f"const rulesEn =\n  {json.dumps(hook_en, ensure_ascii=False)};"
    )
    rendered_hook = _RULES_PL_RE.sub(lambda _: new_hook_rules, hook_text)
    if rendered_hook != hook_text:
        if check:
            dirty = True
        else:
            HOOK_TEMPLATE.write_text(rendered_hook, encoding="utf-8", newline="\n")

    # 2. Update .claude/hooks/language-reminder.mjs if exists
    if HOOK_REPO.is_file():
        repo_hook_text = HOOK_REPO.read_text(encoding="utf-8")
        rendered_repo_hook = _RULES_PL_RE.sub(lambda _: new_hook_rules, repo_hook_text)
        if rendered_repo_hook != repo_hook_text:
            if check:
                dirty = True
            else:
                HOOK_REPO.write_text(rendered_repo_hook, encoding="utf-8", newline="\n")

    # 3. Update templates/AGENTS.md
    agents_text = AGENTS_TEMPLATE.read_text(encoding="utf-8")
    new_agents_rules = (
        f"<!-- kit:brief-rules -->\n{mcp_pl.strip()}\n<!-- /kit:brief-rules -->"
    )
    rendered_agents = _AGENTS_BRIEF_RULES_RE.sub(lambda _: new_agents_rules, agents_text)
    if rendered_agents != agents_text:
        if check:
            dirty = True
        else:
            AGENTS_TEMPLATE.write_text(rendered_agents, encoding="utf-8", newline="\n")

    # 4. Update src/guides/brief_rules.py (pre-rendered constants for the MCP runtime)
    from guides.brief_rules import BRIEF_RULES_EN, BRIEF_RULES_PL, HOOK_RULES_EN, HOOK_RULES_PL

    if (
        BRIEF_RULES_PL.strip() != mcp_pl.strip()
        or BRIEF_RULES_EN.strip() != mcp_en.strip()
        or HOOK_RULES_PL.strip() != hook_pl.strip()
        or HOOK_RULES_EN.strip() != hook_en.strip()
    ):
        if check:
            dirty = True
        else:
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

    if check and dirty:
        print("Pliki wygenerowane z brief-rules.md są nieaktualne!", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    raise SystemExit(render_all(check=check_mode))
