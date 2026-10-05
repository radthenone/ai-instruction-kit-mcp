"""
Issue i PR z kita dostają etykietę i tablicę dopasowane do repo (#91).

`/git-start` i `/git-end` wołały `gh issue create` / `gh pr create` bez sprawdzenia
etykiet i GitHub Projects, więc issue lądowały bez `type: *` i poza tablicą repo.
Kroki są w samych agentach, nie w `git-branch-pr.mdc` — ta reguła trafia tylko do Cursora.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"
STEPS = ("gh label list", "gh project list")


class TestLabelProjectOnCreate(unittest.TestCase):
    def test_agents_define_both_steps(self) -> None:
        for name in ("git-start.md", "git-end.md"):
            text = (AGENTS / name).read_text(encoding="utf-8")
            for step in (*STEPS, "gh auth refresh -s project"):
                self.assertIn(step, text, f"{name}: brak `{step}`")

    def test_create_uses_matched_flags(self) -> None:
        for name, create in (("git-start.md", "gh issue create --title \"<title EN>\""), ("git-end.md", "gh pr create --base <target>")):
            text = (AGENTS / name).read_text(encoding="utf-8")
            call = text[text.index(create) :].split("\n\n", 1)[0]
            self.assertIn("--label", call, f"{name}: `{create}` bez --label")
            self.assertIn("--project", call, f"{name}: `{create}` bez --project")


if __name__ == "__main__":
    unittest.main()
