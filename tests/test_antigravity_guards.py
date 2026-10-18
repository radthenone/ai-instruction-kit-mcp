"""Antigravity guardy przez PreToolUse hooks (#201).

Bootstrap: `--clients antigravity` kładzie guardy kita w `.agents/hooks/` oraz
workspace'owy `.agents/hooks.json` — nazwany hook `kit-guards` z matcherami
`run_command`, `call_mcp_tool|^mcp_` i narzędziami plikowymi. `.agents/hooks.json` dzielimy
z użytkownikiem (własne hooki), więc scala się tylko klucz kita, a `prune`
zdejmuje wyłącznie ten klucz. Adapter `invoke-hook.js --to antigravity`
przyjmuje payload PreToolUse Antigravity (`toolCall.name` + `toolCall.args`)
i zwraca decyzję w kontrakcie Antigravity (`{"decision": ..., "reason": ...}`).
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
HOOKS_TEMPLATE = KIT_ROOT / "templates" / "antigravity" / "hooks.json"
NODE = shutil.which("node")
# Czyste środowisko hosta: tylko KIT_HOST_PROFILE decyduje (jak w test_guards).
VPS = {"GUIDES_HOST_PROFILE": "", "UV_NO_SYNC": ""}


def _raw_hook(script: str, payload: dict, env: dict | None = None) -> str:
    """Odpal `node invoke-hook.js <script> --to antigravity`; surowy stdout."""
    proc = subprocess.run(
        [NODE or "node", str(GUARDS / "invoke-hook.js"), script, "--to", "antigravity"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    assert proc.returncode == 0, f"{script}: exit {proc.returncode}: {proc.stderr}"
    return proc.stdout.strip()


def _run_hook(script: str, payload: dict, env: dict | None = None) -> dict:
    """Sparsowany stdout adaptera (`{decision, reason}`); pusty = `{}`."""
    out = _raw_hook(script, payload, env)
    return json.loads(out) if out else {}


def _antigravity(tool_name: str, args: dict) -> dict:
    """Payload PreToolUse w kształcie Antigravity (camelCase, `toolCall`)."""
    return {
        "conversationId": "c-test",
        "workspacePaths": [str(KIT_ROOT)],
        "transcriptPath": "/tmp/transcript.jsonl",
        "artifactDirectoryPath": "/tmp/artifacts",
        "modelName": "gemini-3.6-flash-medium",
        "toolCall": {"name": tool_name, "args": args},
        "stepIdx": 3,
    }


def _mcp(server: str, tool: str, arguments: dict) -> dict:
    return _antigravity(
        "call_mcp_tool",
        {"ServerName": server, "ToolName": tool, "Arguments": arguments, "toolAction": "x"},
    )


@unittest.skipUnless(NODE, "brak node")
class AntigravityInvokeHookAdapterTest(unittest.TestCase):
    """Adapter `--to antigravity` — deny i allow na payloadach PreToolUse."""

    def test_git_guard_deny_push_master(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            _antigravity("run_command", {"CommandLine": "git push origin master", "Cwd": str(KIT_ROOT)}),
        )
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("git-guard", out.get("reason", ""))

    def test_git_guard_allow_push_feat(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            _antigravity("run_command", {"CommandLine": "git push origin feat/x"}),
        )
        self.assertEqual(out.get("decision"), "allow")

    def test_allow_output_has_no_claude_contract(self) -> None:
        """Antigravity czyta `{decision, reason}` — nie kontrakt Claude Code."""
        raw = json.loads(
            _raw_hook("git-guard.mjs", _antigravity("run_command", {"CommandLine": "git status"}))
        )
        self.assertEqual(raw.get("decision"), "allow")
        self.assertNotIn("hookSpecificOutput", raw)

    def test_run_command_without_commandline_denied(self) -> None:
        out = _run_hook("git-guard.mjs", _antigravity("run_command", {"Cwd": str(KIT_ROOT)}))
        self.assertEqual(out.get("decision"), "deny")

    def test_sensitive_guard_deny_env_view(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _antigravity("view_file", {"AbsolutePath": "/repo/.env"}))
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn(".env", out.get("reason", ""))

    def test_sensitive_guard_deny_env_write(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _antigravity("write_to_file", {"TargetFile": "app/.env", "CodeContent": ""}),
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_sensitive_guard_deny_env_replace_tools(self) -> None:
        for tool in ("replace_file_content", "multi_replace_file_content"):
            with self.subTest(tool=tool):
                out = _run_hook(
                    "sensitive-files-guard.mjs",
                    _antigravity(tool, {"TargetFile": "app/.env"}),
                )
                self.assertEqual(out.get("decision"), "deny")

    def test_sensitive_guard_deny_lockfile_write(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _antigravity("write_to_file", {"TargetFile": "uv.lock"}),
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_sensitive_guard_allow_source_file(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _antigravity("view_file", {"AbsolutePath": "/repo/src/app.py"}),
        )
        self.assertEqual(out.get("decision"), "allow")

    def test_file_tool_without_path_denied(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _antigravity("view_file", {}))
        self.assertEqual(out.get("decision"), "deny")

    def test_server_guard_deny_docker_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _antigravity("run_command", {"CommandLine": "docker compose up"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "deny")
        self.assertIn("server-guard", out.get("reason", ""))

    def test_server_guard_allow_docker_on_local(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _antigravity("run_command", {"CommandLine": "docker compose up"}),
            env={**VPS, "KIT_HOST_PROFILE": "local"},
        )
        self.assertEqual(out.get("decision"), "allow")

    def test_server_guard_deny_playwright_mcp_on_vps(self) -> None:
        """Antigravity (agy 1.3.0) woła MCP jednym narzędziem `call_mcp_tool`
        z `ServerName`/`ToolName`/`Arguments` — payload złapany z żywej sesji."""
        out = _run_hook(
            "server-guard.mjs",
            _mcp("playwright", "browser_click", {"element": "button"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_server_guard_other_mcp_allowed_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _mcp("context7", "resolve-library-id", {"libraryName": "react"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "allow")

    def test_server_guard_deny_prefixed_playwright_mcp_on_vps(self) -> None:
        """Na wypadek nazw `mcp_<server>_<tool>` (IDE / przyszłe wersje) — matcher `^mcp_`."""
        out = _run_hook(
            "server-guard.mjs",
            _antigravity("mcp_playwright_browser_click", {"element": "button"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_server_guard_other_prefixed_mcp_allowed_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _antigravity("mcp_github_create_issue", {"title": "x"}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "allow")

    def test_mcp_without_server_name_denied(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _antigravity("call_mcp_tool", {"ToolName": "browser_click", "Arguments": {}}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_sensitive_guard_deny_env_edit_file(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _antigravity("edit_file", {"TargetFile": str(KIT_ROOT / ".env")}),
        )
        self.assertEqual(out.get("decision"), "deny")

    def test_missing_policy_file_fails_closed(self) -> None:
        out = _run_hook("nie-ma-takiego.sh", _antigravity("run_command", {"CommandLine": "git status"}))
        self.assertEqual(out.get("decision"), "deny")


@unittest.skipUnless(NODE and resolve_bash(), "brak node lub bash")
class AntigravityBootstrapGuardsTest(unittest.TestCase):
    """`--clients antigravity` kładzie hooki i guardy w `.agents/`."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI")
            self.skipTest("brak bash")

    def _install(self, clients: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="antigravity-guards-"))
        workspace = tmp / "app"
        workspace.mkdir()
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)
        return workspace

    def test_antigravity_gets_guards_and_server_guard_json(self) -> None:
        workspace = self._install("antigravity")
        hooks = workspace / ".agents" / "hooks"
        self.assertTrue((hooks / "invoke-hook.js").is_file(), hooks)
        for guard in ("git-guard.mjs", "server-guard.mjs", "sensitive-files-guard.mjs"):
            with self.subTest(guard=guard):
                self.assertTrue((hooks / guard).is_file(), guard)
                self.assertEqual((hooks / guard).read_bytes(), (GUARDS / guard).read_bytes())
        self.assertEqual((hooks / "invoke-hook.js").read_bytes(), (GUARDS / "invoke-hook.js").read_bytes())
        # server-guard.json renderowany obok guarda (decyzja VPS/Local w runtime).
        self.assertTrue((hooks / "server-guard.json").is_file(), hooks)
        # Guardy tylko dla Claude nie trafiają do Antigravity.
        self.assertFalse((hooks / "bash-guard.mjs").exists())

    def test_kit_marker_points_at_installed_file(self) -> None:
        from guides.cli import CLIENT_KIT_MARKERS

        workspace = self._install("antigravity")
        self.assertTrue((workspace / CLIENT_KIT_MARKERS["antigravity"]).is_file(), CLIENT_KIT_MARKERS)

    def test_hooks_json_is_parity_with_template_when_absent(self) -> None:
        workspace = self._install("antigravity")
        installed = workspace / ".agents" / "hooks.json"
        self.assertTrue(installed.is_file(), installed)
        self.assertEqual(installed.read_bytes(), HOOKS_TEMPLATE.read_bytes())

    def test_hooks_json_wires_guards(self) -> None:
        workspace = self._install("antigravity")
        data = json.loads((workspace / ".agents" / "hooks.json").read_text(encoding="utf-8"))
        pre = data["kit-guards"]["PreToolUse"]
        matchers = [entry["matcher"] for entry in pre]
        self.assertIn("run_command", matchers)
        self.assertIn("call_mcp_tool|^mcp_", matchers)
        file_matcher = next(m for m in matchers if "view_file" in m)
        # Zakotwiczony: `view_file` nie może łapać `view_file_outline` itp.
        self.assertTrue(file_matcher.startswith("^(") and file_matcher.endswith(")$"), file_matcher)
        file_tools = set(file_matcher[2:-2].split("|"))
        for tool in ("view_file", "write_to_file", "replace_file_content", "multi_replace_file_content", "edit_file"):
            with self.subTest(tool=tool):
                self.assertIn(tool, file_tools)
        commands = " ".join(h["command"] for entry in pre for h in entry["hooks"])
        self.assertIn("--to antigravity", commands)
        self.assertIn("invoke-hook.js", commands)
        for guard in ("git-guard.mjs", "server-guard.mjs", "sensitive-files-guard.mjs"):
            with self.subTest(guard=guard):
                self.assertIn(guard, commands)

    def test_server_guard_wired_for_command_and_mcp(self) -> None:
        workspace = self._install("antigravity")
        pre = json.loads((workspace / ".agents" / "hooks.json").read_text(encoding="utf-8"))[
            "kit-guards"
        ]["PreToolUse"]
        cmd_entry = next(e for e in pre if e["matcher"] == "run_command")
        self.assertTrue(any("server-guard.mjs" in h["command"] for h in cmd_entry["hooks"]), cmd_entry)
        mcp_entry = next(e for e in pre if e["matcher"] == "call_mcp_tool|^mcp_")
        self.assertTrue(any("server-guard.mjs" in h["command"] for h in mcp_entry["hooks"]), mcp_entry)

    def test_reinstall_merges_kit_key_without_clobbering_user_hooks(self) -> None:
        workspace = self._install("antigravity")
        path = workspace / ".agents" / "hooks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["moj-hook"] = {
            "PreToolUse": [
                {"matcher": "run_command", "hooks": [{"type": "command", "command": "./moj.sh"}]}
            ]
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="antigravity")

        merged = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("moj-hook", merged)
        self.assertIn("kit-guards", merged)
        template = json.loads(HOOKS_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(merged["kit-guards"], template["kit-guards"])

    def test_dropping_antigravity_removes_guards_and_kit_key(self) -> None:
        workspace = self._install("antigravity")
        self.assertTrue((workspace / ".agents" / "hooks" / "git-guard.mjs").is_file())
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
        self.assertFalse((workspace / ".agents" / "hooks").exists())
        self.assertFalse((workspace / ".agents" / "hooks.json").exists())
        self.assertFalse((workspace / ".agents").exists())

    def test_dropping_antigravity_keeps_user_hooks(self) -> None:
        workspace = self._install("antigravity")
        path = workspace / ".agents" / "hooks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["moj-hook"] = {
            "PreToolUse": [
                {"matcher": "run_command", "hooks": [{"type": "command", "command": "./moj.sh"}]}
            ]
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

        self.assertTrue(path.is_file())
        kept = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("moj-hook", kept)
        self.assertNotIn("kit-guards", kept)

    def test_other_clients_do_not_get_antigravity_guard_hooks(self) -> None:
        workspace = self._install("claude")
        self.assertFalse((workspace / ".agents" / "hooks" / "git-guard.mjs").exists())
        self.assertFalse((workspace / ".agents" / "hooks.json").exists())


if __name__ == "__main__":
    unittest.main()


class AntigravityReadmeTest(unittest.TestCase):
    """README opisuje to, co faktycznie leży w `.agents/hooks.json` (#201)."""

    def setUp(self) -> None:
        self.readme = (KIT_ROOT / "README.md").read_text(encoding="utf-8")

    def test_adapter_row_uses_hooks_json_cwd(self) -> None:
        row = next(line for line in self.readme.splitlines() if line.startswith("| Antigravity | `node "))
        self.assertIn("`node hooks/invoke-hook.js <guard>.mjs --to antigravity`", row)

    def test_matchers_match_template(self) -> None:
        pre = json.loads(HOOKS_TEMPLATE.read_text(encoding="utf-8"))["kit-guards"]["PreToolUse"]
        for entry in pre:
            with self.subTest(matcher=entry["matcher"]):
                self.assertIn(f"`{entry['matcher'].replace('|', chr(92) + '|')}`", self.readme)

    def test_documents_unmapped_tools_gap(self) -> None:
        for tool in ("grep_search", "view_file_outline", "view_code_item"):
            with self.subTest(tool=tool):
                self.assertIn(f"`{tool}`", self.readme)
