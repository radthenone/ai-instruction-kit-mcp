"""Codex guardy przez PreToolUse hooks (#199).

Bootstrap: `--clients codex` kładzie `.codex/hooks.json` + guardy w `.codex/hooks/`,
parytet z templates/shared/guards. Adapter `invoke-hook.js --to codex` przyjmuje
payload PreToolUse Codexa i zwraca decyzję w kontrakcie Claude Code
(`hookSpecificOutput.permissionDecision`).
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
NODE = shutil.which("node")
# Czyste środowisko hosta: tylko KIT_HOST_PROFILE decyduje (jak w test_guards).
VPS = {"GUIDES_HOST_PROFILE": "", "UV_NO_SYNC": ""}


def _run_hook(script: str, payload: dict, target: str = "codex", env: dict | None = None) -> dict:
    """Odpal `node invoke-hook.js <script> --to <target>` z payloadem na stdin."""
    proc = subprocess.run(
        [NODE or "node", str(GUARDS / "invoke-hook.js"), script, "--to", target],
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


def _codex(tool_name: str, tool_input: dict) -> dict:
    """Payload PreToolUse w kształcie Codexa."""
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "s-test",
        "cwd": str(KIT_ROOT),
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def _patch(*headers: str) -> str:
    body = "\n".join(f"{h}\n+x" for h in headers)
    return f"*** Begin Patch\n{body}\n*** End Patch\n"


@unittest.skipUnless(NODE, "brak node")
class CodexInvokeHookAdapterTest(unittest.TestCase):
    """Adapter `--to codex` — deny i allow na payloadach PreToolUse Codexa."""

    def test_git_guard_deny_push_master_shell_argv(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            _codex("shell", {"command": ["bash", "-lc", "git push origin master"]}),
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("git-guard", out.get("permissionDecisionReason", ""))

    def test_git_guard_deny_push_master_bash_string(self) -> None:
        out = _run_hook("git-guard.mjs", _codex("Bash", {"command": "git push origin master"}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_git_guard_allow_push_feat(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            _codex("shell", {"command": ["bash", "-lc", "git push origin feat/x"]}),
        )
        self.assertEqual(out.get("permissionDecision"), "allow")

    def test_sensitive_guard_denies_shell_read_of_env(self) -> None:
        # Codex `shell` z argv trafia do guarda jako Bash — odczyt sekretu musi być deny.
        out = _run_hook(
            "sensitive-files-guard.mjs",
            _codex("shell", {"command": ["bash", "-lc", "cat .env"]}),
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn(".env", out.get("permissionDecisionReason", ""))

    def test_shell_without_command_denied(self) -> None:
        out = _run_hook("git-guard.mjs", _codex("shell", {}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_apply_patch_env_denied(self) -> None:
        patch = _patch("*** Update File: src/app.py", "*** Add File: .env")
        out = _run_hook("sensitive-files-guard.mjs", _codex("apply_patch", {"command": patch}))
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn(".env", out.get("permissionDecisionReason", ""))

    def test_apply_patch_delete_key_denied(self) -> None:
        patch = _patch("*** Delete File: certs/server.pem")
        out = _run_hook("sensitive-files-guard.mjs", _codex("apply_patch", {"input": patch}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_apply_patch_src_allowed(self) -> None:
        patch = _patch("*** Update File: src/app.py", "*** Add File: src/new.py")
        out = _run_hook("sensitive-files-guard.mjs", _codex("apply_patch", {"command": patch}))
        self.assertEqual(out.get("permissionDecision"), "allow")

    def test_apply_patch_without_paths_denied(self) -> None:
        out = _run_hook("sensitive-files-guard.mjs", _codex("apply_patch", {"command": "garbage"}))
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_server_guard_deny_docker_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _codex("shell", {"command": ["bash", "-lc", "docker compose up"]}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("server-guard", out.get("permissionDecisionReason", ""))

    def test_server_guard_allow_docker_on_local(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _codex("shell", {"command": ["bash", "-lc", "docker compose up"]}),
            env={**VPS, "KIT_HOST_PROFILE": "local"},
        )
        self.assertNotEqual(out.get("permissionDecision"), "deny")

    def test_server_guard_deny_playwright_mcp_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            _codex("mcp__playwright__browser_click", {}),
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")


@unittest.skipUnless(NODE and resolve_bash(), "brak node lub bash")
class CodexBootstrapGuardsTest(unittest.TestCase):
    """`--clients codex` kładzie hooki i guardy w `.codex/`."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI")
            self.skipTest("brak bash")

    def _install(self, clients: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="codex-guards-"))
        workspace = tmp / "app"
        workspace.mkdir()
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)
        return workspace

    def test_codex_gets_hooks_json_and_guards(self) -> None:
        workspace = self._install("codex")
        hooks = workspace / ".codex" / "hooks"
        self.assertTrue((hooks / "invoke-hook.js").is_file(), hooks)
        for guard in ("git-guard.mjs", "server-guard.mjs", "sensitive-files-guard.mjs"):
            with self.subTest(guard=guard):
                self.assertTrue((hooks / guard).is_file(), guard)
                self.assertEqual(
                    (hooks / guard).read_bytes(),
                    (GUARDS / guard).read_bytes(),
                )
        hooks_json = json.loads((workspace / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        pre = hooks_json["hooks"]["PreToolUse"]
        matchers = {m for entry in pre for m in entry["matcher"].split("|")}
        self.assertIn("Bash", matchers)
        self.assertIn("shell", matchers)
        commands = " ".join(
            h["command"] for entry in pre for h in entry["hooks"]
        )
        self.assertIn("--to codex", commands)
        self.assertIn("invoke-hook.js", commands)

    def test_codex_hooks_json_uses_claude_schema(self) -> None:
        # Codex czyta hooks.json w kontrakcie Claude Code; `failClosed` to klucz Cursora.
        workspace = self._install("codex")
        hooks_json = (workspace / ".codex" / "hooks.json").read_text(encoding="utf-8")
        self.assertNotIn("failClosed", hooks_json)

    def test_server_guard_wired_for_codex(self) -> None:
        workspace = self._install("codex")
        hooks_json = json.loads((workspace / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        pre = hooks_json["hooks"]["PreToolUse"]
        bash_entry = next(e for e in pre if "Bash" in e["matcher"].split("|"))
        self.assertTrue(
            any("server-guard.mjs" in h["command"] for h in bash_entry["hooks"]),
            bash_entry,
        )
        mcp_entry = next(e for e in pre if "playwright" in e["matcher"])
        self.assertTrue(
            any("server-guard.mjs" in h["command"] for h in mcp_entry["hooks"]),
            mcp_entry,
        )

    def test_hook_command_works_from_subdirectory(self) -> None:
        workspace = self._install("codex")
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        sub = workspace / "src" / "deep"
        sub.mkdir(parents=True)
        pre = json.loads((workspace / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        command = next(
            h["command"]
            for e in pre["hooks"]["PreToolUse"] if "shell" in e["matcher"].split("|")
            for h in e["hooks"] if "git-guard" in h["command"]
        )
        bash = resolve_bash()
        assert bash
        proc = subprocess.run(
            [bash, "-c", command],
            cwd=sub,
            input=json.dumps(_codex("shell", {"command": ["bash", "-lc", "git push origin master"]})),
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")

    def test_sensitive_matcher_catches_apply_patch(self) -> None:
        workspace = self._install("codex")
        pre = json.loads((workspace / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        entries = [
            e for e in pre["hooks"]["PreToolUse"]
            if any("sensitive-files-guard" in h["command"] for h in e["hooks"])
        ]
        self.assertTrue(
            any("apply_patch" in e["matcher"].split("|") for e in entries), entries
        )

    def test_dropping_codex_removes_its_guards(self) -> None:
        workspace = self._install("codex")
        self.assertTrue((workspace / ".codex" / "hooks.json").is_file())
        self.assertTrue((workspace / ".codex" / "hooks" / "git-guard.mjs").is_file())
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
        self.assertFalse((workspace / ".codex" / "hooks.json").exists())
        self.assertFalse((workspace / ".codex" / "hooks").exists())


if __name__ == "__main__":
    unittest.main()
