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


def _run_hook(script: str, payload: dict, env: dict | None = None) -> dict:
    """Odpal `node invoke-hook.js <script> --to copilot` z payloadem na stdin."""
    proc = subprocess.run(
        [NODE or "node", str(GUARDS / "invoke-hook.js"), script, "--to", "copilot"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    assert proc.returncode == 0, f"{script}: exit {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
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

    def test_git_guard_allow_push_feature_branch(self) -> None:
        out = _run_hook("git-guard.mjs", _copilot("Bash", {"command": "git push origin feat/x"}))
        self.assertEqual(out.get("permissionDecision"), "allow")

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

    def test_sensitive_guard_allow_source_file(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _copilot("Read", {"file_path": "src/app.py"}))
        self.assertEqual(out.get("permissionDecision"), "allow")

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
