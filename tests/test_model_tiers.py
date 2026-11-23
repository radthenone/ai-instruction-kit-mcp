"""Model tiers agentów (#168, #515): `model-tier:` w template, `targets:` i `agents:` w Profilu."""

from __future__ import annotations

import contextlib
import io
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
    main,
    parse_profile,
    resolve_target,
    sync_agents,
    takeover_alias,
    template_tiers,
)

AGENTS_DIR = KIT_ROOT / "templates" / "shared" / "agents"
TEMPLATE = {"git-start": "light", "cleanup": "light", "create-task": "standard", "night-run": "heavy"}

FOUR_CLIENTS = """\
targets:
  claude:
    light:
      providerInstanceId: claudeAgent
      model: claude-haiku-5-5
      options: [{ id: effort, value: low }]
    standard:
      providerInstanceId: claudeAgent
      model: claude-sonnet-5-5
      options: [{ id: effort, value: medium }]
    heavy:
      providerInstanceId: claudeAgent
      model: claude-opus-5-5
    takeover:
      providerInstanceId: claudeAgent
      model: claude-haiku-5-5
      options: [{ id: effort, value: low }]
  codex:
    light:
      providerInstanceId: codex
      model: gpt-5.5-mini
      options: [{ id: reasoningEffort, value: low }]
    standard:
      providerInstanceId: codex
      model: gpt-5.5
      options: [{ id: reasoningEffort, value: medium }]
    heavy:
      providerInstanceId: codex
      model: gpt-5.5
      options: [{ id: reasoningEffort, value: high }]
    takeover:
      providerInstanceId: codex
      model: gpt-5.5-mini
  antigravity:
    light:
      providerInstanceId: antigravity
      model: gemini-3.8-flash
      options: [{ id: thought_level, value: low }]
    standard:
      providerInstanceId: antigravity
      model: gemini-3.8-flash
      options: [{ id: thought_level, value: high }]
    heavy:
      providerInstanceId: antigravity
      model: gemini-3.8-flash
    takeover:
      providerInstanceId: antigravity
      model: gemini-3.8-flash
  opencode:
    light:
      providerInstanceId: opencode
      model: opencode/deepseek-v4.1-flash-free
    standard:
      providerInstanceId: opencode
      model: opencode/deepseek-v4.1-flash-free
      options: [{ id: variant, value: high }]
    heavy:
      providerInstanceId: opencode
      model: opencode/deepseek-v4.1-flash-free
    takeover:
      providerInstanceId: opencode
      model: opencode/deepseek-v4.1-flash-free
"""


class TestTemplates(unittest.TestCase):
    def test_every_agent_template_has_valid_model_tier(self) -> None:
        tiers = template_tiers(AGENTS_DIR)
        names = {path.stem for path in AGENTS_DIR.glob("*.md")}
        self.assertEqual(set(tiers), names)
        for name, tier in tiers.items():
            with self.subTest(agent=name):
                self.assertIn(tier, TIERS)

    def test_profile_template_parses_without_active_targets(self) -> None:
        """Przykład `targets:` w szablonie Profilu jest zakomentowany — parser nie widzi go jako wpisu."""
        text = (KIT_ROOT / "templates" / "project.profile.yaml").read_text(encoding="utf-8")
        self.assertEqual(parse_profile(text), ({}, None))


class TestDefaultModelTiers(unittest.TestCase):
    """Domyślne model tiers z templates (#516): `review-*` heavy, `night-run` standard."""

    def test_sync_on_empty_profile_writes_default_tiers(self) -> None:
        """Sync na pustym Profilu daje heavy dla `review-*` i standard dla `night-run`."""
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "project.profile.yaml"
            profile.write_text("", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["model_tiers.py", "sync", str(profile), str(AGENTS_DIR)])
            agents = parse_profile(profile.read_text(encoding="utf-8"))[1] or {}
        self.assertEqual(code, 0)
        heavy = set(agents.get("heavy", []))
        self.assertEqual(
            heavy,
            {
                "review-architecture",
                "review-backend",
                "review-bugbot",
                "review-edge",
                "review-frontend",
                "review-security",
                "review-tests",
                "review-ui",
            },
        )
        self.assertLessEqual({path.stem for path in AGENTS_DIR.glob("review-*.md")}, heavy)
        self.assertIn("night-run", agents.get("standard", []))


class TestParseTargets(unittest.TestCase):
    def test_reads_four_clients_with_four_tiers(self) -> None:
        targets, _ = parse_profile(FOUR_CLIENTS)
        self.assertEqual(set(targets), {"claude", "codex", "antigravity", "opencode"})
        for client in targets:
            with self.subTest(client=client):
                self.assertEqual(set(targets[client]), {"light", "standard", "heavy", "takeover"})

    def test_codex_entry_keeps_provider_model_and_options(self) -> None:
        targets, _ = parse_profile(FOUR_CLIENTS)
        self.assertEqual(
            targets["codex"]["standard"],
            {
                "providerInstanceId": "codex",
                "model": "gpt-5.5",
                "options": [{"id": "reasoningEffort", "value": "medium"}],
            },
        )

    def test_entry_without_options_has_empty_options_list(self) -> None:
        targets, _ = parse_profile(FOUR_CLIENTS)
        self.assertEqual(targets["claude"]["heavy"]["options"], [])

    def test_takeover_without_entry_copies_standard_of_same_client(self) -> None:
        text = "targets:\n  codex:\n    standard:\n      providerInstanceId: codex\n      model: gpt-5.5\n"
        targets, _ = parse_profile(text)
        self.assertEqual(targets["codex"]["takeover"], targets["codex"]["standard"])

    def test_takeover_entry_keeps_its_own_full_shape(self) -> None:
        text = (
            "targets:\n  codex:\n    standard:\n      providerInstanceId: codex\n      model: gpt-5.5\n"
            "    takeover:\n      providerInstanceId: codex\n      model: gpt-5.5-mini\n"
            "      options: [{ id: reasoningEffort, value: low }]\n"
        )
        targets, _ = parse_profile(text)
        self.assertEqual(
            targets["codex"]["takeover"],
            {
                "providerInstanceId": "codex",
                "model": "gpt-5.5-mini",
                "options": [{"id": "reasoningEffort", "value": "low"}],
            },
        )

    def test_quoted_option_id_and_value_are_read(self) -> None:
        targets, _ = parse_profile(
            'targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n'
            '      options: [{ id: "effort", value: "low" }]\n'
        )
        self.assertEqual(targets["claude"]["light"]["options"], [{"id": "effort", "value": "low"}])

    def test_duplicate_client_is_error(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "  codex:\n    light:\n      providerInstanceId: codex\n"
            "  claude:\n    heavy:\n      providerInstanceId: claudeAgent\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("zdublowany", str(ctx.exception))
        self.assertIn("targets.claude", str(ctx.exception))

    def test_duplicate_tier_is_error(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "    light:\n      providerInstanceId: claudeAgent\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("targets.claude.light", str(ctx.exception))

    def test_duplicate_field_is_error(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "      model: claude-haiku-5-5\n      model: claude-sonnet-5-5\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("targets.claude.light.model", str(ctx.exception))

    def test_duplicate_option_id_is_error(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "      options: [{ id: effort, value: low }, { id: effort, value: high }]\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("effort", str(ctx.exception))

    def test_empty_quoted_provider_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude:\n    light:\n      providerInstanceId: ''\n")
        self.assertIn("providerInstanceId", str(ctx.exception))

    def test_empty_quoted_model_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(
                'targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n      model: ""\n'
            )
        self.assertIn("bez modelu", str(ctx.exception))

    def test_tab_indentation_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n\tclaude:\n\t\tlight:\n\t\t\tproviderInstanceId: claudeAgent\n")
        self.assertIn("tabulator", str(ctx.exception))

    def test_two_top_level_targets_blocks_are_error(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "name: x\n"
            "targets:\n  codex:\n    light:\n      providerInstanceId: codex\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("targets:", str(ctx.exception))
        self.assertIn("zdublowany", str(ctx.exception))

    def test_missing_blocks_parse_as_empty(self) -> None:
        self.assertEqual(parse_profile("name: app\n"), ({}, None))

    def test_unknown_client_is_error_with_allowed_list(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  gemini:\n    light:\n      providerInstanceId: x\n")
        self.assertIn("targets.gemini", str(ctx.exception))
        self.assertIn("claude, codex, antigravity, opencode", str(ctx.exception))

    def test_unknown_tier_is_error_with_allowed_list(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude:\n    fast:\n      providerInstanceId: claudeAgent\n")
        self.assertIn("targets.claude.fast", str(ctx.exception))
        self.assertIn("light, standard, heavy, takeover", str(ctx.exception))

    def test_entry_without_provider_instance_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude:\n    light:\n      model: claude-haiku-5-5\n")
        self.assertIn("providerInstanceId", str(ctx.exception))

    def test_empty_model_is_error_not_silent(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n      model:\n")
        self.assertIn("targets.claude.light.model", str(ctx.exception))
        self.assertIn("bez modelu", str(ctx.exception))

    def test_unknown_field_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(
                "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n      temperature: 0.2\n"
            )
        self.assertIn("temperature", str(ctx.exception))

    def test_options_must_be_inline_list(self) -> None:
        text = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "      options:\n        - { id: effort, value: low }\n"
        )
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(text)
        self.assertIn("inline", str(ctx.exception))

    def test_empty_options_list_is_empty(self) -> None:
        targets, _ = parse_profile(
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n      options: []\n"
        )
        self.assertEqual(targets["claude"]["light"]["options"], [])

    def test_inline_targets_block_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets: {claude: {light: haiku}}\n")
        self.assertIn("blokiem", str(ctx.exception))

    def test_tier_with_plain_value_instead_of_fields_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude:\n    light: haiku\n")
        self.assertIn("targets.claude.light", str(ctx.exception))

    def test_client_with_plain_value_instead_of_tiers_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("targets:\n  claude: haiku\n")
        self.assertIn("targets.claude", str(ctx.exception))


class TestRetiredKeys(unittest.TestCase):
    """Stare klucze `models:` i `t3.targets` są twardym błędem z instrukcją migracji (ADR-0018)."""

    def test_models_key_is_hard_error_with_migration_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("models:\n  claude:\n    light: haiku\n")
        self.assertIn("models:", str(ctx.exception))
        self.assertIn("targets:", str(ctx.exception))

    def test_t3_key_is_hard_error_with_migration_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("t3:\n  targets:\n    claude:\n      light: haiku\n")
        self.assertIn("t3:", str(ctx.exception))
        self.assertIn("targets:", str(ctx.exception))

    def test_sync_stops_on_models_key_and_keeps_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "project.profile.yaml"
            original = "models:\n  claude:\n    light: haiku\n"
            profile.write_text(original, encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = main(["model_tiers.py", "sync", str(profile), str(AGENTS_DIR)])
            self.assertEqual(profile.read_text(encoding="utf-8"), original)
        self.assertEqual(code, 1)
        self.assertIn("models:", err.getvalue())


class TestParseAgents(unittest.TestCase):
    def test_unknown_tier_in_agents_is_error_with_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  medium: git-start\n")
        message = str(ctx.exception)
        self.assertIn("medium", message)
        self.assertIn("light, standard, heavy", message)

    def test_agent_in_two_tiers_is_error_with_hint(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light: git-start\n  heavy: git-start\n")
        message = str(ctx.exception)
        self.assertIn("git-start", message)
        self.assertIn("light", message)
        self.assertIn("heavy", message)

    def test_block_list_in_agents_is_error_with_supported_form(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light:\n    - cleanup\n")
        self.assertIn("po przecinku", str(ctx.exception))

    def test_two_top_level_agents_blocks_are_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light: git-start\nx: 1\nagents:\n  light: cleanup\n")
        self.assertIn("agents:", str(ctx.exception))
        self.assertIn("zdublowany", str(ctx.exception))

    def test_duplicate_agents_tier_is_error(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile("agents:\n  light: git-start\n  light: cleanup\n")
        self.assertIn("agents.light", str(ctx.exception))

    def test_comment_at_column_zero_inside_block_is_skipped(self) -> None:
        _, agents = parse_profile("agents:\n# moje\n  light: cleanup\nx: 1\n")
        self.assertEqual(agents, {"light": ["cleanup"]})


class TestResolveTarget(unittest.TestCase):
    TARGETS = {
        "claude": {
            "light": {
                "providerInstanceId": "claudeAgent",
                "model": "claude-haiku-5-5",
                "options": [{"id": "effort", "value": "low"}],
            }
        }
    }

    def test_ref_returns_target_object(self) -> None:
        self.assertEqual(resolve_target({"target": "claude.light"}, self.TARGETS), self.TARGETS["claude"]["light"])

    def test_ref_with_model_override_keeps_provider_and_options(self) -> None:
        resolved = resolve_target({"target": "claude.light", "model": "claude-sonnet-5-5"}, self.TARGETS)
        self.assertEqual(resolved["model"], "claude-sonnet-5-5")
        self.assertEqual(resolved["providerInstanceId"], "claudeAgent")
        self.assertEqual(resolved["options"], [{"id": "effort", "value": "low"}])

    def test_ref_with_options_override_keeps_model(self) -> None:
        resolved = resolve_target({"target": "claude.light", "options": [{"id": "effort", "value": "max"}]}, self.TARGETS)
        self.assertEqual(resolved["options"], [{"id": "effort", "value": "max"}])
        self.assertEqual(resolved["model"], "claude-haiku-5-5")

    def test_override_does_not_change_targets(self) -> None:
        resolve_target({"target": "claude.light", "model": "claude-sonnet-5-5"}, self.TARGETS)
        self.assertEqual(self.TARGETS["claude"]["light"]["model"], "claude-haiku-5-5")

    def test_full_entry_is_used_as_is(self) -> None:
        entry = {"providerInstanceId": "codex", "model": "gpt-5.5", "options": []}
        self.assertEqual(resolve_target(entry, {}), entry)

    def test_unknown_ref_is_error_naming_the_ref(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            resolve_target({"target": "claude.ultra"}, self.TARGETS)
        self.assertIn("claude.ultra", str(ctx.exception))

    def test_entry_without_ref_or_provider_is_error(self) -> None:
        with self.assertRaises(ProfileError):
            resolve_target({"model": "claude-haiku-5-5"}, self.TARGETS)


class TestTakeoverAlias(unittest.TestCase):
    def test_alias_is_derived_from_claude_model_id(self) -> None:
        cases = {
            "claude-haiku-5-5": "haiku",
            "claude-sonnet-5-5": "sonnet",
            "claude-opus-5-5": "opus",
            "claude-fable-5-2": "fable",
        }
        for model, alias in cases.items():
            with self.subTest(model=model):
                self.assertEqual(takeover_alias(model), alias)

    def test_alias_passes_through(self) -> None:
        self.assertEqual(takeover_alias("haiku"), "haiku")

    def test_missing_model_means_session_model(self) -> None:
        self.assertIsNone(takeover_alias(None))

    def test_unknown_model_id_means_session_model(self) -> None:
        for model in ("gpt-5.5", "ollama/llama3:8b", "claude-unknown-family"):
            with self.subTest(model=model):
                self.assertIsNone(takeover_alias(model))


class TestApplyModels(unittest.TestCase):
    def _agent(self, root: Path, name: str) -> Path:
        path = root / f"{name}.md"
        path.write_text(f"---\nname: {name}\ndescription: d\n---\n\nbody\n", encoding="utf-8")
        return path

    def test_claude_apply_writes_model_and_effort_for_mapped_tier(self) -> None:
        profile = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "      model: claude-haiku-5-5\n      options: [{ id: effort, value: low }]\n"
            "agents:\n  light: git-start\n  heavy: night-run\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start, night = self._agent(root, "git-start"), self._agent(root, "night-run")
            before = night.read_text(encoding="utf-8")
            apply_models("claude", profile, root)
            self.assertEqual(
                start.read_text(encoding="utf-8"),
                "---\nname: git-start\ndescription: d\nmodel: claude-haiku-5-5\neffort: low\n---\n\nbody\n",
            )
            self.assertEqual(night.read_text(encoding="utf-8"), before)

    def test_claude_apply_without_effort_option_writes_only_model(self) -> None:
        profile = (
            "targets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
            "      model: claude-haiku-5-5\nagents:\n  light: git-start\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            start = self._agent(Path(tmp), "git-start")
            apply_models("claude", profile, Path(tmp))
            self.assertEqual(
                start.read_text(encoding="utf-8"),
                "---\nname: git-start\ndescription: d\nmodel: claude-haiku-5-5\n---\n\nbody\n",
            )

    def test_opencode_targets_write_nothing_until_command_path_moves(self) -> None:
        """OpenCode: `model:` dopiero po #527 (nowa ścieżka `.opencode/commands/kit-ai/`)."""
        profile = (
            "targets:\n  opencode:\n    light:\n      providerInstanceId: opencode\n"
            "      model: anthropic/claude-haiku-5-5\nagents:\n  light: git-start\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            start = self._agent(Path(tmp), "git-start")
            before = start.read_text(encoding="utf-8")
            apply_models("opencode", profile, Path(tmp))
            self.assertEqual(start.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
