"""Krok Retro w /night-run (#372): ostatni przed NIGHT-RUN REPORT, tylko propozycje.

Skan (`kit-ai retro scan`) i klasyfikacja (`/kit-retro`) wracają do rozmowy, a raport dostaje
jedną linię podsumowania. Issue z tych znalezisk zakłada człowiek po akceptacji, nie
orkiestrator, i krok nie może zablokować raportu, gdy skan się nie uda.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)
RETRO_HEADING = "\n## Retro\n"
REPORT_HEADING = "\n## NIGHT-RUN REPORT"


def retro_step(text: str) -> str:
    """Sekcja Retro: od nagłówka do pierwszego nagłówka raportu (bez nagłówka raportu)."""
    start = text.index(RETRO_HEADING) + 1
    end = text.index(REPORT_HEADING, start) + 1
    return text[start:end]


class NightRunRetroStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def test_retro_step_precedes_report(self) -> None:
        self.assertIn(RETRO_HEADING, self.text)
        self.assertLess(self.text.index(RETRO_HEADING), self.text.index(REPORT_HEADING))

    def test_retro_is_last_step_before_report(self) -> None:
        step = retro_step(self.text)
        self.assertEqual(re.findall(r"^## ", step[len("## Retro") :], re.MULTILINE), [])
        self.assertLess(self.text.index("## Pomiar kosztu ticketu"), self.text.index(RETRO_HEADING))

    def test_step_scans_then_classifies_with_skill(self) -> None:
        step = retro_step(self.text)
        self.assertIn("kit-ai retro scan --since", step)
        self.assertIn("`/kit-retro`", step)
        self.assertLess(step.index("kit-ai retro scan"), step.index("`/kit-retro`"))

    def test_step_is_non_blocking(self) -> None:
        self.assertIn("pominięte", retro_step(self.text))

    def test_step_leaves_issues_to_human(self) -> None:
        self.assertIn("nie zakładasz issue", retro_step(self.text))

    def test_report_has_retro_summary_line(self) -> None:
        report = self.text.split("## NIGHT-RUN REPORT", 1)[1]
        self.assertIn("Retro: <liczba znalezisk>", report)


class NightRunRetroCopiesTests(unittest.TestCase):
    def test_dogfood_copies_carry_retro_step(self) -> None:
        for rel in COPIES:
            with self.subTest(copy=rel):
                text = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(RETRO_HEADING, text)


if __name__ == "__main__":
    unittest.main()
