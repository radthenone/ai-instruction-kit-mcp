"""Odpowiedzi agenta idą w języku Profilu, niezależnie od języka wejścia (#248).

Kontrola tekstowa źródeł: reguła w AGENTS.md i plikach klientów, linia języka w
szablonach orkiestratorów oraz w stopce `/headless`. Render u klienta sprawdza
test_generated_artifacts; tutaj pilnujemy, że źródła niosą regułę.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = KIT_ROOT / "templates"

INDEPENDENCE = "niezależnie od języka wejścia"

# Źródła instrukcji, w których ma być reguła niezależności od języka wejścia.
INSTRUCTION_SOURCES = (
    "AGENTS.md",
    "shared/rules/use-guides.md",
    "cursor/rules/use-guides.mdc",
    "kiro/steering/instruction-kit.md",
)

# Orkiestratory odpalające subagentów: prompt dla subagenta i hand-back w języku z get_language.
ORCHESTRATORS = (
    "night-run",
    "review-architecture",
    "review-backend",
    "review-bugbot",
    "review-edge",
    "review-frontend",
    "review-security",
    "review-tests",
    "review-ui",
    "git-start",
    "git-commit",
    "git-end",
    "git-check",
    "headless",
)


class AgentLanguageRuleTest(unittest.TestCase):
    def test_instruction_sources_state_independence_from_input_language(self) -> None:
        for rel in INSTRUCTION_SOURCES:
            with self.subTest(source=rel):
                text = (TEMPLATES / rel).read_text(encoding="utf-8")
                self.assertIn(INDEPENDENCE, text)

    def test_orchestrator_templates_name_subagent_prompt_and_handback_language(self) -> None:
        for name in ORCHESTRATORS:
            with self.subTest(agent=name):
                text = (TEMPLATES / "shared" / "agents" / f"{name}.md").read_text(encoding="utf-8")
                if name == "headless":
                    text = (TEMPLATES / "shared" / "headless" / "headless.mjs").read_text(encoding="utf-8")
                    self.assertIn("Język odpowiedzi", text)
                    continue
                self.assertIn("prompt dla subagenta", text)
                self.assertIn("hand-back", text)
                self.assertIn("get_language", text)


if __name__ == "__main__":
    unittest.main()
