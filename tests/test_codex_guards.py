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


@unittest.skipUnless(NODE, "brak node")
class CodexInvokeHookAdapterTest(unittest.TestCase):
    """Adapter `--to codex` — deny i allow na payloadach PreToolUse."""

    def test_git_guard_deny_push_master(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            {"tool_name": "Bash", "tool_input": {"command": "git push origin master"}},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("git-guard", out.get("permissionDecisionReason", ""))

    def test_git_guard_allow_push_feat(self) -> None:
        out = _run_hook(
            "git-guard.mjs",
            {"tool_name": "Bash", "tool_input": {"command": "git push origin feat/x"}},
        )
        self.assertEqual(out.get("permissionDecision"), "allow")

    def test_sensitive_files_deny_env(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            {"tool_name": "Write", "tool_input": {"file_path": ".env"}},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")

    def test_sensitive_files_allow_src(self) -> None:
        out = _run_hook(
            "sensitive-files-guard.mjs",
            {"tool_name": "Write", "tool_input": {"file_path": "src/app.py"}},
        )
        self.assertEqual(out.get("permissionDecision"), "allow")

    def test_server_guard_deny_docker_on_vps(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            {"tool_name": "Bash", "tool_input": {"command": "docker compose up"}},
            env={**VPS, "KIT_HOST_PROFILE": "vps"},
        )
        self.assertEqual(out.get("permissionDecision"), "deny")
        self.assertIn("server-guard", out.get("permissionDecisionReason", ""))

    def test_server_guard_allow_docker_on_local(self) -> None:
        out = _run_hook(
            "server-guard.mjs",
            {"tool_name": "Bash", "tool_input": {"command": "docker compose up"}},
            env={**VPS, "KIT_HOST_PROFILE": "local"},
        )
        self.assertNotEqual(out.get("permissionDecision"), "deny")

    def test_empty_payload_guard_decides(self) -> None:
        out = _run_hook("git-guard.mjs", {})
        self.assertIn(out.get("permissionDecision"), {"allow", "deny"})


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
        matchers = {entry["matcher"] for entry in pre}
        self.assertIn("Bash", matchers)
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
        bash_entry = next(e for e in pre if e["matcher"] == "Bash")
        self.assertTrue(
            any("server-guard.mjs" in h["command"] for h in bash_entry["hooks"]),
            bash_entry,
        )
        mcp_entry = next(e for e in pre if "playwright" in e["matcher"])
        self.assertTrue(
            any("server-guard.mjs" in h["command"] for h in mcp_entry["hooks"]),
            mcp_entry,
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
