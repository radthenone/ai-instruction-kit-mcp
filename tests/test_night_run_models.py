"""Night-run uruchamia komendy kitu na modelach agentów, nie sesji (#230).

Reguła musi być per klient: Claude Code i opencode mają model per agent, pozostali
klienci zostają na modelu sesji. Sprawdzamy szablon, kopie po reloadzie oraz to, co
naprawdę generuje bootstrap dla klientów bez modelu per agent (Cursor, Codex).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, posix_path, resolve_bash

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)
RULE = "Komendy kitu uruchamiasz według klienta"
BRANCHES = ("**Claude Code:**", "**opencode:**", "**klienci bez modelu per agent**")
REPORT_HEADER = "| Ticket | Stan | Wykonawca | Review | Model | Dowód |"


class TestNightRunModels(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def test_per_client_rule_in_template(self) -> None:
        self.assertIn(RULE, self.text)
        for marker in BRANCHES:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)
        for client in ("Cursor", "Codex", "VS Code", "Kiro", "Kilo", "Antigravity"):
            self.assertIn(client, self.text)
        self.assertIn("bez parametru `model`", self.text)
        self.assertIn("`.opencode/command/`", self.text)
        self.assertIn("model z frontmattera, gdy", self.text)
        self.assertIn("nadpisuje frontmatter", self.text)
        self.assertIn("fallback przy braku agenta", self.text)

    def test_old_nesting_prohibition_is_gone(self) -> None:
        self.assertNotIn("subagent nie uruchomi kolejnych", self.text)
        self.assertNotIn("w Claude: przez Skill, nie", self.text)
        self.assertIn("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", self.text)

    def test_review_uses_agent_not_skill(self) -> None:
        self.assertNotIn("przez Skill", self.text)
        chain = " ".join(self.text.split("## Łańcuch na ticket", 1)[1].split())
        self.assertIn(RULE, chain)
        self.assertNotIn("bez parametru `model`", chain)

    def test_ticket_prompt_git_steps_follow_rule(self) -> None:
        prompt = " ".join(
            self.text.split("## Prompt ticketu", 1)[1].split("## Testy", 1)[0].split()
        )
        self.assertEqual(prompt.count(RULE), 1)
        self.assertNotIn("bez `model`", prompt)
        self.assertIn("CI pilnuje agent `git-end`", prompt)
        self.assertIn("nie naprawia kodu", prompt)
        self.assertIn("hand-backiem", prompt)

    def test_report_has_model_column_and_meta(self) -> None:
        report = self.text.split("## NIGHT-RUN REPORT", 1)[1]
        self.assertIn(REPORT_HEADER, report)
        self.assertIn("meta.json", self.text)
        self.assertIn("message.model", self.text)
        self.assertIn("Fallback modelu", report)

    def test_copies_have_rule_and_no_old_review_path(self) -> None:
        for rel in COPIES:
            copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(copy=rel):
                self.assertIn(RULE, copy)
                self.assertNotIn("subagent nie uruchomi kolejnych", copy)
                self.assertNotIn("przez Skill", copy)
                self.assertIn(REPORT_HEADER, copy)


class TestGeneratedCopiesWithoutModelPerAgent(unittest.TestCase):
    """Cursor i Codex nie dostają ścieżki do agentów Claude — nie mają modelu per agent."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="kit-night-run-clients-")
        target = Path(cls._tmp) / "generated"
        (target / ".ai").mkdir(parents=True)
        profile = KIT_ROOT / ".ai" / "project.profile.yaml"
        shutil.copy2(profile, target / ".ai" / "project.profile.yaml")

        bash = resolve_bash()
        if not bash:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            if is_ci():
                raise AssertionError("brak bash na CI — generowanie kopii musi być sprawdzone")
            raise unittest.SkipTest("brak bash — pomijam generowanie kopii")
        result = subprocess.run(
            [
                bash,
                "--noprofile",
                "--norc",
                posix_path(KIT_ROOT / "scripts" / "bootstrap-project.sh"),
                str(target),
                "--clients",
                "cursor,codex",
                "--from",
                str(KIT_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise AssertionError(f"bootstrap nie wystartował ({result.returncode}): {result.stderr}")
        cls.generated = target

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_cursor_and_codex_do_not_point_to_claude_agents(self) -> None:
        for rel in (".cursor/agents/night-run.md", ".codex/skills/night-run/SKILL.md"):
            text = (self.generated / rel).read_text(encoding="utf-8")
            with self.subTest(copy=rel):
                self.assertNotIn(".claude/agents", text)
                self.assertNotIn("**Claude Code:**", text)
                self.assertIn(RULE, text)
                for marker in BRANCHES[1:]:
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
