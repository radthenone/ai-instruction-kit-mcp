"""Testy weryfikujące generowanie i spójność reguł briefu z szablonu (#355, ADR-0010)."""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = KIT_ROOT / "templates" / "shared" / "rules" / "brief-rules.md"


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


if __name__ == "__main__":
    unittest.main()
