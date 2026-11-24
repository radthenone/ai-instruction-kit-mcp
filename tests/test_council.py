"""Testy modułu `guides.council` (#545) — parsowanie bez PyYAML, resolver z #515, supp-target."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.council import (
    COUNCIL_SEATS,
    DEFAULT_ROUNDS,
    CouncilConfig,
    CouncilMember,
    load_council,
    parse_council,
)

TARGETS: dict[str, dict[str, dict]] = {
    "claude": {
        "light": {
            "providerInstanceId": "claudeAgent",
            "model": "claude-haiku-5-5",
            "options": [{"id": "effort", "value": "low"}],
        },
        "standard": {
            "providerInstanceId": "claudeAgent",
            "model": "claude-sonnet-5-5",
            "options": [{"id": "effort", "value": "medium"}],
        },
        "heavy": {
            "providerInstanceId": "claudeAgent",
            "model": "claude-opus-5-5",
            "options": [{"id": "effort", "value": "high"}],
        },
    },
    "opencode": {
        "heavy": {
            "providerInstanceId": "opencode",
            "model": "openrouter/openai/gpt-6-sol",
            "options": [{"id": "variant", "value": "high"}],
        },
    },
    "antigravity": {
        "heavy": {
            "providerInstanceId": "antigravity",
            "model": "gemini-3.1-pro-preview",
            "options": [{"id": "thinking_level", "value": "high"}],
        },
    },
}


class TestParseCouncil(unittest.TestCase):
    """Testy parsowania sekcji `council:`."""

    def test_missing_block_reports_missing_membership(self) -> None:
        """Brak `council:` w Profilu to zgłoszenie, nie domyślny dobór flagowców (#545)."""
        config = parse_council(None, targets=TARGETS)
        self.assertEqual(config.rounds, DEFAULT_ROUNDS)
        self.assertEqual(config.members, [])
        self.assertTrue(any("brak bloku `council:`" in n for n in config.notices))

    def test_invalid_section_type_reports_notice(self) -> None:
        """Sekcja niebędąca mapą generuje uwagę i zwraca pusty skład."""
        config = parse_council("delegate", targets=TARGETS)
        self.assertEqual(config.members, [])
        self.assertTrue(any("oczekiwano mapy" in n for n in config.notices))

    def test_resolving_refs_to_targets(self) -> None:
        """Członkowie jako refy `<klient>.<tier>` są rozwiązywani przez resolver z #515."""
        section = {
            "rounds": 2,
            "members": {
                "claude": {"target": "claude.heavy"},
                "opencode": {"target": "opencode.heavy"},
                "antigravity": {"target": "antigravity.heavy"},
            },
        }
        config = parse_council(section, targets=TARGETS)
        self.assertEqual(len(config.members), COUNCIL_SEATS)
        self.assertEqual(config.rounds, 2)
        claude = next(m for m in config.members if m.name == "claude")
        self.assertEqual(claude.target["providerInstanceId"], "claudeAgent")
        self.assertEqual(claude.target["model"], "claude-opus-5-5")
        self.assertEqual(claude.target["options"], [{"id": "effort", "value": "high"}])
        self.assertIsNone(claude.supp_target)
        self.assertEqual(config.notices, [])

    def test_target_model_and_options_overrides(self) -> None:
        """Nadpisania model / options w refie nadpisują wartości bazowe z targets."""
        section = {
            "members": {
                "claude": {
                    "target": {
                        "target": "claude.heavy",
                        "model": "claude-sonnet-5-5",
                        "options": [{"id": "effort", "value": "low"}],
                    }
                },
                "opencode": {"target": "opencode.heavy"},
                "antigravity": {"target": "antigravity.heavy"},
            }
        }
        config = parse_council(section, targets=TARGETS)
        claude = next(m for m in config.members if m.name == "claude")
        self.assertEqual(claude.target["model"], "claude-sonnet-5-5")
        self.assertEqual(claude.target["options"], [{"id": "effort", "value": "low"}])

    def test_supp_target_resolution_full_entry_and_ref(self) -> None:
        """`supp-target` jest poprawnie rozwiązywany jako pełny wpis lub jako ref."""
        section = {
            "members": {
                "claude": {
                    "target": "claude.heavy",
                    "supp-target": {
                        "providerInstanceId": "claudeAgent",
                        "model": "claude-opus-5-5",
                        "options": [{"id": "effort", "value": "medium"}],
                    },
                },
                "opencode": {
                    "target": "opencode.heavy",
                    "supp-target": "claude.standard",
                },
                "antigravity": {
                    "target": "antigravity.heavy",
                },
            }
        }
        config = parse_council(section, targets=TARGETS)
        claude = next(m for m in config.members if m.name == "claude")
        self.assertIsNotNone(claude.supp_target)
        assert claude.supp_target is not None
        self.assertEqual(claude.supp_target["options"], [{"id": "effort", "value": "medium"}])

        opencode = next(m for m in config.members if m.name == "opencode")
        self.assertIsNotNone(opencode.supp_target)
        assert opencode.supp_target is not None
        self.assertEqual(opencode.supp_target["model"], "claude-sonnet-5-5")

        antigravity = next(m for m in config.members if m.name == "antigravity")
        self.assertIsNone(antigravity.supp_target)

    def test_unknown_ref_reports_notice_without_guessing(self) -> None:
        """Nieznany ref w target generuje uwagę; brak supp-target oznacza odpadnięcie członka."""
        section = {
            "members": {
                "claude": {"target": "claude.ultra"},
                "opencode": {"target": "opencode.heavy"},
            }
        }
        config = parse_council(section, targets=TARGETS)
        self.assertEqual(len(config.members), 1)
        self.assertTrue(any("claude" in n and "nierozwiązywalny `target`" in n for n in config.notices))
        self.assertTrue(any("1 członków, rada wymaga 3" in n for n in config.notices))

    def test_unknown_ref_with_valid_supp_target_rescues_member(self) -> None:
        """Nieznany ref w target, ale poprawny supp-target pozwala członkowi uczestniczyć."""
        section = {
            "members": {
                "claude": {
                    "target": "claude.ultra",
                    "supp-target": "claude.heavy",
                },
                "opencode": {"target": "opencode.heavy"},
                "antigravity": {"target": "antigravity.heavy"},
            }
        }
        config = parse_council(section, targets=TARGETS)
        self.assertEqual(len(config.members), 3)
        claude = next(m for m in config.members if m.name == "claude")
        self.assertEqual(claude.target["model"], "claude-opus-5-5")
        self.assertTrue(any("claude" in n and "nierozwiązywalny `target`" in n for n in config.notices))

    def test_membership_count_other_than_three_reports_notice(self) -> None:
        """Rada wymaga 3 członków; 2 członków generuje uwagę bez błędu twardego."""
        section = {
            "members": {
                "claude": {"target": "claude.heavy"},
                "opencode": {"target": "opencode.heavy"},
            }
        }
        config = parse_council(section, targets=TARGETS)
        self.assertEqual(len(config.members), 2)
        self.assertTrue(any("2 członków, rada wymaga 3" in n for n in config.notices))

    def test_rounds_count_default_and_custom(self) -> None:
        """Liczba rund czytana z `rounds:`, domyślnie 2."""
        self.assertEqual(parse_council({}, targets=TARGETS).rounds, DEFAULT_ROUNDS)
        self.assertEqual(parse_council({"rounds": 4}, targets=TARGETS).rounds, 4)
        config_bad = parse_council({"rounds": -1}, targets=TARGETS)
        self.assertEqual(config_bad.rounds, DEFAULT_ROUNDS)
        self.assertTrue(any("`rounds` musi być > 0" in n for n in config_bad.notices))

    def test_to_dict_includes_target_and_supp_target(self) -> None:
        """Metoda to_dict członka formatuje klucze `name`, `target` oraz `supp-target`."""
        member = CouncilMember(
            name="claude",
            target={"providerInstanceId": "claudeAgent", "model": "claude-opus-5-5", "options": []},
            supp_target={"providerInstanceId": "claudeAgent", "model": "claude-sonnet-5-5", "options": []},
        )
        d = member.to_dict()
        self.assertEqual(d["name"], "claude")
        self.assertIn("target", d)
        self.assertIn("supp-target", d)


class TestLoadCouncil(unittest.TestCase):
    """Testy wczytywania `council:` z pliku Profilu (bez PyYAML)."""

    def test_missing_file_reports_no_block(self) -> None:
        """Brak pliku Profilu zwraca bezpieczny stan z uwagą."""
        with tempfile.TemporaryDirectory() as tmp:
            config = load_council(Path(tmp) / "project.profile.yaml")
        self.assertEqual(config.rounds, DEFAULT_ROUNDS)
        self.assertEqual(config.members, [])
        self.assertTrue(any("brak bloku `council:`" in n for n in config.notices))

    def test_loads_profile_with_targets_and_council_full_syntax(self) -> None:
        """Wczytanie Profilu z `targets:` i `council:` z inline dict `supp-target`."""
        profile_content = """
name: demo
language: pl

targets:
  claude:
    standard:
      providerInstanceId: claudeAgent
      model: claude-sonnet-5-5
    heavy:
      providerInstanceId: claudeAgent
      model: claude-opus-5-5
      options: [{ id: effort, value: high }]
  opencode:
    standard:
      providerInstanceId: opencode
      model: openrouter/openai/gpt-6-sol
    heavy:
      providerInstanceId: opencode
      model: openrouter/openai/gpt-6-sol
      options: [{ id: variant, value: high }]
  antigravity:
    standard:
      providerInstanceId: antigravity
      model: gemini-3.1-pro-preview
    heavy:
      providerInstanceId: antigravity
      model: gemini-3.1-pro-preview
      options: [{ id: thinking_level, value: high }]

council:
  rounds: 3
  members:
    claude:
      target: claude.heavy
      supp-target: { providerInstanceId: claudeAgent, model: claude-opus-5-5, options: [{ id: effort, value: medium }] }
    opencode:
      target: opencode.heavy
      supp-target: { providerInstanceId: opencode, model: gpt-5, options: [{ id: variant, value: high }] }
    antigravity:
      target: antigravity.heavy
      supp-target: { providerInstanceId: antigravity, model: gemini-3, options: [{ id: thinking_level, value: high }] }
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "project.profile.yaml"
            p.write_text(profile_content, encoding="utf-8")
            config = load_council(p)

        self.assertEqual(config.rounds, 3)
        self.assertEqual(len(config.members), 3)
        self.assertEqual(config.notices, [])
        claude = next(m for m in config.members if m.name == "claude")
        self.assertEqual(claude.target["model"], "claude-opus-5-5")
        self.assertIsNotNone(claude.supp_target)
        assert claude.supp_target is not None
        self.assertEqual(claude.supp_target["options"], [{"id": "effort", "value": "medium"}])


if __name__ == "__main__":
    unittest.main()
