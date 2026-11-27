"""Testy integracyjne rdzenia ``scripts/bootstrap-project.sh``: dry-run, real-run, git i scalanie E2E."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_bootstrap import KIT_ROOT, _BootstrapTestCase, _snapshot

from guides.bootstrap import BootstrapError, plan_bootstrap, run_bootstrap


class TestDryRun(_BootstrapTestCase, unittest.TestCase):
    """Tryb dry-run (``plan_bootstrap``) na sandboxie."""

    def test_dry_run_does_not_touch_workspace(self) -> None:
        """Plan powstaje z przebiegu w sandboxie — repo aplikacji zostaje nietknięte."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "README.md").write_text("app\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)

            self.assertIn(".claude/hooks/git-guard.mjs", plan.created)
            self.assertIn(".claude/settings.json", plan.created)
            self.assertIn(".ai/.kit-bootstrap.json", plan.created)
            self.assertEqual(plan.modified, [])
            self.assertEqual(plan.deleted, [])

    def test_dry_run_reports_deletions_from_client_pruning(self) -> None:
        """Sprzątanie klientów spoza --clients też widać w planie, zanim skasuje."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".cursor" / "hooks").mkdir(parents=True)
            (workspace / ".cursor" / "mcp.json").write_text("{}\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)
            self.assertIn(".cursor/mcp.json", plan.deleted)

    def test_dry_run_skips_headless_runs(self) -> None:
        """Logi i worktree runów /headless (#183) nie są kopiowane do sandboxu planu."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run = workspace / ".ai" / "headless-runs" / "r1"
            run.mkdir(parents=True)
            (run / "headless.log").write_text("log\n", encoding="utf-8")

            plan = plan_bootstrap(workspace_root=workspace, kit_root=KIT_ROOT, clients="claude")
            listed = plan.created + plan.modified + plan.deleted + plan.unchanged
            self.assertFalse([rel for rel in listed if "headless-runs" in rel], listed)

    def test_dry_run_does_not_list_existing_claude_md_as_created(self) -> None:
        """Bootstrap tworzy `CLAUDE.md` tylko gdy brak — istniejący nie jest „Nowy” (#279)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "CLAUDE.md").write_text("@AGENTS.md\n# własne\n", encoding="utf-8")

            plan = plan_bootstrap(workspace_root=workspace, kit_root=KIT_ROOT, clients="claude")
            self.assertNotIn("CLAUDE.md", plan.created)
            self.assertNotIn("CLAUDE.md", plan.modified)

    def test_dry_run_right_after_real_run_reports_no_changes(self) -> None:
        """Dry-run zaraz po prawdziwym reloadzie nie ma nic do zrobienia (#279)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / "docs" / "adr").mkdir(parents=True)
            (workspace / "docs" / "adr" / "0001-x.md").write_text("# x\n", encoding="utf-8")
            (workspace / "CONTEXT.md").write_text("# Słownik\n", encoding="utf-8")
            (workspace / "web").mkdir()
            (workspace / "web" / "package.json").write_text(
                json.dumps({"scripts": {"build": "next build"}}), encoding="utf-8"
            )
            (workspace / "Taskfile.yml").write_text(
                "version: '3'\ntasks:\n  test:\n    cmds:\n      - pytest -n auto\n",
                encoding="utf-8",
            )

            run_bootstrap(kit_root=KIT_ROOT, target=workspace)
            plan = plan_bootstrap(workspace_root=workspace, kit_root=KIT_ROOT)

            self.assertEqual(plan.created, [])
            self.assertEqual(plan.modified, [])
            self.assertEqual(plan.deleted, [])


class TestRealRun(_BootstrapTestCase, unittest.TestCase):
    """Prawdziwy przebieg ``scripts/bootstrap-project.sh``: instalacja, źródła i git."""

    # Konfigi MCP, które bootstrap renderuje ze ścieżką maszyny (`uv run --project`,
    # `--kit-root`, absolutny `--workspace`) — po jednym na klienta.
    MCP_CONFIGS = (
        ".mcp.json",
        ".cursor/mcp.json",
        ".vscode/mcp.json",
        ".codex/config.toml",
        ".kiro/settings/mcp.json",
        ".kilocode/mcp.json",
        ".agents/mcp_config.json",
        "opencode.json",
    )

    @staticmethod
    def _git(cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()

    def _git_repo(self, workspace: Path) -> None:
        workspace.mkdir()
        self._git(workspace, "init", "-q")
        self._git(workspace, "config", "user.email", "test@test.local")
        self._git(workspace, "config", "user.name", "test")

    def test_run_installs_hooks_settings_and_stamp(self) -> None:
        """Kryterium ukończenia z issue #31 — hooki, PreToolUse i stamp na dysku."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertTrue((workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())
            self.assertTrue((workspace / ".ai" / ".kit-bootstrap.json").is_file())
            # Karta T3 tylko przy `t3code` w Profilu (#514); domyślny Profil jej nie ma.
            self.assertFalse((workspace / ".ai" / "night-run-t3.md").exists())
            settings = (workspace / ".claude" / "settings.json").read_text(encoding="utf-8")
            self.assertIn("PreToolUse", settings)

    def test_inherited_kit_workspace_does_not_leak_into_real_run(self) -> None:
        """`KIT_WORKSPACE` z otoczenia nie przekierowuje prawdziwego reloadu (#279)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            other = Path(tmp) / "other"
            other.mkdir()

            with mock.patch.dict(os.environ, {"KIT_WORKSPACE": str(other)}):
                run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="codex,opencode")

            for rel in (".codex/config.toml", "opencode.json"):
                with self.subTest(config=rel):
                    text = (workspace / rel).read_text(encoding="utf-8")
                    self.assertNotIn(other.as_posix(), text)
                    self.assertIn(workspace.resolve().as_posix(), text)

    def test_local_source_uses_uv_run_not_uvx(self) -> None:
        """Lokalny klon: `uv run --project` czyta kod i moduły z dysku."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(
                target=workspace,
                kit_root=KIT_ROOT,
                clients="claude,codex,vscode,opencode",
                from_src=str(KIT_ROOT),
            )

            for rel in (
                ".mcp.json",
                ".codex/config.toml",
                ".vscode/mcp.json",
                "opencode.json",
            ):
                with self.subTest(config=rel):
                    text = (workspace / rel).read_text(encoding="utf-8")
                    self.assertIn('"uv"', text)
                    self.assertNotIn('"uvx"', text)
                    self.assertIn('"run", "--project"', text)
                    self.assertNotIn("--codegen", text)
                    self.assertNotIn('"--from"', text)
                    self.assertIn("--kit-root", text)

    def test_remote_source_keeps_uvx(self) -> None:
        """Przy źródle zdalnym klonu nie ma — `uvx` jest poprawny, a `--kit-root` wskazywałby w pustkę."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(
                target=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
                from_src="git+https://example.com/kit.git",
            )

            text = (workspace / ".mcp.json").read_text(encoding="utf-8")
            self.assertIn('"uvx"', text)
            self.assertIn('"--from"', text)
            self.assertNotIn("--kit-root", text)

    def test_gitattributes_installed_only_when_missing(self) -> None:
        """Brak pliku → szablon z LF; własny plik projektu zostaje nietknięty."""
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "fresh"
            fresh.mkdir()
            run_bootstrap(target=fresh, kit_root=KIT_ROOT, clients="claude")
            self.assertIn("* text=auto eol=lf", (fresh / ".gitattributes").read_text(encoding="utf-8"))

            own = Path(tmp) / "own"
            own.mkdir()
            (own / ".gitattributes").write_bytes(b"*.png binary\n")
            run_bootstrap(target=own, kit_root=KIT_ROOT, clients="claude")
            self.assertEqual((own / ".gitattributes").read_bytes(), b"*.png binary\n")

    def test_gitignore_keeps_machine_specific_files_out_of_git(self) -> None:
        """Konfigi MCP i stamp są ignorowane przez git, a reszta konfiguracji zostaje wersjonowana (#69)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="all")

            for rel in (*self.MCP_CONFIGS, ".ai/.kit-bootstrap.json"):
                with self.subTest(ignored=rel):
                    self.assertTrue(
                        (workspace / rel).is_file(), f"{rel} nie został wygenerowany"
                    )
                    self.assertEqual(
                        self._git(workspace, "check-ignore", rel), rel, f"{rel} nie jest ignorowany"
                    )

            for rel in (
                ".ai/project.md",
                ".claude/settings.json",
                ".claude/hooks/git-guard.mjs",
                ".codex/skills/skill-authoring/SKILL.md",
                ".cursor/hooks.json",
                ".github/copilot-instructions.md",
                ".agents/hooks/git-guard.mjs",
                ".agents/hooks.json",
            ):
                with self.subTest(versioned=rel):
                    self.assertEqual(
                        self._git(workspace, "check-ignore", rel), "", f"{rel} jest ignorowany"
                    )

    def test_bootstrap_warns_about_tracked_mcp_configs(self) -> None:
        """Wykrycie śledzonych konfigów MCP w indeksie podaje gotową komendę ``git rm --cached`` (#69)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)
            (workspace / ".vscode").mkdir()
            (workspace / ".mcp.json").write_text("{}\n", encoding="utf-8")
            (workspace / ".vscode" / "mcp.json").write_text("{}\n", encoding="utf-8")
            self._git(workspace, "add", ".mcp.json", ".vscode/mcp.json")
            self._git(workspace, "commit", "-q", "-m", "old bootstrap")

            out = run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,vscode")

            self.assertIn(" rm --cached .mcp.json .vscode/mcp.json", out)
            self.assertEqual(
                self._git(workspace, "ls-files", ".mcp.json"), ".mcp.json",
                "bootstrap sam odśledził plik — to decyzja użytkownika",
            )

    def test_bootstrap_is_quiet_when_nothing_machine_specific_is_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)

            out = run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertNotIn("git rm --cached", out)

    def test_missing_script_is_an_error(self) -> None:
        """Kit bez skryptu bootstrapu — jasny błąd zamiast cichego nic."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_kit = Path(tmp) / "kit"
            fake_kit.mkdir()
            with self.assertRaises(BootstrapError) as ctx:
                run_bootstrap(target=Path(tmp) / "app", kit_root=fake_kit)
            self.assertIn("bootstrap-project.sh", str(ctx.exception))


class TestBootstrapShellMergeE2E(_BootstrapTestCase, unittest.TestCase):
    """Testy dymne E2E potwierdzające spięcie ``scripts/bootstrap-project.sh`` z ``guides.bootstrap``."""

    def test_json_and_codex_toml_merge_e2e(self) -> None:
        """Pełny przebieg powłoki scala JSON i TOML użytkownika z wpisem kita (#160)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex")

            mcp_path = workspace / ".mcp.json"
            mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
            mcp_data["mcpServers"]["mine"] = {"command": "my-server"}
            mcp_data["mcpServers"]["project-guides"] = {"command": "legacy"}
            mcp_path.write_text(json.dumps(mcp_data), encoding="utf-8")

            toml_path = workspace / ".codex" / "config.toml"
            mine_toml = '\n[mcp_servers.mine]\ncommand = "x"\n'
            toml_path.write_text(toml_path.read_text(encoding="utf-8") + mine_toml, encoding="utf-8")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex")

            merged_mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
            self.assertEqual(merged_mcp["mcpServers"]["mine"], {"command": "my-server"})
            self.assertNotIn("project-guides", merged_mcp["mcpServers"])
            merged_toml = toml_path.read_text(encoding="utf-8")
            self.assertIn(mine_toml, merged_toml)
            self.assertEqual(merged_toml.count("[mcp_servers.kit-ai-mcp]"), 1)

    def test_gitignore_section_e2e_idempotent(self) -> None:
        """Pełny przebieg powłoki dopisuje i odświeża sekcję ``.gitignore`` idempotentnie."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            gitignore = workspace / ".gitignore"
            gitignore.write_text("node_modules/\n", encoding="utf-8")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            first = gitignore.read_text(encoding="utf-8")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            second = gitignore.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertEqual(second.count("# >>> instruction-kit >>>"), 1)
            self.assertIn("node_modules/", second)


if __name__ == "__main__":
    unittest.main()
