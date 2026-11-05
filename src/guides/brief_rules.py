"""Generowany moduł z regułami briefu dla serwera MCP i narzędzi kita (#355, ADR-0010).

Moduł niesie warianty językowe wyrenderowane z szablonu `templates/shared/rules/brief-rules.md`.
Runtime serwera MCP nie czyta szablonu z dysku (ADR-0010 wariant a).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_LANG_BLOCK_RE = re.compile(r"<!-- lang:(\w+) -->\n(.*?)<!-- /lang:\1 -->", re.DOTALL)
_HOOK_BLOCK_RE = re.compile(r"<!-- hook:(\w+) -->\n(.*?)<!-- /hook:\1 -->", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"\{\{docstring_language\|([^}]*)\}\}")


def render_mcp_rules(template_text: str, language: str = "pl") -> str:
    """
    Wyrenderuj reguły w formacie Markdown dla serwera MCP z szablonu.

    Args:
        template_text: Surowa treść szablonu brief-rules.md.
        language: Kod języka (pl lub en).

    Returns:
        str: Wyrenderowane reguły w Markdownie.
    """
    lang = "en" if language.lower().startswith("en") else "pl"
    for match in _LANG_BLOCK_RE.finditer(template_text):
        if match.group(1) == lang:
            content = match.group(2).strip()
            # Podstaw placeholder języka docstringów
            doc_lang = "in English" if lang == "en" else "po polsku"
            content = _PLACEHOLDER_RE.sub(doc_lang, content)
            return content
    raise ValueError(f"Brak bloku lang:{lang} w szablonie reguł briefu")


def render_hook_rules(template_text: str, language: str = "pl") -> str:
    """
    Wyrenderuj reguły w formacie jednolinijkowym dla hooka z szablonu.

    Args:
        template_text: Surowa treść szablonu brief-rules.md.
        language: Kod języka (pl lub en).

    Returns:
        str: Wyrenderowane reguły dla hooka.
    """
    lang = "en" if language.lower().startswith("en") else "pl"
    for match in _HOOK_BLOCK_RE.finditer(template_text):
        if match.group(1) == lang:
            content = match.group(2).strip()
            doc_lang = "in English" if lang == "en" else "po polsku"
            content = _PLACEHOLDER_RE.sub(doc_lang, content)
            return content
    raise ValueError(f"Brak bloku hook:{lang} w szablonie reguł briefu")


# Pre-renderowane warianty dla runtime'u MCP (ADR-0010 wariant a)
BRIEF_RULES_PL = (
    "## Klasyfikacja zadań i reguły MCP (#307, #324)\n"
    "\n"
    "- **Zadanie kodowe:** tworzenie, edycja lub debug plików w `src/`, `tests/`, `templates/`, `modules/`; "
    "implementacja, testy, refactor, pytanie o zachowanie kodu do zmiany.\n"
    "- **Zadanie proceduralne:** każdy slash command z procedury kita (`/git-*`, `/review-*`, `/create-task`, "
    "`/create-skill`, `/night-run`, `/headless`, `/tdd`, `/kit-project-*`) oraz każda czynność zapisu na GitHub.\n"
    "- **Wymóg wywołania:** przed pierwszą edycją przy zadaniu kodowym lub proceduralnym wywołaj `get_overlay`, "
    "a `get_bundle` gdy brief wskazuje moduł. W wątpliwości wywołaj `get_overlay` "
    "(koszt mały, błędny fix bez overlay kosztuje dużo).\n"
    "- **Bez wywołań MCP:** pytania o język, bazę lub Tiery (są w briefie), rozmowa, wyjaśnienie, "
    "odpowiedź tekstowa bez zmiany plików.\n"
    "- **Docstringi:** format repo (Args/Returns, po polsku).\n"
    "- **VPS (#317):** na hoście VPS zakaz instalacji pakietów i buildów poza lockfile-only "
    "(`uv lock --no-build`, `npm install --package-lock-only --ignore-scripts`)."
)

BRIEF_RULES_EN = (
    "## Task classification and MCP rules (#307, #324)\n"
    "\n"
    "- **Coding task:** create, edit or debug files in `src/`, `tests/`, `templates/`, `modules/`; "
    "implementation, tests, refactor, questions on code behavior to change.\n"
    "- **Procedural task:** any kit slash command (`/git-*`, `/review-*`, `/create-task`, `/create-skill`, "
    "`/night-run`, `/headless`, `/tdd`, `/kit-project-*`) and any GitHub write action.\n"
    "- **Require calling:** require calling `get_overlay` before first edit "
    "(and `get_bundle` when brief points to module); when in doubt call `get_overlay` "
    "(small cost, wrong fix without overlay costs a lot).\n"
    "- **No MCP calls:** questions about language, base or Tiers (are in the brief), conversation, "
    "explanation, text response without file edits.\n"
    "- **Docstrings:** repo format (Args/Returns, in English).\n"
    "- **VPS (#317):** on VPS host package installs and builds are denied except lockfile-only "
    "(`uv lock --no-build`, `npm install --package-lock-only --ignore-scripts`)."
)

HOOK_RULES_PL = (
    "Klasyfikacja zadań i reguły MCP (#307, #324): "
    "Zadanie kodowe (tworzenie, edycja lub debug plików w src/, tests/, templates/, modules/; "
    "implementacja, testy, refactor, pytanie o zachowanie kodu do zmiany) lub proceduralne "
    "(każdy slash command kita: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, "
    "oraz każda czynność zapisu na GitHub): wymóg wywołania get_overlay przed pierwszą edycją "
    "(a get_bundle gdy brief wskazuje moduł); w wątpliwości wywołaj get_overlay (koszt mały, błędny fix bez overlay kosztuje dużo). "
    "Pytania o język, bazę, Tiery i rozmowa bez zmian plików — bez wywołań MCP (#307). "
    "Docstringi w formacie repo (Args/Returns, po polsku). "
    "Na hoście VPS zakaz instalacji pakietów i buildów poza lockfile-only (#317, np. uv lock --no-build, npm install --package-lock-only --ignore-scripts)."
)

HOOK_RULES_EN = (
    "Task classification and MCP rules (#307, #324): "
    "Coding task (create, edit or debug files in src/, tests/, templates/, modules/; "
    "implementation, tests, refactor, questions on code behavior to change) or procedural task "
    "(any kit slash command: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, "
    "and any GitHub write action): require calling get_overlay before first edit "
    "(and get_bundle when brief points to module); when in doubt call get_overlay (small cost, wrong fix without overlay costs a lot). "
    "Questions about language, base, Tiers and conversation without file edits — no MCP calls (#307). "
    "Docstrings in repo format (Args/Returns, in English). "
    "On VPS host package installs and builds are denied except lockfile-only (#317, e.g. uv lock --no-build, npm install --package-lock-only --ignore-scripts)."
)


def get_brief_rules(language: str = "pl") -> str:
    """Zwróć pre-renderowane reguły briefu w wybranym języku (pl lub en)."""
    lang = "en" if language.lower().startswith("en") else "pl"
    return BRIEF_RULES_EN if lang == "en" else BRIEF_RULES_PL


def get_hook_rules(language: str = "pl") -> str:
    """Zwróć pre-renderowane reguły hooka w wybranym języku (pl lub en)."""
    lang = "en" if language.lower().startswith("en") else "pl"
    return HOOK_RULES_EN if lang == "en" else HOOK_RULES_PL


_RULES_PL_RE = re.compile(r"const rulesPl =\s*[\s\S]*?(?=\n\nif \(language === \"en\"\))")


def check_brief_rules_freshness(kit_root: Path | None = None) -> list[str]:
    """Sprawdź świeżość wszystkich plików wygenerowanych z szablonu brief-rules.md (#359, ADR-0010).

    Args:
        kit_root: Ścieżka do katalogu głównego kita (domyślnie wykrywana).

    Returns:
        list[str]: Lista opisów plików, które są nieaktualne lub zmodyfikowane ręcznie.
                   Pusta lista oznacza pełną świeżość.
    """
    if kit_root is None:
        kit_root = Path(__file__).resolve().parents[2]

    template_file = kit_root / "templates" / "shared" / "rules" / "brief-rules.md"
    if not template_file.is_file():
        return [f"Brak pliku szablonu reguł briefu: {template_file}"]

    template_text = template_file.read_text(encoding="utf-8")
    mcp_pl = render_mcp_rules(template_text, "pl")
    mcp_en = render_mcp_rules(template_text, "en")
    hook_pl = render_hook_rules(template_text, "pl")
    hook_en = render_hook_rules(template_text, "en")

    stale: list[str] = []

    # 1. Sprawdź stałe w src/guides/brief_rules.py
    if (
        BRIEF_RULES_PL.strip() != mcp_pl.strip()
        or BRIEF_RULES_EN.strip() != mcp_en.strip()
        or HOOK_RULES_PL.strip() != hook_pl.strip()
        or HOOK_RULES_EN.strip() != hook_en.strip()
    ):
        stale.append("src/guides/brief_rules.py: stałe MCP nie odpowiadają wyrenderowanemu szablonowi")

    # 2. Sprawdź templates/AGENTS.md
    agents_template = kit_root / "templates" / "AGENTS.md"
    if agents_template.is_file():
        from guides.bugbot_md import extract_brief_rules

        agents_text = agents_template.read_text(encoding="utf-8")
        brief = extract_brief_rules(agents_text)
        if brief is None or brief.strip() != mcp_pl.strip():
            stale.append("templates/AGENTS.md: blok kit:brief-rules nie odpowiada wyrenderowanemu szablonowi")
    else:
        stale.append(f"Brak pliku: {agents_template}")

    # 3. Sprawdź templates/claude/language-reminder.mjs
    hook_template = kit_root / "templates" / "claude" / "language-reminder.mjs"
    expected_hook_block = (
        f"const rulesPl =\n  {json.dumps(hook_pl, ensure_ascii=False)};\n\n"
        f"const rulesEn =\n  {json.dumps(hook_en, ensure_ascii=False)};"
    )
    if hook_template.is_file():
        hook_text = hook_template.read_text(encoding="utf-8")
        m = _RULES_PL_RE.search(hook_text)
        if not m or m.group(0).strip() != expected_hook_block.strip():
            stale.append("templates/claude/language-reminder.mjs: reguły hooka nie odpowiadają wyrenderowanemu szablonowi")
    else:
        stale.append(f"Brak pliku: {hook_template}")

    # 4. Sprawdź .claude/hooks/language-reminder.mjs (jeśli istnieje)
    hook_repo = kit_root / ".claude" / "hooks" / "language-reminder.mjs"
    if hook_repo.is_file():
        repo_hook_text = hook_repo.read_text(encoding="utf-8")
        m = _RULES_PL_RE.search(repo_hook_text)
        if not m or m.group(0).strip() != expected_hook_block.strip():
            stale.append(".claude/hooks/language-reminder.mjs: reguły hooka repozytorium nie odpowiadają wyrenderowanemu szablonowi")

    return stale
