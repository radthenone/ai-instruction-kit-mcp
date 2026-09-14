#!/usr/bin/env python3
"""
Tabela regresji Guardów z `templates/shared/guards/*.mjs`.

Każdy Guard zna tylko allow albo deny — ADR 0006. Test dla każdego wiersza
odpala prawdziwy proces node z payloadem w kontrakcie Claude Code i sprawdza
`permissionDecision`. Bez node suita jest pomijana (na CI node jest wymagany —
patrz `test_shell_suites.py`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDS = ROOT / "templates" / "shared" / "guards"
NODE = shutil.which("node")

HOME = "/home/tester"

GIT_GUARD: list[tuple[str, str]] = [
    ("git status", "allow"),
    ("git push --force origin main", "deny"),
    ("git push origin +main", "deny"),
    ("git push -f origin master", "deny"),
    ("git push --force-with-lease origin dev", "deny"),
    ("git push origin main", "deny"),
    ("git push origin dev", "deny"),
    ("git push origin HEAD:main", "deny"),
    ("git push --force origin feat/x", "allow"),
    ("git push origin feat/x", "allow"),
    ("git push dev", "allow"),
    ("git push git+https://example.com/repo.git feat/x", "allow"),
    ("rtk git push origin main", "deny"),
    ("git reset --hard", "deny"),
    ("git reset --hard HEAD~1", "deny"),
    ("git reset --soft HEAD~1", "allow"),
    ("git clean -fd", "deny"),
    ("git clean -xdf", "deny"),
    ("git clean -n", "allow"),
    ("git branch -D feat/x", "deny"),
    ("git branch -d feat/x", "allow"),
    ("git checkout .", "deny"),
    ("git checkout -- src/a.py", "deny"),
    ("git checkout -b feat/y", "allow"),
    ("git checkout feat/x", "allow"),
    ("git stash", "allow"),
    ("git restore src/a.py", "allow"),
    ("git commit --no-verify -m x", "allow"),
    ("find . -name '*.tmp' -delete", "allow"),
    ("rm -rf node_modules", "allow"),
    ("rm -rf build/", "allow"),
    ("rm -rf ~/projects", "deny"),
    ("rm -rf ..", "deny"),
    ("rm -r /home/x", "deny"),
    ("rm -rf /", "deny"),
    ("rm -r C:\\Users\\x", "deny"),
    ("cp a.txt ~/.ssh/config", "deny"),
    ("echo x > ~/.claude/settings.json", "deny"),
    ("echo x > ~/.claude/settings.local.json", "deny"),
    ("echo x > /etc/hosts", "deny"),
    ("tee /etc/hosts", "deny"),
    ("sed -i s/a/b/ /etc/profile", "deny"),
    ("echo x > out.txt", "allow"),
    ("cp a.txt ~/notes.txt", "allow"),
    ("sed -i s/a/b/ ~/.bashrc", "allow"),
    ("cat ~/.ssh/config", "allow"),
    ("mkdir -p ~/.claude/hooks", "allow"),
]

BASH_GUARD_WIN: list[tuple[str, str]] = [
    ("git status", "allow"),
    ("pwsh -c Get-ChildItem", "deny"),
    ("powershell -Command ls", "deny"),
    ("powershell.exe -File x.ps1", "deny"),
    ("cmd /c dir", "deny"),
    ("cmd.exe /c dir", "deny"),
    ("ls && pwsh -File build.ps1", "deny"),
    ("ls; cmd /c dir", "deny"),
    ("cat x | powershell -", "deny"),
    ('"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -c ls', "deny"),
    ("/c/Program\\ Files/PowerShell/7/pwsh.exe -c ls", "deny"),
    ("echo pwsh", "allow"),
    ("grep -r cmd src/", "allow"),
    ("npm run cmd", "allow"),
]

SENSITIVE_READ: list[tuple[str, str]] = [
    ("src/app.py", "allow"),
    (".env", "deny"),
    (".env.local", "deny"),
    (".env.production", "deny"),
    (".env.example", "allow"),
    (".env.sample", "allow"),
    (".env.template", "allow"),
    ("certs/server.pem", "deny"),
    ("certs/server.key", "deny"),
    ("certs/client.p12", "deny"),
    ("certs/client.pfx", "deny"),
    ("/home/x/.ssh/id_rsa", "deny"),
    ("/home/x/.ssh/id_rsa.pub", "deny"),
    ("/home/x/.ssh/id_ed25519", "deny"),
    ("/home/x/.netrc", "deny"),
    ("config/credentials.json", "deny"),
    (".git/objects/ab/cdef", "deny"),
    (".git/refs/heads/main", "deny"),
    (".git/hooks/pre-commit", "deny"),
    (".git/HEAD", "allow"),
    (".git/config", "allow"),
    ("package-lock.json", "allow"),
    ("uv.lock", "allow"),
    ("Cargo.lock", "allow"),
    ("README.md", "allow"),
    ("C:\\repo\\.env", "deny"),
]

SENSITIVE_WRITE: list[tuple[str, str]] = [
    ("src/app.py", "allow"),
    (".env", "deny"),
    (".env.example", "allow"),
    ("certs/server.pem", "deny"),
    ("package-lock.json", "deny"),
    ("pnpm-lock.yaml", "deny"),
    ("yarn.lock", "deny"),
    ("bun.lockb", "deny"),
    ("uv.lock", "deny"),
    ("poetry.lock", "deny"),
    ("Pipfile.lock", "deny"),
    ("Cargo.lock", "deny"),
    ("package.json", "allow"),
    ("pyproject.toml", "allow"),
]


def run_guard(name: str, payload: dict, env: dict[str, str] | None = None) -> dict:
    """
    Odpal Guard przez node z payloadem w kontrakcie Claude Code.

    Args:
        name: Nazwa pliku w ``templates/shared/guards``.
        payload: Obiekt podawany na stdin (``tool_name``, ``tool_input``).
        env: Dodatkowe zmienne środowiska (nadpisują odziedziczone).

    Returns:
        dict: Zdekodowany ``hookSpecificOutput`` albo ``{}`` przy pustym stdout.
    """
    proc = subprocess.run(
        [NODE or "node", str(GUARDS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )
    assert proc.returncode == 0, f"{name}: exit {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    if not out:
        return {}
    return json.loads(out).get("hookSpecificOutput", {})


@unittest.skipUnless(NODE, "brak node")
class GitGuardTest(unittest.TestCase):
    def test_table(self) -> None:
        env = {"HOME": HOME, "USERPROFILE": HOME, "SystemDrive": "C:"}
        for command, expected in GIT_GUARD:
            with self.subTest(command=command):
                out = run_guard("git-guard.mjs", {"tool_input": {"command": command}}, env)
                self.assertEqual(out.get("permissionDecision"), expected, out.get("permissionDecisionReason"))

    def test_cursor_shape_and_empty(self) -> None:
        self.assertEqual(run_guard("git-guard.mjs", {"command": "git reset --hard"})["permissionDecision"], "deny")
        self.assertEqual(run_guard("git-guard.mjs", {})["permissionDecision"], "allow")

    def test_never_asks(self) -> None:
        for command, _ in GIT_GUARD:
            out = run_guard("git-guard.mjs", {"tool_input": {"command": command}})
            self.assertIn(out.get("permissionDecision"), {"allow", "deny"})


@unittest.skipUnless(NODE, "brak node")
class BashGuardTest(unittest.TestCase):
    def test_table_on_windows(self) -> None:
        for command, expected in BASH_GUARD_WIN:
            with self.subTest(command=command):
                out = run_guard("bash-guard.mjs", {"tool_input": {"command": command}}, {"GUARD_PLATFORM": "win32"})
                self.assertEqual(out.get("permissionDecision"), expected, out.get("permissionDecisionReason"))

    def test_allows_everything_off_windows(self) -> None:
        for command, _ in BASH_GUARD_WIN:
            out = run_guard("bash-guard.mjs", {"tool_input": {"command": command}}, {"GUARD_PLATFORM": "linux"})
            self.assertEqual(out.get("permissionDecision"), "allow")


@unittest.skipUnless(NODE, "brak node")
class SensitiveFilesGuardTest(unittest.TestCase):
    def test_read(self) -> None:
        for path, expected in SENSITIVE_READ:
            with self.subTest(path=path):
                out = run_guard("sensitive-files-guard.mjs", {"tool_name": "Read", "tool_input": {"file_path": path}})
                self.assertEqual(out.get("permissionDecision"), expected, out.get("permissionDecisionReason"))

    def test_write(self) -> None:
        for tool in ("Write", "Edit", "MultiEdit"):
            for path, expected in SENSITIVE_WRITE:
                with self.subTest(tool=tool, path=path):
                    out = run_guard("sensitive-files-guard.mjs", {"tool_name": tool, "tool_input": {"file_path": path}})
                    self.assertEqual(out.get("permissionDecision"), expected)

    def test_notebook_path(self) -> None:
        out = run_guard("sensitive-files-guard.mjs", {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "x.ipynb"}})
        self.assertEqual(out["permissionDecision"], "allow")

    def test_cursor_before_read_file_shape(self) -> None:
        # Cursor beforeReadFile: file_path + content, bez tool_name → traktuj jak Read.
        out = run_guard("sensitive-files-guard.mjs", {"file_path": "uv.lock", "content": ""})
        self.assertEqual(out["permissionDecision"], "allow")
        out = run_guard("sensitive-files-guard.mjs", {"file_path": ".env", "content": ""})
        self.assertEqual(out["permissionDecision"], "deny")


@unittest.skipUnless(NODE, "brak node")
class RtkCheckTest(unittest.TestCase):
    def test_silent_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claude = Path(tmp) / ".claude"
            claude.mkdir()
            (claude / "settings.json").write_text('{"hooks":{"PreToolUse":[{"hooks":[{"command":"rtk hook claude"}]}]}}')
            out = run_guard("rtk-check.mjs", {}, {"GUARD_HOME": tmp, "GUARD_RTK_BIN": NODE or "node"})
            self.assertEqual(out, {})

    def test_reports_missing_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = run_guard("rtk-check.mjs", {}, {"GUARD_HOME": tmp, "GUARD_RTK_BIN": NODE or "node"})
            self.assertEqual(out.get("hookEventName"), "SessionStart")
            self.assertIn("rtk init -g --auto-patch", out.get("additionalContext", ""))
            self.assertIn("settings.json", out.get("additionalContext", ""))

    def test_reports_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = run_guard("rtk-check.mjs", {}, {"GUARD_HOME": tmp, "GUARD_RTK_BIN": "definitely-not-a-binary-xyz"})
            self.assertIn("PATH", out.get("additionalContext", ""))


@unittest.skipUnless(NODE, "brak node")
class LintersGuardTest(unittest.TestCase):
    def test_silent_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            target = repo / "a.py"
            target.write_text("x=1\n", encoding="utf-8")
            out = run_guard("linters-guard.mjs", {"tool_input": {"file_path": str(target)}})
            self.assertEqual(out, {})

    def test_silent_for_missing_file(self) -> None:
        out = run_guard("linters-guard.mjs", {"tool_input": {"file_path": "/nope/never.py"}})
        self.assertEqual(out, {})

    def test_reports_ruff_findings_when_opted_in(self) -> None:
        ruff = shutil.which("ruff") or (ROOT / ".venv" / "Scripts" / "ruff.exe")
        if not (ruff and Path(ruff).exists()):
            self.skipTest("brak ruff")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "ruff.toml").write_text('[lint]\nselect = ["F"]\n', encoding="utf-8")
            target = repo / "a.py"
            target.write_text("import os\n", encoding="utf-8")
            out = run_guard("linters-guard.mjs", {"tool_input": {"file_path": str(target)}}, {"PATH": f"{Path(ruff).parent}{os.pathsep}{os.environ.get('PATH', '')}"})
            self.assertEqual(out.get("hookEventName"), "PostToolUse")
            self.assertIn("F401", out.get("additionalContext", ""))
            self.assertIn("a.py:1:", out.get("additionalContext", ""))


if __name__ == "__main__":
    unittest.main()
