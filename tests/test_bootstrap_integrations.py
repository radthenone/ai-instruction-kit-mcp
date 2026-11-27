"""Testy integracyjne ``scripts/bootstrap-project.sh``: narzędzie MCP, guardy, integracje i shimy Pythona."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_bootstrap import KIT_ROOT, _BootstrapTestCase, _snapshot

from guides import server
from guides.bootstrap import build_args, find_bash, run_bootstrap


class TestOrcaIntegration(_BootstrapTestCase, unittest.TestCase):
    """Wpis `orca` w Profilu: bootstrap tworzy orca.yaml, `--remove` usuwa wyrenderowany plik (#456)."""

    def _add_orca_to_profile(self, workspace: Path) -> None:
        profile = workspace / ".ai" / "project.profile.yaml"
        text = profile.read_text(encoding="utf-8")
        self.assertIn("integrations: []", text)
        profile.write_text(text.replace("integrations: []", "integrations:\n  - orca"), encoding="utf-8")

    def test_orca_yaml_rendered_only_when_listed_in_profile(self) -> None:
        """orca.yaml powstaje tylko przy wpisie `orca` w Profilu; bez wpisu bootstrap go nie tworzy."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            self.assertFalse((workspace / "orca.yaml").exists())

            self._add_orca_to_profile(workspace)
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertIn("node .ai/worktree.mjs sync .", (workspace / "orca.yaml").read_text(encoding="utf-8"))

    def test_remove_deletes_orca_yaml_rendered_by_kit(self) -> None:
        """`--remove` usuwa orca.yaml wyrenderowany przez kit."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            self._add_orca_to_profile(workspace)
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            self.assertTrue((workspace / "orca.yaml").is_file())

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, remove=True)

            self.assertFalse((workspace / "orca.yaml").exists())


class TestServerTool(_BootstrapTestCase, unittest.TestCase):
    """Narzędzie MCP — domyślki, bramka dry-run i odmowy."""

    def setUp(self) -> None:
        super().setUp()
        self._saved = (
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._legacy_config,
        )
        server._kit_root = KIT_ROOT
        server._clients = ["claude"]
        server._legacy_config = False
        self._tmp = tempfile.mkdtemp(prefix="guides-tool-test-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.workspace = Path(self._tmp) / "app"
        self.workspace.mkdir()
        server._workspace_root = self.workspace

    def tearDown(self) -> None:
        (
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._legacy_config,
        ) = self._saved

    def test_default_call_is_dry_run(self) -> None:
        """Bez argumentów narzędzie planuje, nie instaluje."""
        before = _snapshot(self.workspace)
        out = server.bootstrap_workspace()
        self.assertIn("dry run", out)
        self.assertIn(".ai/.kit-bootstrap.json", out)
        self.assertEqual(_snapshot(self.workspace), before)

    def test_explicit_dry_run_false_installs(self) -> None:
        """Zapis wymaga jawnego dry_run=False."""
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("zainstalowano", out)
        self.assertTrue((self.workspace / ".ai" / ".kit-bootstrap.json").is_file())
        self.assertTrue((self.workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())

    def test_report_has_no_empty_sections(self) -> None:
        """Każdy nagłówek `##` w raporcie musi mieć pod sobą wyliczenie."""
        server.bootstrap_workspace(dry_run=False)
        out = server.bootstrap_workspace()

        self.assertIn("Bez zmian:", out)
        self.assertNotIn("## Bez zmian", out)
        lines = out.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("## "):
                continue
            body = [rest for rest in lines[index + 1 :] if rest.strip()]
            self.assertTrue(body and body[0].startswith("- `"), msg=f"pusta sekcja: {line}")

    def test_missing_workspace_errors_instead_of_writing_cwd(self) -> None:
        """Brak --workspace: błąd, a bieżący katalog procesu zostaje nietknięty."""
        server._workspace_root = None
        cwd_sentinel = Path(self._tmp) / "cwd"
        cwd_sentinel.mkdir()
        previous = Path.cwd()
        os.chdir(cwd_sentinel)
        self.addCleanup(os.chdir, previous)

        out = server.bootstrap_workspace(dry_run=False)

        self.assertIn("błąd", out)
        self.assertIn("--workspace", out)
        self.assertEqual(_snapshot(cwd_sentinel), {})

    def test_workspace_equal_to_kit_is_refused(self) -> None:
        """Bootstrap repo kita samym sobą to pomyłka, nie funkcja."""
        server._workspace_root = KIT_ROOT
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("błąd", out)
        self.assertIn("ten sam katalog", out)

    def test_invalid_clients_is_reported_not_raised(self) -> None:
        """Zła wartość --clients wraca jako komunikat narzędzia."""
        out = server.bootstrap_workspace(clients="nieistniejacy-klient")
        self.assertIn("błąd", out)


class TestOpencodeGuards(_BootstrapTestCase, unittest.TestCase):
    """`--clients opencode` kładzie plugin guardów i guardy w `.opencode/` (#166)."""

    def test_opencode_gets_guard_plugin_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
            self.assertTrue((workspace / ".opencode/plugins/kit-guards.js").is_file())
            for guard in ("invoke-hook.js", "git-guard.mjs", "sensitive-files-guard.mjs"):
                with self.subTest(guard=guard):
                    self.assertEqual(
                        (workspace / ".opencode/hooks" / guard).read_bytes(),
                        (KIT_ROOT / "templates/shared/guards" / guard).read_bytes(),
                    )

    def test_dropping_opencode_removes_its_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            self.assertFalse((workspace / ".opencode").exists())


class TestServerGuardInstall(_BootstrapTestCase, unittest.TestCase):
    """Server-guard i jego JSON trafiają do hooków claude, cursor i opencode (#194)."""

    def test_guard_wired_and_config_rendered_for_each_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            (workspace / ".ai/project.profile.yaml").write_text(
                'server:\n  deny:\n    - "bunx eas-cli"\n', encoding="utf-8"
            )
            (workspace / "Taskfile.yml").write_text(
                "version: '3'\ntasks:\n  up:\n    cmds:\n      - docker compose up -d\n", encoding="utf-8"
            )
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor,opencode")
            for hooks in (".claude/hooks", ".cursor/hooks", ".opencode/hooks"):
                with self.subTest(hooks=hooks):
                    self.assertEqual(
                        (workspace / hooks / "server-guard.mjs").read_bytes(),
                        (KIT_ROOT / "templates/shared/guards/server-guard.mjs").read_bytes(),
                    )
                    config = json.loads((workspace / hooks / "server-guard.json").read_text(encoding="utf-8"))
                    self.assertEqual(config["project_deny"], ["bunx eas-cli"])
                    self.assertTrue(any("task up" in w["chain"] for w in config["wrappers"]))
            settings = json.loads((workspace / ".claude/settings.json").read_text(encoding="utf-8"))
            pre = settings["hooks"]["PreToolUse"]
            bash = next(e for e in pre if e["matcher"] == "Bash")
            self.assertTrue(any("server-guard.mjs" in h["command"] for h in bash["hooks"]))
            self.assertTrue(any("playwright" in e["matcher"] and "server-guard.mjs" in e["hooks"][0]["command"] for e in pre))
            self.assertIn("server-guard.mjs", (workspace / ".cursor/hooks.json").read_text(encoding="utf-8"))
            self.assertIn("server-guard.mjs", (workspace / ".opencode/plugins/kit-guards.js").read_text(encoding="utf-8"))


class TestSensitiveGuardBashWiring(_BootstrapTestCase, unittest.TestCase):
    """Sensitive guard widzi Bash tam, gdzie git-guard już go widzi (#231)."""

    def test_shell_reads_wired_for_each_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex,cursor,vscode")

            settings = json.loads((workspace / ".claude/settings.json").read_text(encoding="utf-8"))
            bash = next(e for e in settings["hooks"]["PreToolUse"] if "Bash" in e["matcher"].split("|"))
            self.assertTrue(
                any("sensitive-files-guard.mjs" in h["command"] for h in bash["hooks"]), bash
            )

            codex = json.loads((workspace / ".codex/hooks.json").read_text(encoding="utf-8"))
            bash = next(e for e in codex["hooks"]["PreToolUse"] if "Bash" in e["matcher"].split("|"))
            self.assertTrue(
                any("sensitive-files-guard.mjs" in h["command"] for h in bash["hooks"]), bash
            )

            cursor = json.loads((workspace / ".cursor/hooks.json").read_text(encoding="utf-8"))
            shell_guards = [h["command"] for h in cursor["hooks"]["beforeShellExecution"]]
            self.assertTrue(
                any("sensitive-files-guard.mjs" in c for c in shell_guards), shell_guards
            )

            # VS Code: hooki PreToolUse bez matchera widzą wszystkie narzędzia, także Bash.
            copilot = json.loads(
                (workspace / ".github/hooks/kit-guards.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                any("sensitive-files-guard.mjs" in e["command"] for e in copilot["hooks"]["PreToolUse"]),
                copilot,
            )


class TestOpencodeDefaultModelE2E(_BootstrapTestCase, unittest.TestCase):
    """Test dymny E2E dziedziczenia ``model`` z globalnego configu OpenCode (#167)."""

    def test_opencode_inherits_global_model_e2e(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            (home / "opencode").mkdir(parents=True)
            (home / "opencode" / "opencode.jsonc").write_text(
                '{\n  // domyślny\n  "model": "opencode/muse-spark",\n}\n',
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home)}):
                run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
            data = json.loads((workspace / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "opencode/muse-spark")


# Atrapy shimów pyenv-win (podmieniane na PATH tylko w teście, `{real}` = prawdziwy Python).
_PLAIN_SHIM = """#!/bin/sh
exec "{real}" "$@"
"""

# Wielolinijkowe `-c` nie przechodzi przez shim, reszta idzie do prawdziwego Pythona.
_MULTILINE_BREAKING_SHIM = """#!/bin/sh
NL='
'
for arg in "$@"; do
  case "$arg" in *"$NL"*) echo "shim: wielolinijkowe -c" >&2; exit 97 ;; esac
done
exec "{real}" "$@"
"""

# `command -v` go widzi, ale uruchomić się nie da (pyenv-win bez zainstalowanej wersji).
_DEAD_SHIM = """#!/bin/sh
echo "'python3' is not recognized as an internal or external command" >&2
exit 1
"""


class TestPythonShimResolution(_BootstrapTestCase, unittest.TestCase):
    """Bootstrap uruchomiony bez KIT_PYTHON nie może ufać shimom `python3` / `python` (#420)."""

    def _run_with_shims(self, workspace: Path, shims: dict[str, str]) -> subprocess.CompletedProcess:
        shim_dir = workspace.parent / "shim"
        shim_dir.mkdir()
        real = Path(sys.executable).as_posix()
        for name, body in shims.items():
            path = shim_dir / name
            path.write_text(body.format(real=real), encoding="utf-8", newline="\n")
            path.chmod(0o755)
        argv = build_args(kit_root=KIT_ROOT, target=workspace, clients="claude")
        new_path = os.pathsep.join([str(shim_dir), os.environ.get("PATH", "")])
        with mock.patch.dict(os.environ, {"PATH": new_path}):
            os.environ.pop("KIT_PYTHON", None)
            os.environ.pop("KIT_WORKSPACE", None)
            return subprocess.run(
                [find_bash(), "--noprofile", "--norc", *argv],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                check=False,
            )

    def test_bootstrap_runs_through_python3_shim_that_breaks_multiline_c(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            result = self._run_with_shims(workspace, {"python3": _MULTILINE_BREAKING_SHIM})

            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertTrue((workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())

    def test_bootstrap_skips_python3_that_does_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            result = self._run_with_shims(
                workspace, {"python3": _DEAD_SHIM, "python": _PLAIN_SHIM}
            )

            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertTrue((workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
