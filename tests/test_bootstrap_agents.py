"""Testy integracyjne ``scripts/bootstrap-project.sh`` dla agentów, tierów, model-tiers i ``/headless``."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from test_bootstrap import KIT_ROOT, _BootstrapTestCase

from guides.bootstrap import BootstrapError, run_bootstrap

BACKEND_AGENTS = {"review-backend", "teacher-backend", "subagent-backend"}
CLIENT_AGENTS = {"review-frontend", "teacher-frontend", "subagent-frontend", "review-ui"}


class TestTierAgents(_BootstrapTestCase, unittest.TestCase):
    """Agenci Stacku tylko dla wybranych Tierów; treść bez Stacka na sztywno."""

    def _bootstrap(self, workspace: Path, backend: str, web: str, mobile: str) -> set[str]:
        (workspace / ".ai").mkdir(parents=True, exist_ok=True)
        (workspace / ".ai" / "project.profile.yaml").write_text(
            f"name: t\nbackend: {backend}\nweb: {web}\nmobile: {mobile}\n", encoding="utf-8"
        )
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex,opencode")
        return {p.stem for p in (workspace / ".claude" / "agents").glob("*.md")}

    def test_agents_follow_tiers(self) -> None:
        cases = {
            ("none", "none", "none"): set(),
            ("fastapi", "none", "none"): BACKEND_AGENTS,
            ("none", "react", "none"): CLIENT_AGENTS,
            ("none", "none", "expo"): CLIENT_AGENTS,
            ("django", "react", "none"): BACKEND_AGENTS | CLIENT_AGENTS,
        }
        for tiers, expected in cases.items():
            with self.subTest(tiers=tiers), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp) / "app"
                installed = self._bootstrap(workspace, *tiers)
                self.assertEqual(installed & (BACKEND_AGENTS | CLIENT_AGENTS), expected)
                self.assertIn("review-architecture", installed)
                self.assertIn("teacher-architecture", installed)
                codex = {p.name for p in (workspace / ".codex" / "skills").iterdir()}
                self.assertEqual(codex & (BACKEND_AGENTS | CLIENT_AGENTS), expected)
                bugbot = (workspace / "BUGBOT.md").read_text(encoding="utf-8")
                self.assertEqual("## Backend" in bugbot, "fastapi" in tiers or "django" in tiers)
                self.assertNotIn("<!-- tier:", bugbot)

    def test_tier_set_to_none_removes_its_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self.assertEqual(self._bootstrap(workspace, "none", "none", "none") & BACKEND_AGENTS, set())
            self.assertNotIn("## Backend", (workspace / "BUGBOT.md").read_text(encoding="utf-8"))
            self.assertEqual(self._bootstrap(workspace, "django", "none", "none") & BACKEND_AGENTS, BACKEND_AGENTS)
            # Nietknięty BUGBOT.md podąża za Tierami (install zawsze zaczyna od `none`).
            self.assertIn("## Backend", (workspace / "BUGBOT.md").read_text(encoding="utf-8"))
            self.assertEqual(self._bootstrap(workspace, "none", "none", "none") & BACKEND_AGENTS, set())
            for rel in (
                ".claude/skills/kit-ai/skills/review-backend/SKILL.md",
                ".codex/skills/review-backend",
                ".opencode/commands/kit-ai/review-backend.md",
            ):
                self.assertFalse((workspace / rel).exists(), rel)

    def test_installed_descriptions_name_no_stack(self) -> None:
        """Opis agenta nie zakłada Django/Expo — Stack przychodzi z Bundle'a."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._bootstrap(workspace, "fastapi", "react", "expo")
            for agent in (workspace / ".claude" / "agents").glob("*.md"):
                text = agent.read_text(encoding="utf-8")
                description = next(l for l in text.splitlines() if l.startswith("description:"))
                with self.subTest(agent=agent.name):
                    self.assertNotRegex(description, "Django|DRF|Expo")
                    self.assertNotIn("\ntier:", text)


class TestModelTiers(_BootstrapTestCase, unittest.TestCase):
    """`targets:` / `agents:` w Profilu → `model:` i `effort:` u Claude (#168, #515)."""

    def _install(self, workspace: Path, profile_extra: str = "") -> None:
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")
        if profile_extra:
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(profile.read_text(encoding="utf-8") + profile_extra, encoding="utf-8")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")

    def test_without_models_agents_have_no_model_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace)
            profile = (workspace / ".ai" / "project.profile.yaml").read_text(encoding="utf-8")
            self.assertIn("\nagents:\n  light: ", profile)
            for rel in (".claude/agents/git-start.md", ".opencode/commands/kit-ai/git-start.md"):
                text = (workspace / rel).read_text(encoding="utf-8")
                self.assertNotIn("model:", text.split("---")[1], rel)
                self.assertNotIn("model-tier", text, rel)

    def test_targets_render_model_and_effort_for_claude_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(
                workspace,
                "\ntargets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n"
                "      model: claude-haiku-5-5\n      options: [{ id: effort, value: low }]\n"
                "    takeover:\n      providerInstanceId: claudeAgent\n      model: claude-haiku-5-5\n"
                "  opencode:\n    light:\n      providerInstanceId: opencode\n"
                "      model: anthropic/claude-haiku-5-5\n"
                "    takeover:\n      providerInstanceId: opencode\n      model: anthropic/claude-haiku-5-5\n",
            )
            read = lambda rel: (workspace / rel).read_text(encoding="utf-8")  # noqa: E731
            self.assertIn("\nmodel: claude-haiku-5-5\neffort: low\n---", read(".claude/agents/git-start.md"))
            self.assertIn(
                "\nmodel: anthropic/claude-haiku-5-5\n---", read(".opencode/commands/kit-ai/git-start.md")
            )
            self.assertNotIn("model:", read(".claude/skills/kit-ai/skills/git-start/SKILL.md").split("---")[1])
            self.assertNotIn("model:", read(".claude/agents/night-run.md").split("---")[1])

    def test_models_key_stops_bootstrap_with_migration_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8") + "\nmodels:\n  claude:\n    light: haiku\n",
                encoding="utf-8",
            )
            with self.assertRaises(BootstrapError) as ctx:
                run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")
            self.assertIn("models:", str(ctx.exception))
            self.assertIn("targets:", str(ctx.exception))

    def test_invalid_agents_block_fails_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            with self.assertRaises(BootstrapError) as ctx:
                self._install(
                    workspace,
                    "\ntargets:\n  claude:\n    turbo:\n      providerInstanceId: claudeAgent\n",
                )
            self.assertIn("targets.claude.turbo", str(ctx.exception))


class TestClaudeAgentDescription(_BootstrapTestCase, unittest.TestCase):
    """Kopia agenta Claude z " #" w opisie wraca z YAML w całości (#547)."""

    def test_generated_claude_agent_keeps_full_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            text = (workspace / ".claude" / "agents" / "git-end.md").read_text(encoding="utf-8")
            meta = yaml.safe_load(text.split("---\n")[1])
            self.assertIn("(Closes #N)", meta["description"])
            self.assertTrue(meta["description"].endswith("(Dawniej git-pr.)"), meta["description"])


class TestHeadlessAgent(_BootstrapTestCase, unittest.TestCase):
    """Agent `/headless` i wrapper tylko przy ≥2 klientach z trybem headless (#169)."""

    HOST_FILES = {
        "claude": (".claude/agents/headless.md", ".claude/skills/kit-ai/skills/headless/SKILL.md"),
        "opencode": (".opencode/commands/kit-ai/headless.md",),
        "codex": (".codex/skills/headless/SKILL.md",),
        "cursor": (".cursor/agents/headless.md",),
    }

    def _install(self, workspace: Path, clients: str) -> None:
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)

    def test_installed_for_every_host_with_its_own_host_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode,codex,cursor")
            sys.path.insert(0, str(KIT_ROOT / "scripts"))
            from command_prefix import read_values, resolve
            sigil, namespace, name_prefix = read_values(KIT_ROOT / "manifest.yaml", "shared")
            expected_headless = resolve(
                (KIT_ROOT / "templates/shared/headless/headless.mjs").read_text(encoding="utf-8"),
                sigil=sigil,
                namespace=namespace,
                name_prefix=name_prefix,
            )
            self.assertEqual(
                (workspace / ".ai/headless.mjs").read_text(encoding="utf-8"),
                expected_headless,
            )
            for host, files in self.HOST_FILES.items():
                for rel in files:
                    with self.subTest(file=rel):
                        text = (workspace / rel).read_text(encoding="utf-8")
                        self.assertIn(f"--host {host} ", text)
                        self.assertNotIn("@KIT_HOST@", text)

    def test_not_installed_with_fewer_than_two_headless_clients(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,codex,cursor")
            self.assertFalse((workspace / ".ai/headless.mjs").exists())
            self.assertFalse((workspace / ".claude/agents/headless.md").exists())
            self.assertFalse((workspace / ".codex/skills/headless").exists())

    def test_installed_with_antigravity_as_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,antigravity")
            self.assertTrue((workspace / ".ai/headless.mjs").is_file())
            self.assertTrue((workspace / ".agents/skills/headless/SKILL.md").is_file())

    def test_removed_when_clients_drop_below_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode,antigravity")
            self.assertTrue((workspace / ".agents/skills/headless/SKILL.md").is_file())
            self._install(workspace, "claude,codex")
            self.assertFalse((workspace / ".agents/skills/headless").exists())
            self.assertFalse((workspace / ".ai/headless.mjs").exists())
            self.assertFalse((workspace / ".claude/agents/headless.md").exists())
            self.assertFalse((workspace / ".claude/skills/kit-ai/skills/headless/SKILL.md").exists())

    def test_light_tier_model_lands_in_claude_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode")
            agent = workspace / ".claude/agents/headless.md"
            self.assertNotIn("model:", agent.read_text(encoding="utf-8").split("---")[1])
            profile = workspace / ".ai/project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8")
                + "\ntargets:\n  claude:\n    light:\n      providerInstanceId: claudeAgent\n      model: haiku\n"
                "    takeover:\n      providerInstanceId: claudeAgent\n      model: haiku\n",
                encoding="utf-8",
            )
            self._install(workspace, "claude,opencode")
            self.assertIn("\nmodel: haiku\n---", agent.read_text(encoding="utf-8"))

    def test_remove_deletes_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, remove=True)
            self.assertFalse((workspace / ".ai/headless.mjs").exists())


if __name__ == "__main__":
    unittest.main()
