"""Komendy Claude Code jako plugin skills-dir ``kit-ai`` (#526).

Plugin ląduje w ``.claude/skills/kit-ai/``: manifest ``.claude-plugin/plugin.json``
bez pola ``version`` i ``skills/<nazwa>/SKILL.md`` dla każdej komendy kita.
Wywołanie ``/kit-ai:<nazwa>``; zewnętrzne skille (``/tdd``, ``/grill-me``) zostają
bez prefiksu, bo nie mają placeholdera prefiksu.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from guides.bootstrap import run_bootstrap
from guides.doctor import _command_names

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = KIT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    # render_agent_commands.py importuje command_prefix; w bootstrapie robi to bash.
    sys.path.insert(0, str(SCRIPTS))
PLUGIN_DIR = ".claude/skills/kit-ai"
SKILLS_DIR = f"{PLUGIN_DIR}/skills"
PROFILE = """name: plugin-test
language: pl
clients: claude,opencode
backend: django
web: react
mobile: none
"""


def _load_script(name: str):
    """Załaduj skrypt z ``scripts/`` jako moduł, bez zmiany sys.path."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(workspace: Path, *, skip_agents: bool = False) -> None:
    """Zainstaluj kit w ``workspace`` z Profilu z oboma Tierami."""
    (workspace / ".ai").mkdir(parents=True, exist_ok=True)
    (workspace / ".ai" / "project.profile.yaml").write_text(PROFILE, encoding="utf-8")
    run_bootstrap(
        target=workspace,
        kit_root=KIT_ROOT,
        clients="claude,opencode",
        skip_agents=skip_agents,
    )


class TestClaudePluginSkills(unittest.TestCase):
    """Plugin ``kit-ai``: manifest, skille komend i migracja starych komend."""

    def test_every_shared_command_is_a_plugin_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)

            plugin = workspace / PLUGIN_DIR
            manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "kit-ai")
            self.assertNotIn("version", manifest)

            expected = {path.stem for path in (KIT_ROOT / "templates" / "shared" / "agents").glob("*.md")}
            installed = {path.parent.name for path in (plugin / "skills").glob("*/SKILL.md")}
            self.assertEqual(installed, expected)

            for name in sorted(installed):
                text = (plugin / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                front = text.split("---")[1]
                with self.subTest(skill=name):
                    self.assertIn(f"\nname: {name}\n", front)
                    self.assertIn("description:", front)
                    self.assertNotIn("readonly:", front)

    def test_frontmatter_keeps_disable_model_invocation_and_drops_readonly(self) -> None:
        module = _load_script("render_agent_commands")
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            (src_dir / "demo.md").write_text(
                "---\nname: demo\ndescription: Demo\nreadonly: true\n"
                "disable-model-invocation: true\n---\n\n"
                "Uruchom @KIT_CMD_PREFIX@git-start albo /tdd.\n",
                encoding="utf-8",
            )
            dest_dir = Path(tmp) / "plugin"
            rc = module.main(["render_agent_commands.py", "claude", str(src_dir), str(dest_dir)])
            self.assertEqual(rc, 0)

            text = (dest_dir / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("name: demo", text)
            self.assertIn("disable-model-invocation: true", text)
            self.assertNotIn("readonly:", text)
            self.assertIn("/kit-ai:git-start", text)
            self.assertIn("/tdd", text)
            self.assertNotIn("@KIT_", text)

    def test_headless_skill_has_host_substituted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)
            text = (workspace / SKILLS_DIR / "headless" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("--host claude ", text)
            self.assertNotIn("@KIT_HOST@", text)

    def test_tier_change_removes_plugin_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)
            self.assertTrue((workspace / SKILLS_DIR / "review-backend" / "SKILL.md").is_file())

            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8")
                .replace("backend: django", "backend: none")
                .replace("web: react", "web: none"),
                encoding="utf-8",
            )
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")

            self.assertFalse((workspace / SKILLS_DIR / "review-backend").exists())
            self.assertFalse((workspace / SKILLS_DIR / "review-frontend").exists())
            self.assertTrue((workspace / SKILLS_DIR / "git-start" / "SKILL.md").is_file())

    def test_skip_agents_generates_no_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace, skip_agents=True)
            self.assertFalse((workspace / PLUGIN_DIR).exists())

    def test_remove_deletes_plugin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)
            self.assertTrue((workspace / PLUGIN_DIR).is_dir())

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode", remove=True)
            self.assertFalse((workspace / PLUGIN_DIR).exists())

    def test_reload_removes_legacy_commands_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            cmd_dir = workspace / ".claude" / "commands"
            cmd_dir.mkdir(parents=True)
            git_start = cmd_dir / "git-start.md"
            git_start.write_text("stara komenda\n", encoding="utf-8")
            review_be = cmd_dir / "review-backend.md"
            review_be.write_text("stara komenda\n", encoding="utf-8")
            mine = cmd_dir / "mine.md"
            mine.write_text("moja komenda\n", encoding="utf-8")

            _install(workspace)
            self.assertFalse(git_start.exists())
            self.assertFalse(review_be.exists())
            self.assertTrue(mine.exists())
            self.assertTrue(cmd_dir.is_dir())

    def test_remove_cleans_legacy_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)
            cmd_dir = workspace / ".claude" / "commands"
            cmd_dir.mkdir(parents=True, exist_ok=True)
            git_start = cmd_dir / "git-start.md"
            git_start.write_text("stara komenda\n", encoding="utf-8")
            review_ui = cmd_dir / "review-ui.md"
            review_ui.write_text("stara komenda\n", encoding="utf-8")
            mine = cmd_dir / "mine.md"
            mine.write_text("moja komenda\n", encoding="utf-8")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode", remove=True)
            self.assertFalse(git_start.exists())
            self.assertFalse(review_ui.exists())
            self.assertTrue(mine.exists())
            self.assertTrue(cmd_dir.is_dir())

    def test_reload_prunes_orphan_plugin_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            _install(workspace)

            orphan_dir = workspace / SKILLS_DIR / "stary-agent"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "SKILL.md").write_text("orphan\n", encoding="utf-8")

            custom_skill_dir = workspace / ".claude" / "skills" / "moj-skill"
            custom_skill_dir.mkdir(parents=True)
            (custom_skill_dir / "SKILL.md").write_text("custom\n", encoding="utf-8")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")
            self.assertFalse(orphan_dir.exists())
            self.assertTrue(custom_skill_dir.is_dir())
            self.assertTrue((custom_skill_dir / "SKILL.md").is_file())


class TestClaudePluginDiscovery(unittest.TestCase):
    """Doctor i kit_status znają ścieżkę pluginu."""

    def test_doctor_lists_plugin_skills_as_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            skill = workspace / SKILLS_DIR / "git-start" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: git-start\ndescription: Start\n---\n", encoding="utf-8")

            names = _command_names(workspace, {"claude"}, is_kit=False)
            self.assertIn("git-start", names)


if __name__ == "__main__":
    unittest.main()
