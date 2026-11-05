"""Testy weryfikujące generowanie i spójność reguł briefu z szablonu (#355, ADR-0010)."""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = KIT_ROOT / "templates" / "shared" / "rules" / "brief-rules.md"
HOOK_TEMPLATE = KIT_ROOT / "templates" / "claude" / "language-reminder.mjs"
HOOK_REPO = KIT_ROOT / ".claude" / "hooks" / "language-reminder.mjs"
AGENTS_TEMPLATE = KIT_ROOT / "templates" / "AGENTS.md"
RENDER_SCRIPT = KIT_ROOT / "scripts" / "render_brief_rules.py"


def load_render_script():
    """Załaduj scripts/render_brief_rules.py jako moduł (logika freshness żyje poza runtime'em MCP, ADR-0010)."""
    spec = importlib.util.spec_from_file_location("render_brief_rules", RENDER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBriefRules(unittest.TestCase):
    """Szablon reguł briefu i generowane warianty językowe (#355)."""

    def test_template_file_exists(self) -> None:
        """Szablon templates/shared/rules/brief-rules.md istnieje."""
        self.assertTrue(TEMPLATE_PATH.is_file(), f"Brak szablonu: {TEMPLATE_PATH}")

    def test_brief_rules_module_pl_and_en(self) -> None:
        """Moduł guides.brief_rules zwraca poprawne reguły w wariantach pl i en."""
        from guides.brief_rules import get_brief_rules, get_hook_rules

        # Wariant PL
        pl_rules = get_brief_rules("pl")
        self.assertIn("## Klasyfikacja zadań i reguły MCP (#307, #324)", pl_rules)
        self.assertIn("Zadanie kodowe", pl_rules)
        self.assertIn("Zadanie proceduralne", pl_rules)
        self.assertIn("get_overlay", pl_rules)
        self.assertIn("po polsku", pl_rules)
        self.assertIn("VPS", pl_rules)

        # Wariant EN
        en_rules = get_brief_rules("en")
        self.assertIn("## Task classification and MCP rules (#307, #324)", en_rules)
        self.assertIn("Coding task", en_rules)
        self.assertIn("Procedural task", en_rules)
        self.assertIn("get_overlay", en_rules)
        self.assertIn("in English", en_rules)
        self.assertIn("VPS", en_rules)

        # Hook PL
        pl_hook = get_hook_rules("pl")
        self.assertIn("Klasyfikacja zadań i reguły MCP (#307, #324):", pl_hook)
        self.assertIn("get_overlay", pl_hook)
        self.assertIn("po polsku", pl_hook)

        # Hook EN
        en_hook = get_hook_rules("en")
        self.assertIn("Task classification and MCP rules (#307, #324):", en_hook)
        self.assertIn("get_overlay", en_hook)
        self.assertIn("in English", en_hook)

    def test_generator_renders_from_template(self) -> None:
        """Generator renderuje reguły bezpośrednio z treści szablonu."""
        from guides.brief_rules import (
            get_brief_rules,
            get_hook_rules,
            render_hook_rules,
            render_mcp_rules,
        )

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertEqual(render_mcp_rules(template_text, "pl").strip(), get_brief_rules("pl").strip())
        self.assertEqual(render_mcp_rules(template_text, "en").strip(), get_brief_rules("en").strip())
        self.assertEqual(render_hook_rules(template_text, "pl").strip(), get_hook_rules("pl").strip())
        self.assertEqual(render_hook_rules(template_text, "en").strip(), get_hook_rules("en").strip())

    def test_hook_contains_rendered_rules(self) -> None:
        """Hook language-reminder.mjs zawiera reguły wygenerowane z szablonu (#355)."""
        from guides.brief_rules import get_hook_rules

        hook_text = HOOK_TEMPLATE.read_text(encoding="utf-8")
        pl_rules = get_hook_rules("pl")
        en_rules = get_hook_rules("en")

        self.assertIn(pl_rules, hook_text)
        self.assertIn(en_rules, hook_text)

    def test_agents_template_contains_rendered_rules(self) -> None:
        """templates/AGENTS.md zawiera blok kit:brief-rules z regułami z szablonu (#355)."""
        from guides.brief_rules import get_brief_rules
        from guides.bugbot_md import extract_brief_rules

        agents_text = AGENTS_TEMPLATE.read_text(encoding="utf-8")
        brief_rules = extract_brief_rules(agents_text)
        self.assertIsNotNone(brief_rules)
        assert brief_rules is not None  # zawęża typ dla ty (assertIsNotNone tego nie robi)
        self.assertEqual(brief_rules.strip(), get_brief_rules("pl").strip())


def extract_hook_rule(hook_content: str, language: str = "pl") -> str:
    """Wyciągnij wartość reguły (rulesPl lub rulesEn) z kodu hooka language-reminder.mjs."""
    lang = "en" if language.lower().startswith("en") else "pl"
    var_name = "rulesEn" if lang == "en" else "rulesPl"
    pattern = rf"const {var_name} =\s*\n?\s*\"([^\"\\]*(?:\\.[^\"\\]*)*)\";"
    match = re.search(pattern, hook_content)
    if not match:
        raise ValueError(f"Nie znaleziono zmiennej {var_name} w hooku")
    return json.loads(f"\"{match.group(1)}\"")


class TestBriefRulesFreshness(unittest.TestCase):
    """Testy świeżości (freshness) generowanych plików reguł briefu (#359, ADR-0010)."""

    def test_check_brief_rules_freshness_all_clean(self) -> None:
        """Funkcja check_brief_rules_freshness potwierdza świeżość wszystkich generowanych plików (#359)."""
        stale = load_render_script().check_brief_rules_freshness(KIT_ROOT)
        self.assertEqual(stale, [], f"Nieaktualne pliki reguł briefu: {stale}")

    def test_hook_template_is_fresh(self) -> None:
        """Hook templates/claude/language-reminder.mjs ma reguły identyczne z renderem szablonu (#359)."""
        from guides.brief_rules import render_hook_rules

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        expected_pl = render_hook_rules(template_text, "pl").strip()
        expected_en = render_hook_rules(template_text, "en").strip()

        hook_text = HOOK_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(extract_hook_rule(hook_text, "pl").strip(), expected_pl)
        self.assertEqual(extract_hook_rule(hook_text, "en").strip(), expected_en)

    def test_agents_template_is_fresh(self) -> None:
        """Sekcja kit:brief-rules w templates/AGENTS.md jest identyczna z renderem szablonu (#359)."""
        from guides.brief_rules import render_mcp_rules
        from guides.bugbot_md import extract_brief_rules

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        expected = render_mcp_rules(template_text, "pl").strip()

        agents_text = AGENTS_TEMPLATE.read_text(encoding="utf-8")
        brief_rules = extract_brief_rules(agents_text)
        self.assertIsNotNone(brief_rules)
        assert brief_rules is not None
        self.assertEqual(brief_rules.strip(), expected)

    def test_script_render_brief_rules_check_passes(self) -> None:
        """Skrypt scripts/render_brief_rules.py --check kończy się sukcesem (kod 0) (#359)."""
        import subprocess
        import sys

        res = subprocess.run(
            [sys.executable, str(KIT_ROOT / "scripts" / "render_brief_rules.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"Błąd skryptu render_brief_rules.py --check: {res.stderr}")

    def test_manual_edit_in_generated_files_detected(self) -> None:
        """Ręczna zmiana w wygenerowanym pliku (hook, AGENTS.md) bez szablonu wywala freshness (#359)."""
        import tempfile
        import shutil

        check_brief_rules_freshness = load_render_script().check_brief_rules_freshness

        with tempfile.TemporaryDirectory(prefix="kit-freshness-") as tmp:
            tmp_root = Path(tmp)
            # Przygotuj strukturę z plikami wygenerowanymi
            (tmp_root / "templates" / "shared" / "rules").mkdir(parents=True)
            (tmp_root / "templates" / "claude").mkdir(parents=True)
            (tmp_root / ".claude" / "hooks").mkdir(parents=True)

            shutil.copy(TEMPLATE_PATH, tmp_root / "templates" / "shared" / "rules" / "brief-rules.md")
            shutil.copy(AGENTS_TEMPLATE, tmp_root / "templates" / "AGENTS.md")
            shutil.copy(HOOK_TEMPLATE, tmp_root / "templates" / "claude" / "language-reminder.mjs")
            if HOOK_REPO.is_file():
                shutil.copy(HOOK_REPO, tmp_root / ".claude" / "hooks" / "language-reminder.mjs")

            # W czystym stanie brak błędów
            self.assertEqual(check_brief_rules_freshness(tmp_root), [])

            # 1. Ręczna edycja w templates/AGENTS.md
            agents_file = tmp_root / "templates" / "AGENTS.md"
            orig_agents = agents_file.read_text(encoding="utf-8")
            agents_file.write_text(orig_agents.replace("Klasyfikacja zadań", "Ręczna modyfikacja"), encoding="utf-8")
            stale = check_brief_rules_freshness(tmp_root)
            self.assertTrue(any("templates/AGENTS.md" in s for s in stale), f"Nie wykryto edycji AGENTS.md: {stale}")
            agents_file.write_text(orig_agents, encoding="utf-8")

            # 2. Ręczna edycja w templates/claude/language-reminder.mjs
            hook_file = tmp_root / "templates" / "claude" / "language-reminder.mjs"
            orig_hook = hook_file.read_text(encoding="utf-8")
            hook_file.write_text(orig_hook.replace("Klasyfikacja zadań", "Ręczna modyfikacja"), encoding="utf-8")
            stale = check_brief_rules_freshness(tmp_root)
            self.assertTrue(any("templates/claude/language-reminder.mjs" in s for s in stale), f"Nie wykryto edycji hooka: {stale}")
            hook_file.write_text(orig_hook, encoding="utf-8")

            # 3. Ręczna edycja w .claude/hooks/language-reminder.mjs
            repo_hook_file = tmp_root / ".claude" / "hooks" / "language-reminder.mjs"
            if repo_hook_file.is_file():
                orig_repo_hook = repo_hook_file.read_text(encoding="utf-8")
                repo_hook_file.write_text(orig_repo_hook.replace("Klasyfikacja zadań", "Ręczna modyfikacja"), encoding="utf-8")
                stale = check_brief_rules_freshness(tmp_root)
                self.assertTrue(any(".claude/hooks/language-reminder.mjs" in s for s in stale), f"Nie wykryto edycji repo hooka: {stale}")
                repo_hook_file.write_text(orig_repo_hook, encoding="utf-8")

    def test_repo_hook_is_fresh(self) -> None:
        """Hook repozytorium .claude/hooks/language-reminder.mjs jest identyczny z renderem szablonu (#359)."""
        from guides.brief_rules import render_hook_rules

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        expected_pl = render_hook_rules(template_text, "pl").strip()
        expected_en = render_hook_rules(template_text, "en").strip()

        repo_hook_text = HOOK_REPO.read_text(encoding="utf-8")
        self.assertEqual(extract_hook_rule(repo_hook_text, "pl").strip(), expected_pl)
        self.assertEqual(extract_hook_rule(repo_hook_text, "en").strip(), expected_en)


if __name__ == "__main__":
    unittest.main()
