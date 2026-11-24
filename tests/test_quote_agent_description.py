"""Kopie agentów Claude: `description` cytowany, więc YAML czyta cały opis (#547)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from quote_agent_description import quote_description  # noqa: E402

AGENT = "---\nname: git-end\ndescription: {value}\nmodel: claude-haiku-5-5\n---\n\nTreść agenta.\n"


def _frontmatter(text: str) -> dict:
    return yaml.safe_load(text.split("---\n")[1])


class TestQuoteDescription(unittest.TestCase):
    def test_roundtrip_keeps_hash_colon_and_quotes(self) -> None:
        value = 'Push (Closes #N). Use when: /kit-ai:git-end, "tryb" i a: b.'
        text = quote_description(AGENT.format(value=value))
        self.assertEqual(_frontmatter(text)["description"], value)
        self.assertIn("model: claude-haiku-5-5\n", text)
        self.assertTrue(text.endswith("---\n\nTreść agenta.\n"))

    def test_already_quoted_value_is_kept(self) -> None:
        text = quote_description(AGENT.format(value='"Push (Closes #N)."'))
        self.assertEqual(_frontmatter(text)["description"], "Push (Closes #N).")


if __name__ == "__main__":
    unittest.main()
