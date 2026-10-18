"""VS Code (Copilot) guardy przez `.github/hooks/` (#200).

Bootstrap: `--clients vscode` kładzie `.github/hooks/kit-guards.json` + guardy w
`.github/hooks/`, parytet z templates/shared/guards, a `rtk-rewrite.json` zostaje
nietknięty. Adapter `invoke-hook.js --to copilot` przyjmuje payload PreToolUse w
kształcie VS Code/Copilota i zwraca decyzję w kontrakcie Claude Code
(`hookSpecificOutput.permissionDecision`) — hooki PascalCase `PreToolUse` czytają
ten sam kształt w VS Code Local i w Copilot CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, resolve_bash

from guides.bootstrap import run_bootstrap

KIT_ROOT = Path(__file__).resolve().parents[1]
GUARDS = KIT_ROOT / "templates" / "shared" / "guards"
HOOKS_TEMPLATE = KIT_ROOT / "templates" / "vscode" / "github" / "hooks" / "kit-guards.json"
NODE = shutil.which("node")
# Czyste środowisko hosta: tylko KIT_HOST_PROFILE decyduje (jak w test_guards).
VPS = {"GUIDES_HOST_PROFILE": "", "UV_NO_SYNC": ""}


def _raw_hook(script: str, payload: dict, env: dict | None = None) -> str:
    """Odpal `node invoke-hook.js <script> --to copilot` z payloadem na stdin; surowy stdout."""
    proc = subprocess.run(
        [NODE or "node", str(GUARDS / "invoke-hook.js"), script, "--to", "copilot"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    assert proc.returncode == 0, f"{script}: exit {proc.returncode}: {proc.stderr}"
    return proc.stdout.strip()


def _run_hook(script: str, payload: dict, env: dict | None = None) -> dict:
    """`hookSpecificOutput` z wyjścia adaptera; pusty stdout (brak opinii) = `{}`."""
    out = _raw_hook(script, payload, env)
    if not out:
        return {}
    return json.loads(out).get("hookSpecificOutput", {})


def _copilot(tool_name: str, tool_input) -> dict:
    """Payload PreToolUse w kształcie VS Code/Copilota (PascalCase, snake_case)."""
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "s-test",
        "timestamp": "2026-10-18T00:00:00Z",
        "cwd": str(KIT_ROOT),
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


@unittest.skipUnless(NODE, "brak node")
class CopilotInvokeHookAdapterTest(unittest.TestCase):
    """Adapter `--to copilot` — deny i allow na payloadach PreToolUse Copilota."""

    def test_git_guard_deny_push_master(self) -> None:
        out = _run_hook("git-guard.mjs", _copilot("Bash", {"command": "git push origin master"}))
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("git-guard", out.get("permissionDecisionReason", ""))

    def test_git_guard_allow_is_empty_output(self) -> None:
        """`allow` w VS Code = auto-approve; adapter milczy, natywne potwierdzenia zostają."""
        out = _raw_hook("git-guard.mjs", _copilot("Bash", {"command": "git push origin feat/x"}))
        self.assertEqual(out, "")

    def test_runtime_tool_name_is_normalized(self) -> None:
        """Copilot CLI podaje runtime `bash`; guard rozumie tylko `Bash`."""
        out = _run_hook("git-guard.mjs", _copilot("bash", {"command": "git push origin master"}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_tool_input_as_json_string_is_parsed(self) -> None:
        """`tool_input` może przyjść jako string JSON — inaczej guard nie widzi `command`."""
        out = _run_hook(
            "git-guard.mjs",
            _copilot("bash", json.dumps({"command": "git push origin master"})),
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_camelcase_payload_is_normalized(self) -> None:
        """Copilot CLI z konfiguracją camelCase: `toolName` + `toolArgs`."""
        out = _run_hook(
            "git-guard.mjs",
            {
                "hook_event_name": "preToolUse",
                "sessionId": "s-test",
                "timestamp": 0,
                "cwd": str(KIT_ROOT),
                "toolName": "bash",
                "toolArgs": {"command": "git push origin master"},
            },
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_sensitive_guard_deny_env_read(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _copilot("Read", {"file_path": ".env"}))
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn(".env", out.get("permissionDecisionReason", ""))

    def test_sensitive_guard_deny_env_write_camelcase_args(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _copilot("edit", {"filePath": "app/.env"}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_vscode_agent_tool_names_are_normalized(self) -> None:
        """VS Code agent mode: `read_file`/`create_file`/`replace_string_in_file` z `filePath`."""
        for tool in ("read_file", "create_file", "replace_string_in_file", "insert_edit_into_file"):
            with self.subTest(tool=tool):
                out = _run_hook("sensitive-files-guard.mjs", _copilot(tool, {"filePath": "app/.env"}))
                self.assertEqual(out.get("permissionDecision"), "deny")
        out = _run_hook(
            "git-guard.mjs", _copilot("run_in_terminal", {"command": "git push origin master"})
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_sensitive_guard_allow_source_file(self) -> None:
        out = _raw_hook("sensitive-files-guard.mjs", _copilot("Read", {"file_path": "src/app.py"}))
        self.assertEqual(out, "")

    def test_deny_has_top_level_and_hook_specific_output(self) -> None:
        """Nadzbiór: top-level `permissionDecision` (Copilot CLI) + `hookSpecificOutput` (VS Code)."""
        raw = json.loads(
            _raw_hook("git-guard.mjs", _copilot("Bash", {"command": "git push origin master"}))
        )
        self.assertEqual(raw.get("permissionDecision"), "deny")
        self.assertIn("git-guard", raw.get("permissionDecisionReason", ""))
        self.assertEqual(raw["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_file_tool_without_path_denied(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _copilot("read_file", {}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_multi_replace_checks_every_path(self) -> None:
        payload = _copilot(
            "multi_replace_string_in_file",
            {"replacements": [{"filePath": "src/a.py"}, {"filePath": "app/.env"}]},
        )
        out = _run_hook("sensitive-files-guard.mjs", payload)
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn(".env", out.get("permissionDecisionReason", ""))
        safe = _copilot(
            "multi_replace_string_in_file",
            {"replacements": [{"filePath": "src/a.py"}, {"filePath": "src/b.py"}]},
        )
        self.assertEqual(_raw_hook("sensitive-files-guard.mjs", safe), "")

    def test_multi_replace_without_paths_denied(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _copilot("multi_replace_string_in_file", {"replacements": []}),
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_apply_patch_env_denied(self) -> None:
        patch = "*** Begin Patch\n*** Update File: src/a.py\n*** Add File: app/.env\n*** End Patch"
        out = _run_hook("sensitive-files-guard.mjs", _copilot("apply_patch", {"input": patch}))
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn(".env", out.get("permissionDecisionReason", ""))
        safe = "*** Begin Patch\n*** Update File: src/a.py\n*** End Patch"
        self.assertEqual(
            _raw_hook("sensitive-files-guard.mjs", _copilot("apply_patch", {"input": safe})), ""
        )

    def test_create_and_run_task_is_bash(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            _copilot("create_and_run_task", {"task": {"command": "git push origin master"}}),
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_sensitive_guard_deny_lockfile_write(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _copilot("Write", {"path": "uv.lock"}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_server_guard_deny_docker_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _copilot("Bash", {"command": "docker compose up"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("server-guard", out.get("permissionDecisionReason", ""))

    def test_server_guard_allow_docker_on_local(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _copilot("Bash", {"command": "docker compose up"}),
            env={**VPS, "KIT_HOST_PROFILE": "local"},
        )
        self.assertNotEqual(out.get("permissionDecision"), "deny")

    def test_server_guard_deny_playwright_mcp_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _copilot("mcp__playwright__browser_click", {}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_server_guard_deny_vscode_playwright_mcp_name_on_vps(self) -> None:
        """VS Code nazywa narzędzia MCP `mcp_<server>_<tool>` (jedno podkreślenie)."""
        out = _run_hook(
            "server-guard.mjs",
            _copilot("mcp_playwright_browser_navigate", {"url": "http://x"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")


@unittest.skipUnless(NODE and resolve_bash(), "brak node lub bash")
class VscodeBootstrapGuardsTest(unittest.TestCase):
    """`--clients vscode` kładzie hooki i guardy w `.github/hooks/`."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI")
            self.skipTest("brak bash")

    def _install(self, clients: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="vscode-guards-"))
        workspace = tmp / "app"
        workspace.mkdir()
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)
        return workspace

    def test_vscode_gets_guard_hooks_and_guards(self) -> None:
        workspace = self._install("vscode")
        hooks = workspace / ".github" / "hooks"
        self.assertTrue((hooks / "invoke-hook.js").is_file(), hooks)
        for guard in ("git-guard.mjs", "server-guard.mjs", "sensitive-files-guard.mjs"):
            with self.subTest(guard=guard):
                self.assertTrue((hooks / guard).is_file(), guard)
                self.assertEqual((hooks / guard).read_bytes(), (GUARDS / guard).read_bytes())
        self.assertEqual(
            (hooks / "invoke-hook.js").read_bytes(),
            (GUARDS / "invoke-hook.js").read_bytes(),
        )
        # server-guard.json renderowany obok guarda (decyzja VPS/Local w runtime).
        self.assertTrue((hooks / "server-guard.json").is_file(), hooks)

    def test_vscode_guard_hooks_file_is_parity_with_template(self) -> None:
        workspace = self._install("vscode")
        installed = workspace / ".github" / "hooks" / "kit-guards.json"
        self.assertTrue(installed.is_file(), installed)
        self.assertEqual(installed.read_bytes(), HOOKS_TEMPLATE.read_bytes())
        data = json.loads(installed.read_text(encoding="utf-8"))
        commands = " ".join(
            entry["command"] for entry in data["hooks"]["PreToolUse"]
        )
        self.assertIn("invoke-hook.js", commands)
        self.assertIn("--to copilot", commands)
        for guard in ("git-guard.mjs", "server-guard.mjs", "sensitive-files-guard.mjs"):
            with self.subTest(guard=guard):
                self.assertIn(guard, commands)

    def test_rtk_rewrite_hook_is_untouched(self) -> None:
        workspace = self._install("vscode")
        installed = workspace / ".github" / "hooks" / "rtk-rewrite.json"
        source = KIT_ROOT / "templates" / "vscode" / "github" / "hooks" / "rtk-rewrite.json"
        self.assertEqual(installed.read_bytes(), source.read_bytes())
        self.assertIn("rtk hook copilot", installed.read_text(encoding="utf-8"))

    def test_other_clients_do_not_get_copilot_guard_hooks(self) -> None:
        workspace = self._install("claude")
        self.assertFalse((workspace / ".github" / "hooks" / "kit-guards.json").exists())

    def test_dropping_vscode_removes_its_guards(self) -> None:
        workspace = self._install("vscode")
        self.assertTrue((workspace / ".github" / "hooks" / "git-guard.mjs").is_file())
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
        self.assertFalse((workspace / ".github" / "hooks").exists())


if __name__ == "__main__":
    unittest.main()
