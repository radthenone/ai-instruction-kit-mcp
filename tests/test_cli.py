"""Testy CLI ``kit-ai`` (install / reload / status) i narzędzia MCP ``reload_workspace``.

Bootstrap leci naprawdę (``scripts/bootstrap-project.sh``) na katalogach tymczasowych,
bez TTY — pytania są pomijane, liczą się flagi.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from _shell import posix_path, resolve_bash
from test_bootstrap import KIT_ROOT, _BootstrapTestCase, _snapshot

from guides import cli, server


def _quiet_main(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class TestInstall(_BootstrapTestCase):
    def test_install_with_flags_writes_profile_files_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "tmp-app"

            code, out = _quiet_main("install", str(app), "--language", "en", "--clients", "claude")

            self.assertEqual(code, 0, out)
            profile = yaml.safe_load((app / ".ai" / "project.profile.yaml").read_text())
            self.assertEqual(profile["language"], "en")
            self.assertEqual(profile["clients"], "claude")
            self.assertEqual(profile["name"], "tmp-app")
            for tier in ("backend", "web", "mobile"):
                self.assertEqual(profile[tier], "none")
            self.assertTrue((app / ".ai" / "project.md").is_file())
            self.assertTrue((app / ".claude" / "hooks" / "git-guard.mjs").is_file())

            mcp = (app / ".mcp.json").read_text(encoding="utf-8")
            self.assertNotIn("--codegen", mcp)
            self.assertNotIn("--preset", mcp)
            self.assertIn('"run", "--project"', mcp)

            self.assertIn('"mcpServers"', out)
            self.assertIn("claude: .mcp.json", out)
            self.assertIn("/kit-project-begin", out)
            # #122: brak hooka pre-push, Superpowers z settings.json, blok „Dalej”.
            self.assertFalse((app / "git-hooks").exists())
            settings = json.loads((app / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertIn("superpowers-marketplace", settings["extraKnownMarketplaces"])
            self.assertIs(settings["enabledPlugins"]["superpowers@superpowers-marketplace"], True)
            self.assertIn("Dalej", out)
            self.assertIn("/plugin install superpowers@superpowers-marketplace", out)

    def test_reload_keeps_user_settings_and_does_not_duplicate_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            path = app / ".claude" / "settings.json"
            settings = json.loads(path.read_text(encoding="utf-8"))
            settings["permissions"] = {"allow": ["Bash(ls)"]}
            settings["enabledPlugins"]["moj@moj-market"] = True
            path.write_text(json.dumps(settings), encoding="utf-8")

            self.assertEqual(_quiet_main("reload", str(app))[0], 0)

            after = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(after["permissions"], {"allow": ["Bash(ls)"]})
            self.assertEqual(
                after["enabledPlugins"],
                {"moj@moj-market": True, "superpowers@superpowers-marketplace": True},
            )
            self.assertEqual(list(after["extraKnownMarketplaces"]), ["superpowers-marketplace"])

    def test_install_refuses_existing_kit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            (app / ".ai").mkdir(parents=True)
            (app / ".ai" / "project.profile.yaml").write_text("name: app\n", encoding="utf-8")

            code, out = _quiet_main("install", str(app), "--clients", "claude")

            self.assertEqual(code, 1)
            self.assertIn("kit-ai reload", out)
            self.assertEqual(
                (app / ".ai" / "project.profile.yaml").read_text(encoding="utf-8"), "name: app\n"
            )


class TestReload(_BootstrapTestCase):
    def test_tier_change_keeps_mcp_json_and_overlay(self) -> None:
        """Stack w Profilu nie trafia do konfiguracji klienta — reload jej nie zmienia."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            mcp_before = (app / ".mcp.json").read_text(encoding="utf-8")
            overlay = app / ".ai" / "project.md"
            overlay.write_text("# moje\n", encoding="utf-8")
            profile = app / ".ai" / "project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8").replace("backend: none", "backend: fastapi"),
                encoding="utf-8",
            )

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertEqual((app / ".mcp.json").read_text(encoding="utf-8"), mcp_before)
            self.assertEqual(overlay.read_text(encoding="utf-8"), "# moje\n")
            self.assertIn("backend: fastapi", profile.read_text(encoding="utf-8"))

    def test_reload_migrates_preset_stamp(self) -> None:
        """Repo sprzed Tierów: stamp z presetem, bez Profilu → Profil core + none."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            (app / ".ai").mkdir(parents=True)
            (app / ".ai" / ".kit-bootstrap.json").write_text(
                json.dumps(
                    {
                        "kit_commit": "",
                        "preset": "_base",
                        "language": "en",
                        "codegen": "orval",
                        "clients": "claude",
                    }
                ),
                encoding="utf-8",
            )
            (app / ".mcp.json").write_text(
                '{"mcpServers": {"project-guides": {"args": ["--preset", "_base"]}}}\n', encoding="utf-8"
            )

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertIn("Profil core + none", out)
            profile = yaml.safe_load((app / ".ai" / "project.profile.yaml").read_text())
            self.assertEqual(profile["language"], "en")
            self.assertEqual(profile["clients"], "claude")
            self.assertEqual(profile["backend"], "none")
            args = json.loads((app / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["project-guides"]["args"]
            self.assertNotIn("--preset", args)
            self.assertEqual(args[args.index("--language") + 1], "en")
            stamp = json.loads((app / ".ai" / ".kit-bootstrap.json").read_text(encoding="utf-8"))
            self.assertNotIn("preset", stamp)

    def test_reload_without_kit_points_to_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _quiet_main("reload", tmp)
            self.assertEqual(code, 1)
            self.assertIn("kit-ai install", out)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=True)


class TestReloadCommitHint(_BootstrapTestCase):
    """Po reloadzie lista plików kita do zacommitowania przed `git pull` (#281)."""

    HINT = "chore: sync kit files"
    HOOK = ".claude/hooks/git-guard.mjs"

    def _installed_repo(self, tmp: str) -> Path:
        app = Path(tmp) / "app"
        self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
        _git(app, "init", "-q")
        _git(app, "config", "user.email", "test@test.local")
        _git(app, "config", "user.name", "test")
        (app / self.HOOK).write_text("// stara wersja kita\n", encoding="utf-8")
        _git(app, "add", "-A")
        _git(app, "commit", "-q", "-m", "init")
        return app

    def test_reload_lists_changed_kit_files_and_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._installed_repo(tmp)
            (app / "src").mkdir()
            (app / "src" / "app.py").write_text("print('moje')\n", encoding="utf-8")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertTrue(out.rstrip().endswith(f'"{self.HINT}"`.'), out[-300:])
            self.assertIn(self.HOOK, self._hint_section(out))
            self.assertNotIn("src/app.py", out)

    def test_reload_lists_file_dirty_before_and_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._installed_repo(tmp)
            (app / self.HOOK).write_text("// moja zmiana\n", encoding="utf-8")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertIn(self.HOOK, self._hint_section(out))

    def test_reload_lists_pruned_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude,cursor")[0], 0)
            _git(app, "init", "-q")
            _git(app, "config", "user.email", "test@test.local")
            _git(app, "config", "user.name", "test")
            _git(app, "add", "-A")
            _git(app, "commit", "-q", "-m", "init")
            profile = app / ".ai" / "project.profile.yaml"
            text = profile.read_text(encoding="utf-8")
            self.assertIn("clients: cursor,claude", text)
            profile.write_text(text.replace("clients: cursor,claude", "clients: claude"), encoding="utf-8")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertIn(".cursor/", self._hint_section(out))

    def test_dry_run_prints_no_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._installed_repo(tmp)

            code, out = _quiet_main("reload", str(app), "--dry-run")
            mcp_out = self._mcp_reload(app, dry_run=True)

            self.assertEqual(code, 0, out)
            self.assertNotIn(self.HINT, out)
            self.assertNotIn(self.HINT, mcp_out)

    def test_second_reload_prints_no_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._installed_repo(tmp)
            self.assertEqual(_quiet_main("reload", str(app))[0], 0)

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertNotIn(self.HINT, out)

    def test_reload_outside_git_prints_no_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            (app / self.HOOK).write_text("// stara wersja kita\n", encoding="utf-8")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertNotIn(self.HINT, out)

    def test_mcp_reload_lists_changed_kit_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self._installed_repo(tmp)
            out = self._mcp_reload(app, dry_run=False)

            self.assertTrue(out.rstrip().endswith(f'"{self.HINT}"`.'), out[-300:])
            hint = self._hint_section(out)
            self.assertIn(self.HOOK, hint)
            self.assertNotIn("```", hint)

    @staticmethod
    def _hint_section(out: str) -> str:
        return out.partition("Reload zmienił pliki kita:")[2]

    @staticmethod
    def _mcp_reload(app: Path, *, dry_run: bool) -> str:
        saved = (server._kit_root, server._workspace_root)
        server._kit_root, server._workspace_root = KIT_ROOT, app
        try:
            return server.reload_workspace(dry_run=dry_run)
        finally:
            server._kit_root, server._workspace_root = saved


class TestReloadTool(_BootstrapTestCase):
    def test_mcp_reload_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            (app / ".claude" / "hooks" / "git-guard.mjs").unlink()
            before = _snapshot(app)
            saved = (server._kit_root, server._workspace_root)
            server._kit_root, server._workspace_root = KIT_ROOT, app
            try:
                out = server.reload_workspace()
            finally:
                server._kit_root, server._workspace_root = saved

            self.assertEqual(_snapshot(app), before)
            self.assertIn("dry run", out)
            self.assertIn(".claude/hooks/git-guard.mjs", out)


USER_FILES = {
    ".claude/agents/moj.md": "moj agent\n",
    ".claude/commands/moja.md": "moja komenda\n",
    ".claude/hooks/moj-hook.sh": "#!/bin/sh\n",
    ".opencode/moje.txt": "moje\n",
    ".codex/skills/moj/SKILL.md": "moj skill\n",
    ".github/prompts/moj.prompt.md": "moj prompt\n",
    ".cursor/agents/moj.md": "moj cursor\n",
    "src/app.py": "print('app')\n",
}


def _write_user_files(app: Path) -> None:
    for rel, text in USER_FILES.items():
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_text(text, encoding="utf-8")


class TestPruneAndRemove(_BootstrapTestCase):
    """Prune i `kit-ai remove` kasują tylko pliki kita — własne pliki użytkownika zostają (#123)."""

    def test_unselected_client_prune_keeps_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "all")[0], 0)
            _write_user_files(app)
            profile = app / ".ai" / "project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8").replace("clients: all", "clients: kiro"),
                encoding="utf-8",
            )

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            for rel, text in USER_FILES.items():
                self.assertEqual((app / rel).read_text(encoding="utf-8"), text, rel)
            for rel in (
                ".claude/agents/git-start.md",
                ".claude/commands/git-start.md",
                ".claude/hooks/git-guard.mjs",
                ".claude/skills",
                ".opencode/command",
                ".opencode/plugins",
                "opencode.json",
                ".codex/skills/git-start",
                ".codex/config.toml",
                ".github/prompts/git-start.prompt.md",
                ".cursor/agents/git-start.md",
                ".cursor/mcp.json",
                ".mcp.json",
            ):
                self.assertFalse((app / rel).exists(), rel)
            self.assertTrue((app / ".kiro" / "agents" / "git-start.md").is_file())

    def test_remove_leaves_only_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            # Bajty, nie write_text: na Windows dałby CRLF, a kit celowo zapisuje .gitignore w LF.
            (app / ".gitignore").write_bytes(b"node_modules/\n")
            _write_user_files(app)
            before = _snapshot(app)
            self.assertEqual(_quiet_main("install", str(app), "--clients", "all")[0], 0)
            (app / "BUGBOT.md").write_bytes("# moje reguły\n".encode())
            settings = app / ".claude" / "settings.json"
            data = json.loads(settings.read_text(encoding="utf-8"))
            data["permissions"] = {"allow": ["Bash(ls)"]}
            settings.write_text(json.dumps(data), encoding="utf-8")

            code, out = _quiet_main("remove", str(app))

            self.assertEqual(code, 0, out)
            after = _snapshot(app)
            # Nietknięte AGENTS.md / .gitattributes zniknęły, zmieniony BUGBOT.md został.
            self.assertEqual(after.pop("BUGBOT.md"), "# moje reguły\n".encode())
            self.assertIn(b"permissions", after.pop(".claude/settings.json"))
            self.assertNotIn(b"git-guard", settings.read_bytes())
            self.assertIn(".ai/project.md", after)
            after.pop(".ai/project.md")
            self.assertEqual(after, before)

    def test_remove_drops_bugbot_with_empty_block_but_keeps_project_rules(self) -> None:
        """`--remove` traktuje pusty blok jak nietknięty plik, ale reguły projektu zostawia."""
        open_marker = "<!-- project:rules -->"
        close_marker = "<!-- /project:rules -->"

        def rewrite_block(app: Path, rules: str) -> Path:
            bugbot = app / "BUGBOT.md"
            text = bugbot.read_text(encoding="utf-8")
            start = text.index(open_marker) + len(open_marker)
            end = text.index(close_marker)
            bugbot.write_text(text[:start] + rules + text[end:], encoding="utf-8", newline="\n")
            return bugbot

        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            bugbot = rewrite_block(app, "\n")

            self.assertEqual(_quiet_main("remove", str(app))[0], 0)

            self.assertFalse(bugbot.exists())

        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            bugbot = rewrite_block(app, "\n- Moja reguła\n")

            self.assertEqual(_quiet_main("remove", str(app))[0], 0)

            self.assertIn("- Moja reguła", bugbot.read_text(encoding="utf-8"))

    def test_remove_keeps_changed_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            agents = app / "AGENTS.md"
            agents.write_text(agents.read_text(encoding="utf-8") + "\n## Moje\n", encoding="utf-8")

            self.assertEqual(_quiet_main("remove", str(app))[0], 0)

            self.assertIn("## Moje", agents.read_text(encoding="utf-8"))
            self.assertFalse((app / ".ai" / "project.profile.yaml").exists())
            self.assertFalse((app / ".ai" / ".kit-bootstrap.json").exists())

    def test_remove_dry_run_lists_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude")[0], 0)
            before = _snapshot(app)

            code, out = _quiet_main("remove", str(app), "--dry-run")

            self.assertEqual(code, 0, out)
            self.assertEqual(_snapshot(app), before)
            self.assertIn(".claude/hooks/git-guard.mjs", out)
            self.assertIn(".ai/project.profile.yaml", out)
            self.assertNotIn(".ai/project.md", out)

    def test_remove_without_kit_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _quiet_main("remove", tmp)
            self.assertEqual(code, 1)
            self.assertIn("nie ma kita", out)


class TestBashRejectsPresets(_BootstrapTestCase):
    def test_preset_flag_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for flag in ("--preset", "--codegen"):
                with self.subTest(flag=flag):
                    result = subprocess.run(
                        [
                            resolve_bash() or "bash",
                            posix_path(KIT_ROOT / "scripts" / "bootstrap-project.sh"),
                            tmp,
                            flag,
                            "x",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        stdin=subprocess.DEVNULL,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("kit-ai reload", result.stderr)


class TestHelpers(unittest.TestCase):
    def test_git_bash_paths_on_windows(self) -> None:
        self.assertEqual(cli.to_path("/m/projects/app", windows=True), Path("M:/projects/app"))
        self.assertEqual(cli.to_path("M:/projects/app", windows=True), Path("M:/projects/app"))
        self.assertEqual(cli.to_path("/m/projects", windows=False), Path("/m/projects"))

    def test_questions_fall_back_to_defaults_on_eof(self) -> None:
        # Windows: stdin z NUL ma isatty() == True, więc pytania padają mimo braku wejścia.
        def eof(_prompt: str) -> str:
            raise EOFError

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.ask_settings(None, None, interactive=True, input_fn=eof), ("pl", "all"))

    def test_questions_use_defaults_and_retry_invalid(self) -> None:
        answers = iter(["", "nope", "claude,codex"])
        with contextlib.redirect_stdout(io.StringIO()):
            language, clients = cli.ask_settings(
                None, None, interactive=True, input_fn=lambda _prompt: next(answers)
            )
        self.assertEqual((language, clients), ("pl", "claude,codex"))

    def test_no_tty_skips_questions(self) -> None:
        def _fail(_prompt: str) -> str:
            raise AssertionError("pytanie bez TTY")

        self.assertEqual(
            cli.ask_settings(None, None, interactive=False, input_fn=_fail), ("pl", "all")
        )

    def test_mcp_entry_modes(self) -> None:
        workspace = Path("/srv/app")
        clone = cli.mcp_server_entry(
            cli.KitSource("/kit", is_clone=True), language="pl", clients="all", workspace=workspace
        )
        self.assertEqual(clone["command"], "uv")
        self.assertEqual(clone["args"][:3], ["run", "--project", "/kit"])
        remote = cli.mcp_server_entry(
            cli.KitSource("git+https://x/kit.git@v1", is_clone=False),
            language="pl",
            clients="all",
            workspace=workspace,
        )
        self.assertEqual(remote["command"], "uvx")
        self.assertEqual(remote["args"][:2], ["--from", "git+https://x/kit.git@v1"])
        for entry in (clone, remote):
            self.assertNotIn("--codegen", entry["args"])
            self.assertEqual(entry["args"][-2:], ["--workspace", "/srv/app"])


class TestWorkspaceSettings(unittest.TestCase):
    def test_profile_without_clients_falls_back_to_stamp(self) -> None:
        """Profil sprzed kit-ai (bez `clients:`) nie może zgubić klientów i języka ze stampu."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / ".ai").mkdir()
            (app / ".ai" / "project.profile.yaml").write_text(
                "name: app\nlanguage: pl\nbackend: none\n", encoding="utf-8"
            )
            (app / ".ai" / ".kit-bootstrap.json").write_text(
                json.dumps({"language": "en", "clients": "claude"}), encoding="utf-8"
            )

            settings = cli.workspace_settings(app)

            self.assertEqual((settings.language, settings.clients), ("en", "claude"))
            self.assertFalse(settings.migrated)

    def test_fresh_clone_reads_clients_from_committed_kit_files(self) -> None:
        """Stamp jest w .gitignore — świeży klon / worktree ma tylko zacommitowane pliki kita."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            for rel in (".claude/agents/git-start.md", ".opencode/command/git-start.md"):
                (app / rel).parent.mkdir(parents=True)
                (app / rel).write_text("---\n", encoding="utf-8")

            settings = cli.workspace_settings(app)

            self.assertEqual((settings.language, settings.clients), ("pl", "claude,opencode"))
            self.assertTrue(settings.migrated)

    def test_overlay_left_by_remove_is_not_a_kit(self) -> None:
        """`remove` zostawia `.ai/project.md` — po nim `install` ma znów przejść."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / ".ai").mkdir()
            (app / ".ai" / "project.md").write_text("# app\n", encoding="utf-8")

            with self.assertRaises(cli.SetupError):
                cli.workspace_settings(app)


class TestKitRepoAsWorkspace(unittest.TestCase):
    """Repo kita rozpoznajemy po zawartości — także gdy CLI działa z koła (`uv tool`)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.wheel = Path(self._tmp.name) / "wheel" / "_data"
        self.wheel.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_kit_repo_is_its_own_source(self) -> None:
        """Koło bywa starsze od checkoutu — reload i status w repo kita biorą checkout."""
        self.assertEqual(cli.own_kit_root(KIT_ROOT, self.wheel), KIT_ROOT)

    def test_app_repo_keeps_given_kit(self) -> None:
        app = Path(self._tmp.name) / "app"
        app.mkdir()
        self.assertEqual(cli.own_kit_root(app, self.wheel), self.wheel)

    def test_install_and_remove_refuse_kit_repo_from_wheel(self) -> None:
        """Dawny warunek `workspace == kit_root` przepuszczał to, gdy kit był kołem."""
        with self.assertRaisesRegex(cli.SetupError, "repo kita"):
            cli.install_workspace(KIT_ROOT, self.wheel, language="pl", clients="claude")
        with self.assertRaisesRegex(cli.SetupError, "repo kita"):
            cli.remove_workspace(KIT_ROOT, self.wheel, dry_run=True)


if __name__ == "__main__":
    unittest.main()
