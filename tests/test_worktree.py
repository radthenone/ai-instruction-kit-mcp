"""Testy konfiguracji worktree, generatora .ai/worktree.json i CLI .ai/worktree.mjs (#299)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guides.doctor import run_doctor
from guides.worktree import (
    DEFAULT_VENV,
    KNOWN_WORKTREE_KEYS,
    MACHINE_FILES,
    VALID_VENV_VALUES,
    parse_worktree_section,
    render_worktree_config,
    resolve_worktree_config,
)

KIT_ROOT = Path(__file__).resolve().parents[1]


class TestWorktreeConfig(unittest.TestCase):
    def test_parse_valid_worktree_section(self) -> None:
        yaml_text = """\
name: test
worktree:
  copy:
    - .env
    - opencode.json
  link:
    - frontend/node_modules
  setup:
    - echo hello
  venv: overlay
"""
        parsed = parse_worktree_section(yaml_text)
        self.assertEqual(parsed["copy"], [".env", "opencode.json"])
        self.assertEqual(parsed["link"], ["frontend/node_modules"])
        self.assertEqual(parsed["setup"], ["echo hello"])
        self.assertEqual(parsed["venv"], "overlay")
        self.assertEqual(parsed["warnings"], [])

    def test_parse_worktree_warnings(self) -> None:
        yaml_text = """\
worktree:
  unknown_key: 123
  copy:
    - valid/path
    - ../invalid/path
  link: not-a-list
  setup:
    - 456
  venv: invalid_choice
"""
        parsed = parse_worktree_section(yaml_text)
        warnings = parsed["warnings"]
        self.assertTrue(any("nieznany klucz `worktree.unknown_key`" in w for w in warnings))
        self.assertTrue(any(".." in w for w in warnings))
        self.assertTrue(any("zły typ `worktree.link" in w for w in warnings))
        self.assertTrue(any("zły typ elementu w `worktree.setup`" in w for w in warnings))
        self.assertTrue(any("zły typ/wartość `worktree.venv" in w for w in warnings))

    def test_resolve_default_copy_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".env").write_text("FOO=bar", encoding="utf-8")
            (workspace / "opencode.json").write_text("{}", encoding="utf-8")
            # .mcp.json does not exist in workspace, so it shouldn't be in copy list

            resolved = resolve_worktree_config({}, workspace_root=workspace)
            self.assertEqual(resolved["venv"], DEFAULT_VENV)
            self.assertEqual(resolved["link"], [])
            self.assertEqual(resolved["setup"], [])
            self.assertIn(".env", resolved["copy"])
            self.assertIn("opencode.json", resolved["copy"])
            self.assertNotIn(".mcp.json", resolved["copy"])

    def test_doctor_validates_worktree_and_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".ai").mkdir()
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(
                "name: test\nworktree:\n  copy:\n    - ../outside\n",
                encoding="utf-8",
            )
            report = run_doctor(workspace, KIT_ROOT, clients="claude")
            kinds = [w.kind for w in report.warnings]
            self.assertIn("invalid-worktree-config", kinds)

            # Fix profile
            profile.write_text("name: test\nworktree:\n  copy:\n    - .env\n", encoding="utf-8")
            # Missing .ai/worktree.json -> drift warning
            report2 = run_doctor(workspace, KIT_ROOT, clients="claude")
            kinds2 = [w.kind for w in report2.warnings]
            self.assertIn("stale-worktree-config", kinds2)

            # Render .ai/worktree.json
            render_worktree_config(workspace, profile)
            report3 = run_doctor(workspace, KIT_ROOT, clients="claude")
            kinds3 = [w.kind for w in report3.warnings]
            self.assertNotIn("stale-worktree-config", kinds3)
            self.assertNotIn("invalid-worktree-config", kinds3)


if __name__ == "__main__":
    unittest.main()

WRAPPER = KIT_ROOT / "templates/shared/worktree/worktree.mjs"
NODE = shutil.which("node") or "node"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    (path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=path, check=True, capture_output=True)


class TestWorktreeCLI(unittest.TestCase):
    def test_cli_add_plain_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            wt_dir = repo / ".worktrees" / "plain-wt"
            # add --plain
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "--detach", "HEAD", "--plain"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}, stderr: {res.stderr}")
            self.assertIn("[worktree] path: " + str(wt_dir), res.stdout)
            self.assertIn("[worktree] branch: detached HEAD", res.stdout)
            self.assertTrue(wt_dir.is_dir())

            # Make dirty
            (wt_dir / "dirty.txt").write_text("dirty", encoding="utf-8")
            # remove without --force should fail
            res_fail = subprocess.run(
                [NODE, str(WRAPPER), "remove", str(wt_dir)],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_fail.returncode, 2)
            self.assertTrue(wt_dir.exists())

            # remove with --force should succeed
            res_force = subprocess.run(
                [NODE, str(WRAPPER), "remove", str(wt_dir), "--force"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_force.returncode, 0)
            self.assertFalse(wt_dir.exists())

    def test_cli_copy_and_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            # Create project files and .ai/worktree.json
            (repo / ".env").write_text("SECRET=123\n", encoding="utf-8")
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "some-pkg.txt").write_text("pkg", encoding="utf-8")

            (repo / ".ai").mkdir()
            (repo / ".ai" / "worktree.json").write_text(
                json.dumps({
                    "copy": [".env"],
                    "link": ["node_modules"],
                    "setup": [],
                    "venv": "none"
                }),
                encoding="utf-8"
            )

            wt_dir = repo / ".worktrees" / "feature-wt"
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "feature-branch"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}, stderr: {res.stderr}")
            self.assertIn("[worktree] copied: .env", res.stdout)
            self.assertIn("[worktree] linked: node_modules", res.stdout)
            self.assertTrue((wt_dir / ".env").is_file())
            self.assertEqual((wt_dir / ".env").read_text(encoding="utf-8"), "SECRET=123\n")
            self.assertTrue((wt_dir / "node_modules").exists())
            self.assertTrue((wt_dir / "node_modules").is_symlink())
            self.assertIn("link do node_modules", res.stdout)

    def test_cli_setup_guard_denial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            # Install server-guard in .claude/hooks
            hooks_dir = repo / ".claude" / "hooks"
            hooks_dir.mkdir(parents=True)
            shutil.copy(KIT_ROOT / "templates/shared/guards/server-guard.mjs", hooks_dir / "server-guard.mjs")

            (repo / ".ai").mkdir()
            (repo / ".ai" / "worktree.json").write_text(
                json.dumps({
                    "copy": [],
                    "link": [],
                    "setup": ["uv sync"],
                    "venv": "none"
                }),
                encoding="utf-8"
            )

            wt_dir = repo / ".worktrees" / "setup-wt"
            env = dict(os.environ, KIT_HOST_PROFILE="vps")
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "setup-branch"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}, stderr: {res.stderr}")
            self.assertIn("setup skipped: uv sync", res.stdout)

    def test_cli_setup_failure_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            (repo / ".ai").mkdir()
            (repo / ".ai" / "worktree.json").write_text(
                json.dumps({
                    "copy": [],
                    "link": [],
                    "setup": ["false"],
                    "venv": "none"
                }),
                encoding="utf-8"
            )

            wt_dir = repo / ".worktrees" / "fail-wt"
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "fail-branch"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertTrue(wt_dir.exists())
            self.assertIn("setup failed: false", res.stdout)

    def test_cli_lockfile_drift_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            (repo / "uv.lock").write_text("lock-v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "uv.lock"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "add lock"], cwd=repo, check=True, capture_output=True)

            wt_dir = repo / ".worktrees" / "lock-wt"
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "lock-branch", "--plain"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)

            # Change lockfile in worktree
            (wt_dir / "uv.lock").write_text("lock-v2-different\n", encoding="utf-8")

            res_sync = subprocess.run(
                [NODE, str(WRAPPER), "sync", str(wt_dir)],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_sync.returncode, 0)
            self.assertIn("deps differ from main checkout — VPS tests unreliable, verify in CI", res_sync.stdout)

    def test_cli_prune_merged_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            wt_dir = repo / ".worktrees" / "merged-wt"
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "merged-branch", "--plain"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertTrue(wt_dir.exists())

            # Commit in worktree and merge to main
            (wt_dir / "file.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=wt_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "wt commit"], cwd=wt_dir, check=True, capture_output=True)

            subprocess.run(["git", "merge", "merged-branch"], cwd=repo, check=True, capture_output=True)

            # Run prune
            res_prune = subprocess.run(
                [NODE, str(WRAPPER), "prune"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_prune.returncode, 0)
            self.assertIn("[worktree] pruned", res_prune.stdout)
            self.assertFalse(wt_dir.exists())

    def test_cli_venv_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            # Create dummy package src/mypkg/__init__.py and commit it
            pkg_dir = repo / "src" / "mypkg"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "__init__.py").write_text("# mypkg\n", encoding="utf-8")
            subprocess.run(["git", "add", "src"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "add pkg"], cwd=repo, check=True, capture_output=True)

            # Create main .venv
            res_venv = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(repo / ".venv")], capture_output=True)
            if res_venv.returncode != 0:
                self.skipTest("Cannot create test venv")

            # Find site-packages
            sp = None
            for pth in (repo / ".venv").rglob("site-packages"):
                if pth.is_dir():
                    sp = pth
                    break
            if not sp:
                self.skipTest("No site-packages in test venv")

            # Add editable .pth pointing to repo/src
            (sp / "mypkg.pth").write_text(str(repo / "src") + "\n", encoding="utf-8")

            (repo / ".ai").mkdir()
            (repo / ".ai" / "worktree.json").write_text(
                json.dumps({
                    "copy": [],
                    "link": [],
                    "setup": [],
                    "venv": "auto"
                }),
                encoding="utf-8"
            )

            wt_dir = repo / ".worktrees" / "venv-wt"
            res = subprocess.run(
                [NODE, str(WRAPPER), "add", str(wt_dir), "venv-branch"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}, stderr: {res.stderr}")
            self.assertIn("[worktree] venv: overlay", res.stdout)
            self.assertTrue((wt_dir / ".venv").is_dir())

            # Find overlay python interpreter
            wt_py = wt_dir / ".venv" / "bin" / "python"
            if not wt_py.exists():
                wt_py = wt_dir / ".venv" / "Scripts" / "python.exe"
            self.assertTrue(wt_py.exists())

            # Test import mypkg
            check_res = subprocess.run(
                [str(wt_py), "-c", "import mypkg; print(mypkg.__file__)"],
                cwd=wt_dir,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_res.returncode, 0, f"stdout: {check_res.stdout}, stderr: {check_res.stderr}")

            self.assertTrue(check_res.stdout.strip().startswith(str(wt_dir / "src")))

            # Also check uv run --no-sync if uv available
            uv_bin = shutil.which("uv")
            if uv_bin:
                uv_res = subprocess.run(
                    [uv_bin, "run", "--no-sync", "python", "-c", "import mypkg; print(mypkg.__file__)"],
                    cwd=wt_dir,
                    capture_output=True,
                    text=True,
                )
                if uv_res.returncode == 0:
                    self.assertTrue(uv_res.stdout.strip().startswith(str(wt_dir / "src")))

    def test_bootstrap_installs_worktree(self) -> None:
        from guides.bootstrap import run_bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertTrue((workspace / ".ai" / "worktree.mjs").is_file())
            self.assertTrue((workspace / ".ai" / "worktree.json").is_file())
            data = json.loads((workspace / ".ai" / "worktree.json").read_text(encoding="utf-8"))
            self.assertEqual(data["venv"], "auto")


def _run_wt(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(WRAPPER), *args], cwd=repo, capture_output=True, text=True)


def _write_config(repo: Path, cfg: dict) -> None:
    (repo / ".ai").mkdir(exist_ok=True)
    (repo / ".ai" / "worktree.json").write_text(json.dumps(cfg), encoding="utf-8")


class TestWorktreeSafety(unittest.TestCase):
    def test_copy_does_not_overwrite_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            (repo / ".env").write_text("MAIN=1\n", encoding="utf-8")
            _write_config(repo, {"copy": [".env"], "link": [], "setup": [], "venv": "none"})
            wt = repo / ".worktrees" / "keep-wt"
            res = _run_wt(repo, "add", str(wt), "--detach", "HEAD")
            self.assertEqual(res.returncode, 0, res.stderr)
            wt_env = wt / ".env"
            self.assertEqual(wt_env.read_text(encoding="utf-8"), "MAIN=1\n")
            # sync nie nadpisuje istniejącego pliku w worktree
            wt_env.write_text("WT=2\n", encoding="utf-8")
            res_sync = _run_wt(repo, "sync", str(wt))
            self.assertEqual(res_sync.returncode, 0, res_sync.stderr)
            self.assertEqual(wt_env.read_text(encoding="utf-8"), "WT=2\n")

    def test_link_with_existing_destination_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            (repo / "node_modules").mkdir()
            _write_config(repo, {"copy": [], "link": ["node_modules"], "setup": [], "venv": "none"})
            wt = repo / ".worktrees" / "link-wt"
            res = _run_wt(repo, "add", str(wt), "--detach", "HEAD", "--plain")
            self.assertEqual(res.returncode, 0, res.stderr)
            # Cel już istnieje w worktree (lokalny katalog) — link go nie zastępuje
            (wt / "node_modules").mkdir()
            res_sync = _run_wt(repo, "sync", str(wt))
            self.assertEqual(res_sync.returncode, 0, res_sync.stderr)
            self.assertTrue((wt / "node_modules").is_dir())
            self.assertFalse((wt / "node_modules").is_symlink())

    def test_paths_outside_repo_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            (Path(tmp) / "x").write_text("outside\n", encoding="utf-8")
            _write_config(repo, {"copy": ["../x"], "link": ["../x"], "setup": [], "venv": "none"})
            wt = repo / ".worktrees" / "escape-wt"
            res = _run_wt(repo, "add", str(wt), "--detach", "HEAD")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("pominięto copy poza repo: ../x", res.stdout)
            self.assertIn("pominięto link poza repo: ../x", res.stdout)
            self.assertFalse((repo / ".worktrees" / "x").exists())

    def test_remove_refuses_main_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            # .venv ignorowany, żeby główne drzewo było czyste (test ma dotykać gałęzi "główny checkout")
            (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "ignore venv"], cwd=repo, check=True, capture_output=True)
            venv = repo / ".venv"
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "marker").write_text("keep\n", encoding="utf-8")
            res = _run_wt(repo, "remove", ".")
            self.assertEqual(res.returncode, 2)
            self.assertTrue((venv / "bin" / "marker").is_file())
            self.assertTrue((repo / ".git").exists())

    def test_sync_refuses_main_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            res = _run_wt(repo, "sync", ".")
            self.assertEqual(res.returncode, 2)

    def test_prune_keeps_dirty_foreign_and_uncommitted_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)

            def make_merged(wt: Path, branch: str) -> None:
                res = _run_wt(repo, "add", str(wt), branch, "--plain")
                self.assertEqual(res.returncode, 0, res.stderr)
                (wt / f"{branch}.txt").write_text("c\n", encoding="utf-8")
                subprocess.run(["git", "add", "."], cwd=wt, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", branch], cwd=wt, check=True, capture_output=True)
                subprocess.run(["git", "merge", "--ff-only", branch], cwd=repo, check=True, capture_output=True)

            dirty = repo / ".worktrees" / "dirty-wt"
            make_merged(dirty, "dirty-branch")
            (dirty / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")

            foreign = Path(tmp) / "foreign-wt"
            make_merged(foreign, "foreign-branch")

            empty = repo / ".worktrees" / "empty-wt"
            res = _run_wt(repo, "add", str(empty), "empty-branch", "--plain")
            self.assertEqual(res.returncode, 0, res.stderr)

            res_prune = _run_wt(repo, "prune")
            self.assertEqual(res_prune.returncode, 0, res_prune.stderr)
            self.assertTrue(dirty.exists())
            self.assertTrue(foreign.exists())
            self.assertTrue(empty.exists())
            self.assertIn("niezacommitowane zmiany", res_prune.stdout)
            self.assertIn("nie jest worktree kita", res_prune.stdout)
            self.assertIn("bez własnych commitów", res_prune.stdout)

    def test_add_remote_only_branch_uses_dwim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _init_git_repo(repo)
            bare = Path(tmp) / "origin.git"
            subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "push", "-q", "origin", "HEAD:refs/heads/remote-only"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True, capture_output=True)
            wt = repo / ".worktrees" / "remote-only"
            res = _run_wt(repo, "add", str(wt), "remote-only", "--plain")
            self.assertEqual(res.returncode, 0, res.stderr)
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=wt, capture_output=True, text=True).stdout.strip()
            self.assertEqual(branch, "remote-only")
