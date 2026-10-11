"""Model tiers agentów (#168): `model-tier:` w template, `models:`/`agents:` w Profilu."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from model_tiers import (  # noqa: E402
    TIERS,
    ProfileError,
    apply_models,
    parse_profile,
    sync_agents,
    template_tiers,
)

AGENTS_DIR = KIT_ROOT / "templates" / "shared" / "agents"
TEMPLATE = {"git-start": "light", "cleanup": "light", "create-task": "standard", "night-run": "heavy"}


class TestTemplates(unittest.TestCase):
    def test_every_agent_template_has_valid_model_tier(self) -> None:
        tiers = template_tiers(AGENTS_DIR)
        names = {path.stem for path in AGENTS_DIR.glob("*.md")}
        self.assertEqual(set(tiers), names)
        for name, tier in tiers.items():
            with self.subTest(agent=name):
                self.assertIn(tier, TIERS)


class TestParseProfile(unittest.TestCase):
    def test_reads_models_and_agents_blocks(self) -> None:
        text = (
            "name: app\n"
            "models:\n"
            "  claude:\n"
            "    light: haiku\n"
            "  opencode:\n"
            "    light: ollama/llama3:8b  # lokalnie\n"
            "agents:\n"
            "  light: git-start, cleanup\n"
            "  heavy: \"night-run\"\n"
            "codegen: orval\n"
        )
        models, agents = parse_profile(text)
        self.assertEqual(models, {"claude": {"light": "haiku"}, "opencode": {"light": "ollama/llama3:8b"}})
        self.assertEqual(agents, {"light": ["git-start", "cleanup"], "heavy": ["night-run"]})

    def test_missing_blocks_parse_as_empty(self) -> None:
        self.assertEqual(parse_profile("name: app\n"), ({}, None))

    def test_unknown_tier_in_agents_is_error_with_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  medium: git-start\n")
        message = str(ctx.exception)
        self.assertIn("medium", message)
        self.assertIn("light, standard, heavy", message)

    def test_unknown_tier_in_models_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("models:\n  claude:\n    fast: haiku\n")
        self.assertIn("models.claude.fast", str(ctx.exception))

    def test_agent_in_two_tiers_is_error_with_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light: git-start\n  heavy: git-start\n")
        message = str(ctx.exception)
        self.assertIn("git-start", message)
        self.assertIn("light", message)
        self.assertIn("heavy", message)

    def test_empty_model_value_is_error_not_new_client(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("models:\n  claude:\n    light:\n    heavy: opus\n")
        self.assertIn("models.claude.light", str(ctx.exception))

    def test_tier_at_client_indent_is_error(self) -> None:
        with self.assertRaises(ProfileError):
            parse_profile("models:\n  claude:\n  light: haiku\n")

    def test_block_list_in_agents_is_error_with_supported_form(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light:\n    - cleanup\n")
        self.assertIn("po przecinku", str(ctx.exception))

    def test_flow_map_is_error_with_supported_form(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("models: {claude: {light: haiku}}\n")
        self.assertIn("blokiem", str(ctx.exception))

    def test_comment_at_column_zero_inside_block_is_skipped(self) -> None:
        _, agents = parse_profile("agents:\n# moje\n  light: cleanup\nx: 1\n")
        self.assertEqual(agents, {"light": ["cleanup"]})


class TestSyncAgents(unittest.TestCase):
    def test_creates_block_from_template_when_missing(self) -> None:
        text, report = sync_agents("name: app\n# komentarz\n", TEMPLATE)
        self.assertTrue(text.startswith("name: app\n# komentarz\n"))
        _, agents = parse_profile(text)
        self.assertEqual(
            agents,
            {"light": ["cleanup", "git-start"], "standard": ["create-task"], "heavy": ["night-run"]},
        )
        self.assertEqual(len(report), 4)

    def test_keeps_profile_assignment_over_template(self) -> None:
        profile = "agents:\n  heavy: git-start\n  light: cleanup\n  standard: create-task\nx: 1\n"
        text, report = sync_agents(profile, TEMPLATE)
        agents = parse_profile(text)[1] or {}
        self.assertEqual(agents["heavy"], ["git-start", "night-run"])
        self.assertEqual(agents["light"], ["cleanup"])
        self.assertTrue(text.endswith("x: 1\n"))
        self.assertEqual(report, ["+ agents.heavy: night-run"])

    def test_removes_names_unknown_to_kit_and_reports(self) -> None:
        profile = "agents:\n  light: git-start,cleanup,ghost\n  standard: create-task\n  heavy: night-run\n"
        text, report = sync_agents(profile, TEMPLATE)
        agents = parse_profile(text)[1] or {}
        self.assertEqual(agents["light"], ["git-start", "cleanup"])
        self.assertEqual(report, ["- agents.light: ghost (nie ma takiego agenta w kicie)"])

    def test_in_sync_profile_is_untouched(self) -> None:
        profile = "agents:\n  light: git-start, cleanup # moje\n  standard: create-task\n  heavy: night-run\n"
        self.assertEqual(sync_agents(profile, TEMPLATE), (profile, []))

    def test_rewrite_keeps_crlf_line_endings(self) -> None:
        text, _ = sync_agents("a: 1\r\nagents:\r\n  light: ghost\r\n", TEMPLATE)
        self.assertNotIn("\n", text.replace("\r\n", ""))

    def test_rewrite_after_inner_comment_leaves_no_orphan_lines(self) -> None:
        text, _ = sync_agents("agents:\n# c\n  light: cleanup\nx: 1\n", TEMPLATE)
        self.assertEqual(text.count("light:"), 1)
        self.assertTrue(text.endswith("x: 1\n"))


class TestApplyModels(unittest.TestCase):
    def _agent(self, root: Path, name: str) -> Path:
        path = root / f"{name}.md"
        path.write_text(f"---\nname: {name}\ndescription: d\n---\n\nbody\n", encoding="utf-8")
        return path

    def test_inserts_model_for_mapped_tier(self) -> None:
        profile = "models:\n  claude:\n    light: haiku\nagents:\n  light: git-start\n  heavy: night-run\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start, night = self._agent(root, "git-start"), self._agent(root, "night-run")
            before = night.read_text(encoding="utf-8")
            apply_models("claude", profile, root)
            self.assertEqual(
                start.read_text(encoding="utf-8"),
                "---\nname: git-start\ndescription: d\nmodel: haiku\n---\n\nbody\n",
            )
            self.assertEqual(night.read_text(encoding="utf-8"), before)

    def test_other_client_mapping_is_ignored(self) -> None:
        profile = "models:\n  opencode:\n    light: anthropic/claude-haiku-5-5\nagents:\n  light: git-start\n"
        with tempfile.TemporaryDirectory() as tmp:
            start = self._agent(Path(tmp), "git-start")
            before = start.read_text(encoding="utf-8")
            apply_models("claude", profile, Path(tmp))
            self.assertEqual(start.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
