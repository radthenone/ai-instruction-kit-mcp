import unittest
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1] / "templates" / "shared" / "agents"
FILES = ["git-start.md", "git-check.md", "git-end.md", "night-run.md"]


def base_block(text):
    start = text.index("Baza (ta sama reguła")
    return text[start : text.index("```\n", text.index("```bash", start) + 7)]


class BaseBranchRuleTest(unittest.TestCase):
    def test_old_dev_if_exists_rule_is_gone(self):
        for name in FILES:
            text = (AGENTS / name).read_text(encoding="utf-8")
            for old in ("`dev` jeśli istnieje", "`dev` jeśli na remote", "`dev` jeśli `origin/dev`"):
                self.assertNotIn(old, text, name)

    def test_same_block_everywhere(self):
        blocks = {n: base_block((AGENTS / n).read_text(encoding="utf-8")) for n in FILES}
        first = blocks[FILES[0]]
        for name, block in blocks.items():
            self.assertEqual(block, first, name)
        for needle in ("^base:", "merge-base --is-ancestor origin/dev", "baseRefName"):
            self.assertIn(needle, first)


if __name__ == "__main__":
    unittest.main()
