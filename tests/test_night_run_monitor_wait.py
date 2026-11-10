"""Weryfikacja procedur night-run pod kątem oczekiwania przez Monitor zamiast sleep (#335).

Procedury nie mogą kazać agentowi czekać przez `sleep N; <cmd>` (harness Claude Code
to blokuje: 'Blocked: sleep'). Dozwolony jest wyłącznie wzorzec Monitor z pętlą until
dla Claude Code oraz foreground `timeout … until grep` dla pozostałych klientów.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
HEADLESS_TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "headless.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)

ALLOWED_UNTIL_LOOP = re.compile(r"until\s+[^;]+;\s*do\s+sleep\s+\d+;\s*done")


def find_forbidden_sleeps(text: str) -> list[str]:
    """Zwraca wystąpienia `sleep \\d+;` znajdujące się poza wzorcem until-loop."""
    stripped = ALLOWED_UNTIL_LOOP.sub("<ALLOWED_UNTIL_LOOP>", text)
    return [m.strip() for m in re.findall(r"[^\n]*sleep\s+\d+;[^\n]*", stripped)]


class TestNightRunMonitorWait(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def _background_section(self, text: str) -> str:
        return text.split("- Praca w tle", 1)[1].split("\n- ", 1)[0]

    def test_no_sleep_outside_until_pattern_in_template(self) -> None:
        forbidden = find_forbidden_sleeps(self.text)
        self.assertEqual(
            forbidden,
            [],
            msg=f"Znaleziono niedozwolone `sleep \\d+;` w szablonie night-run: {forbidden}",
        )

    def test_explicit_ban_on_sleep_cmd(self) -> None:
        flat = " ".join(self.text.split())
        self.assertRegex(
            flat,
            r"[Zz]akaz `?sleep N; <cmd>`?",
            msg="Szablon powinien wprost zakazywać `sleep N; <cmd>`",
        )
        self.assertIn("Blocked: sleep", self.text)

    def test_monitor_pattern_for_claude(self) -> None:
        background_sec = self._background_section(self.text)
        self.assertIn("Monitor", background_sec)

    def test_foreground_timeout_stays_for_clients_without_monitor(self) -> None:
        background_sec = self._background_section(self.text)
        self.assertIn("timeout", background_sec)
        self.assertIn("pierwszoplanow", background_sec)

    def test_ticket_subagent_waits_in_foreground(self) -> None:
        paragraph = self._background_section(self.text).split("(tylko Claude Code)", 1)[1]
        self.assertIn("timeout", paragraph)
        self.assertIn("until grep", paragraph)

    def test_ci_checks_no_sleep_prefix(self) -> None:
        self.assertNotIn("sleep 20; gh pr checks", self.text)
        self.assertIn("gh pr checks", self.text)

    def test_headless_template_has_no_waiting_sleep(self) -> None:
        headless_text = HEADLESS_TEMPLATE.read_text(encoding="utf-8")
        forbidden = find_forbidden_sleeps(headless_text)
        self.assertEqual(
            forbidden,
            [],
            msg=f"Znaleziono `sleep \\d+;` w szablonie headless: {forbidden}",
        )
        self.assertIn("Monitor", headless_text)

    def test_all_rendered_copies_have_no_forbidden_sleep(self) -> None:
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy_text = (KIT_ROOT / rel).read_text(encoding="utf-8")
                forbidden = find_forbidden_sleeps(copy_text)
                self.assertEqual(
                    forbidden,
                    [],
                    msg=f"Kopia {rel} zawiera niedozwolone `sleep \\d+;`: {forbidden}",
                )
                self.assertIn("Monitor", copy_text)


if __name__ == "__main__":
    unittest.main()
