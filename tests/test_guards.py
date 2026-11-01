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
    # Reguły push patrzą tylko na segment z `git push`, nie na całą komendę.
    ("git merge-base --is-ancestor origin/dev x && git push -u origin HEAD", "allow"),
    ("git show origin/master:a.js > b && git push -u origin fix/x", "allow"),
    ("rm -f x; git push origin +main", "deny"),
    ("rm -f x; git push origin master", "deny"),
    ("git fetch && git push -f origin master", "deny"),
    ("git push origin feat/x 2>&1 | tail -3", "allow"),
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
    # Tekst w ciele heredoca z cytowanym ogranicznikiem i w apostrofach to dane (#206).
    ("python3 - <<'EOF'\nprint(1)\ngit push origin master\nEOF", "allow"),
    ("sed -i 's|x|git push origin master|' f.md", "allow"),
    ("cat <<A <<'B'\nx\nA\ngit push origin master\nB", "allow"),
    # Wykonywana treść dalej łapie deny: heredoc bez cytatu, powłoka czytająca heredoc,
    # `<<` w cudzysłowie, `$'…'`, `bash -c` / `eval`, ref w apostrofach.
    ("cat <<EOF\n$(git reset --hard)\nEOF", "deny"),
    ("cat <<EOF > notes.md\ndon't panic\nEOF\ngit reset --hard", "deny"),
    ("bash <<'EOF'\ngit push origin master\nEOF", "deny"),
    ('echo "<<EOF"\ngit reset --hard', "deny"),
    ("echo $'it\\'s' ; git reset --hard", "deny"),
    ("bash -c 'git push origin master'", "deny"),
    ("eval 'git reset --hard'", "deny"),
    ("git push origin 'master'", "deny"),
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
    ("bun.lock", "allow"),
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
    ("bun.lock", "deny"),
    ("uv.lock", "deny"),
    ("poetry.lock", "deny"),
    ("Pipfile.lock", "deny"),
    ("Cargo.lock", "deny"),
    ("package.json", "allow"),
    ("pyproject.toml", "allow"),
]

# Bash czyta sekret obejściem Read (#231). Guard widzi formę oryginalną (Claude Code)
# albo przepisaną przez RTK (opencode): `cat .env` → `rtk read .env`.
SENSITIVE_SHELL: list[tuple[str, str]] = [
    ("cat .env", "deny"),
    ("cat .env.local", "deny"),
    ("head -5 .env", "deny"),
    ("rtk read .env --max-lines 5", "deny"),
    ("rtk grep KEY .env", "deny"),
    ("rtk read id_rsa", "deny"),
    ("grep KEY .env", "deny"),
    ("sudo cat ~/.ssh/id_rsa", "deny"),
    ("env cat .env", "deny"),
    ("ls && cat .env | head", "deny"),
    ("source .env", "deny"),
    (". .env", "deny"),
    ('cat "certs/server.pem"', "deny"),
    ("rtk proxy cat .env", "deny"),
    ("sudo -u root cat .env", "deny"),
    ("echo $(cat .env)", "deny"),
    ("X=$(cat .env)", "deny"),
    ("FOO=1 cat .env", "deny"),
    ("cat .env>out", "deny"),
    ("cat < .env", "deny"),
    ("grep -e KEY .env", "deny"),
    ("cat .env.example", "allow"),
    ("cat README.md", "allow"),
    ("grep .env .gitignore", "allow"),
    ('grep -n "\\.env" .gitignore', "allow"),
    ("grep -rn '.env' .", "allow"),
    ("grep -e .env .gitignore", "allow"),
    ("rg id_rsa docs/", "allow"),
    ("rg '\\.env' src/", "allow"),
    ("cat .env.example > .env", "allow"),
    ("cat > .env <<EOF", "allow"),
    ("cp .env.example .env", "allow"),
    ("ls -la .env", "allow"),
    ("git check-ignore .env", "allow"),
    ("rm .env", "allow"),
    ("echo X > .env", "allow"),
    ('true & cat .env', "deny"),
    ('cat .env&', "deny"),
    ('grep -eKEY .env', "deny"),
    ('grep --regexp=KEY .env', "deny"),
    ('sed -e1p .env', "deny"),
    ('grep --regexp KEY .env', "deny"),
    ('cat -e .env', "deny"),
    ('less -e .env', "deny"),
    ('cat $(git rev-parse --show-toplevel)/.env', "deny"),
    ('cat "$(pwd)/.env"', "deny"),
    ('/bin/cat .env', "deny"),
    ('\\\\cat .env', "deny"),
    ('cat <.env', "deny"),
    ("env -S 'cat .env'", "deny"),
    ('bash -c "cat .env"', "deny"),
    ('grep -A 3 KEY .env', "deny"),
    ('/usr/bin/sudo cat .env', "deny"),
    ('cat foo >> .env', "allow"),
    ('cat >> .env <<EOF', "allow"),
    ('grep -A 3 .env README.md', "allow"),
    ('grep "load .env" README.md', "allow"),
    ('grep -e "load .env" README.md', "allow"),
    ('echo ok 2>&1', "allow"),
    ('cat foo 2>&1 > .env', "allow"),
    # Granica: guard tekstowy nie udaje pełnej ochrony (README, decyzja z #231).
    ("grep -r KEY .", "allow"),
    ("python -c \"open('.env')\"", "allow"),
]


def run_guard(name: str, payload: object, env: dict[str, str] | None = None) -> dict:
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
        encoding="utf-8",
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

    def test_shell_read(self) -> None:
        for command, expected in SENSITIVE_SHELL:
            with self.subTest(command=command):
                out = run_guard("sensitive-files-guard.mjs", {"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertEqual(out.get("permissionDecision"), expected, out.get("permissionDecisionReason"))

    def test_null_payload_does_not_crash(self) -> None:
        for payload in (None, "x", {"tool_input": None}):
            self.assertEqual(run_guard("sensitive-files-guard.mjs", payload)["permissionDecision"], "allow")

    def test_copilot_string_input_still_denies_read(self) -> None:
        # Adapter Copilota daje string jako command i file_path naraz — plik nie może zniknąć.
        proc = subprocess.run(
            [NODE or "node", str(GUARDS / "invoke-hook.js"), "sensitive-files-guard.mjs", "--to", "copilot"],
            input=json.dumps({"tool_name": "view", "tool_input": ".env"}),
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertIn("deny", proc.stdout)

    def test_copilot_bare_string_is_command_for_bash_not_path(self) -> None:
        # Nie-JSON toolArgs dla bash to komenda — `cat yarn.lock` nie jest zapisem lockfile.
        for tool_args, expected in (("cat config/yarn.lock", "allow"), ("ls config/.env", "allow"), ("cat .env", "deny")):
            with self.subTest(tool_args=tool_args):
                proc = subprocess.run(
                    [NODE or "node", str(GUARDS / "invoke-hook.js"), "sensitive-files-guard.mjs", "--to", "copilot"],
                    input=json.dumps({"toolName": "bash", "toolArgs": tool_args}),
                    capture_output=True, text=True, encoding="utf-8", check=False,
                )
                self.assertEqual("deny" in proc.stdout, expected == "deny", proc.stdout)

    def test_cursor_before_shell_execution_shape(self) -> None:
        # Cursor beforeShellExecution: `.command` bez tool_name.
        out = run_guard("sensitive-files-guard.mjs", {"command": "cat .env"})
        self.assertEqual(out.get("permissionDecision"), "deny")
        out = run_guard("sensitive-files-guard.mjs", {"command": "cat README.md"})
        self.assertEqual(out.get("permissionDecision"), "allow")


@unittest.skipUnless(NODE, "brak node")
class KitDoctorReminderTest(unittest.TestCase):
    """#269: SessionStart przypomina o otwartej partii doctora; bez pliku — cisza."""

    MODE_C = '/kit-project-edit "napraw zgłoszenia doctora"'

    def test_reminds_when_doctor_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".ai").mkdir()
            (Path(tmp) / ".ai" / ".kit-doctor.json").write_text('{"warnings": 2}', encoding="utf-8")
            out = run_guard("kit-doctor-reminder.mjs", {}, {"CLAUDE_PROJECT_DIR": tmp})
            self.assertEqual(out.get("hookEventName"), "SessionStart")
            self.assertIn(".ai/.kit-doctor.json", out.get("additionalContext", ""))
            self.assertIn(self.MODE_C, out.get("additionalContext", ""))

    def test_silent_without_doctor_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = run_guard("kit-doctor-reminder.mjs", {}, {"CLAUDE_PROJECT_DIR": tmp})
            self.assertEqual(out, {})

    def test_uses_payload_cwd_without_claude_project_dir(self) -> None:
        """Codex i Copilot nie ustawiają CLAUDE_PROJECT_DIR — katalog z `cwd` wejścia."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".ai").mkdir()
            (Path(tmp) / ".ai" / ".kit-doctor.json").write_text("{}", encoding="utf-8")
            out = run_guard("kit-doctor-reminder.mjs", {"cwd": tmp}, {"CLAUDE_PROJECT_DIR": ""})
            self.assertIn(self.MODE_C, out.get("additionalContext", ""))

    def test_registered_once_per_session_for_each_client(self) -> None:
        """Tylko SessionStart (raz na sesję) — nie przy każdym prompcie."""
        templates = Path(__file__).resolve().parents[1] / "templates"
        for rel in (
            "claude/settings.json",
            "codex/hooks.json",
            "vscode/github/hooks/kit-guards.json",
        ):
            with self.subTest(rel=rel):
                hooks = json.loads((templates / rel).read_text(encoding="utf-8"))["hooks"]
                events = [event for event, entries in hooks.items() if "kit-doctor-reminder.mjs" in json.dumps(entries)]
                self.assertEqual(events, ["SessionStart"])


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


# Server-guard (#194) — tabela z `KIT_HOST_PROFILE=vps`, po kategorii deny i allow.
SERVER_GUARD: list[tuple[str, str]] = [
    ("docker compose up", "deny"),
    ("docker stop x", "deny"),
    ("docker-compose run api", "deny"),
    ("podman run x", "deny"),
    ("docker logs -f api", "deny"),
    ("docker ps", "allow"),
    ("docker logs api", "allow"),
    ("docker compose ps", "allow"),
    ("docker-compose ps", "allow"),
    ("uv run ruff", "deny"),
    ("uv sync", "deny"),
    ("pip install x", "deny"),
    ("bun install", "deny"),
    ("npm ci", "deny"),
    ("uv run --no-sync ruff", "allow"),
    ("uvx ruff check", "deny"),
    ("uvx --offline ruff", "allow"),
    ("next build", "deny"),
    ("turbo run build", "deny"),
    ("turbo run typecheck", "allow"),
    ("tsc --noEmit", "allow"),
    ("npx playwright test", "deny"),
    ("cypress run", "deny"),
    ("pytest -n auto", "deny"),
    ("pytest tests/", "allow"),
    ("git status && ruff check .", "allow"),
    ("taskfoo build", "allow"),
    # Obejścia: powłoka, sudo, prefiksy, przypisania, łańcuchy.
    ('bash -c "docker compose up"', "deny"),
    ("sudo docker compose up", "deny"),
    ("sudo -n docker stop x", "deny"),
    ("sudo -u deploy docker stop x", "deny"),
    ("timeout 600 uv sync", "deny"),
    ("FOO=1 bun install", "deny"),
    ("nice -n 10 next build", "deny"),
    ("git status && docker compose up -d", "deny"),
    ("echo $(docker compose up)", "deny"),
    # Launchery (review #1): komenda za `uv run` / `npx` / `python -m` też jest sprawdzana.
    ("uv run --no-sync pytest -n auto", "deny"),
    ("uv run --no-sync python -m pytest -n 4", "deny"),
    ("python -m pytest -n 4", "deny"),
    ("python3 -m pytest tests/", "allow"),
    ("npx next build", "deny"),
    ("bunx --bun next build", "deny"),
    ("pnpm dlx playwright test", "deny"),
    ("uv --directory x run ruff", "deny"),
    ("uv --directory x run --no-sync ruff", "allow"),
    ("uv run --no-sync ruff check .", "allow"),
    # Powłoki i prefiksy (review #5).
    ('bash -lc "docker compose up"', "deny"),
    ("sh -ec 'uv sync'", "deny"),
    ("/usr/bin/docker compose up", "deny"),
    ("env -i docker compose up", "deny"),
    ("env -u HOME docker compose up", "deny"),
    ("timeout -s KILL 60 uv sync", "deny"),
    ("FOO= docker compose up", "deny"),
    ('eval "docker compose up"', "deny"),
    ("echo `docker compose up`", "deny"),
    # Cudzysłowy i heredoki to dane, nie komendy (review #7).
    ('git commit -m "x; docker compose up later"', "allow"),
    ("git commit -m 'fix | docker stop x'", "allow"),
    ("gh pr create --body \"$(cat <<'EOF'\nUruchom docker compose up\nuv sync\nEOF\n)\"", "allow"),
    ("cat <<EOF > notes.md\ndocker compose up\nEOF\ngit status", "allow"),
    ("cat <<EOF > notes.md\ntext\nEOF\ndocker compose up", "deny"),
    # Backticki w pojedynczych apostrofach to dane, nie podstawienie komendy (#206).
    ("sed -i 's|- `uv run python -m unittest`|x|' f.md", "allow"),
    ("gh pr create --title t --body 'Blokuje `docker compose up` na VPS'", "allow"),
    ("cat <<'E' > f\nuv run python -m x\nE\ngit status", "allow"),
    ('echo "uruchom docker compose up"', "allow"),
    ("uv run python -m x", "deny"),
    ("echo $(uv run python -m x)", "deny"),
    ("echo $'a\\'b' $(uv run python -m x)", "deny"),
    # Przypisanie w linii (review #8) i drobne (review #10).
    ("UV_NO_SYNC=1 uv run ruff", "allow"),
    ("command -v docker", "allow"),
    ("docker logs -tf app", "deny"),
    ("docker logs --tail 50 app", "allow"),
    ("podman ps", "allow"),
    ("podman logs app", "allow"),
    ("podman run x", "deny"),
    # Globalna wtyczka RTK przepisuje komendę przed guardem opencode (#227):
    # `rtk` to launcher, nie zwykły prefiks — `rtk next` gubi słowo `build`.
    ("rtk bun install", "deny"),
    ("mv a b && rtk bun install", "deny"),
    ("rtk uv sync", "deny"),
    ("rtk next", "deny"),
    ('rtk run -c "bun install"', "deny"),
    ("rtk run bun install", "deny"),
    ("rtk proxy uv sync", "deny"),
    ("rtk -v pnpm install", "deny"),
    ("rtk --ultra-compact npm ci", "deny"),
    ("rtk --skip-env bun install", "deny"),
    ("rtk ls", "allow"),
    ("rtk git status", "allow"),
    # `rtk next X` zawsze uruchamia `next build X` — także dev/start/lint i ścieżki.
    ("rtk next --debug", "deny"),
    ("rtk next dev", "deny"),
    ("rtk next start", "deny"),
    ("rtk next lint", "deny"),
    ("rtk next apps/web", "deny"),
    ("rtk next -- build", "deny"),
    ("rtk next --help", "allow"),
    # Flagi i `--` po podkomendzie launchera nie omijają guarda.
    ("rtk proxy --ultra-compact uv sync", "deny"),
    ("rtk proxy --skip-env bun install", "deny"),
    ("rtk proxy -- bun install", "deny"),
    ("rtk err -- next build", "deny"),
    ("rtk summary --ultra-compact uv sync", "deny"),
    ('rtk run --command "bun install"', "deny"),
    ('rtk run --command="bun install"', "deny"),
    ('rtk run -c"bun install"', "deny"),
    ("rtk run -c 'echo \"x\"'", "allow"),
    # Pojedynczy cytowany argument rtk uruchamia przez `sh -c`.
    ("rtk test 'bun install'", "deny"),
    ('rtk summary "bun install"', "deny"),
    ('rtk err "bun install"', "deny"),
    ('rtk test "uv sync"', "deny"),
    ("rtk summary 'next build'", "deny"),
    ("rtk run 'bun install'", "deny"),
    ('rtk run "echo x; docker compose up"', "deny"),
    ("rtk test 'echo hi'", "allow"),
    # Cytowany `rtk proxy` uruchamia komendę, a separator w cytowanym argumencie
    # rtk run|test|summary|err trafia do powłoki po sklejeniu argumentów.
    ("rtk proxy 'bun install'", "deny"),
    ('rtk proxy "uv sync"', "deny"),
    ("rtk run echo 'x;' bun install", "deny"),
    ("rtk test echo 'x;' bun install", "deny"),
    ("rtk summary true '|| bun install'", "deny"),
    ("rtk err echo 'x&&' bun install", "deny"),
    ("npx expo@latest install x", "deny"),
    # Zagnieżdżenie ponad limit to deny, nie crash hooka (fail-open).
    ("rtk " * 8000 + "bun install", "deny"),
    ("npx " * 8000 + "bun install", "deny"),
    # CLI, które same instalują paczki (ADR 0009: krótka lista) (#227).
    ("bunx shadcn@latest init -y", "deny"),
    ("pnpm dlx shadcn add button", "deny"),
    ("npx shadcn@latest add button", "deny"),
    ("npx expo install expo-camera", "deny"),
    ("expo install expo-camera", "deny"),
    # Luki instalacji/update (#301): uv, pip z wersją w nazwie, aliasy i update JS.
    ("uv pip sync r.txt", "deny"),
    ("uv pip install -r r.txt", "deny"),
    ("uv tool install ruff", "deny"),
    ("uv run --with requests python x.py", "deny"),
    ("uv run --no-sync --with requests python x.py", "deny"),
    ("uv run --no-sync --with-requirements r.txt python x.py", "deny"),
    # #317 — aktualizacja samego lockfile (bez instalacji i builda) jest dozwolona.
    ("uv lock --no-build", "allow"),
    ("uv lock", "deny"),
    ("uv add httpx --no-sync --no-build", "allow"),
    ("uv add httpx --no-build --no-sync", "allow"),
    ("uv add httpx --no-sync", "deny"),
    ("uv add httpx", "deny"),
    ("uv remove httpx --no-sync --no-build", "allow"),
    ("uv remove httpx --no-build", "deny"),
    ("npm install --package-lock-only --ignore-scripts", "allow"),
    ("npm install --package-lock-only", "deny"),
    ("npm install", "deny"),
    ("pnpm install --lockfile-only --ignore-scripts", "allow"),
    ("pnpm install --lockfile-only", "deny"),
    ("pnpm install", "deny"),
    ("bun install --lockfile-only --ignore-scripts", "allow"),
    ("bun install --lockfile-only", "deny"),
    ("bun install", "deny"),
    # Yarn: Yarn 1 nie ma trybu lock-only, a Berry nie ma `--ignore-scripts`;
    # guard nie rozpoznaje wersji, więc bezpiecznie zostaje deny.
    ("yarn install --mode=update-lockfile", "deny"),
    # #317 review — obejścia formy lock-only: komentarz, separator `--`, negacje flag,
    # flagi w cudzysłowach i rozwinięcia powłoki (`$`, `{…}`, `\\`).
    ("uv lock # --no-build", "deny"),
    ("uv lock -- --no-build", "deny"),
    ('uv lock "--" --no-build', "deny"),
    ("uv lock --no-build --build", "deny"),
    ("uv add x -- --no-sync --no-build", "deny"),
    ("uv add x # --no-sync --no-build", "deny"),
    ("uv add x $SEP --no-sync --no-build", "deny"),
    ("uv add x {--,} --no-sync --no-build", "deny"),
    ("uv add x \\-- --no-sync --no-build", "deny"),
    ('uv add x --no-sync "--no-build"', "deny"),
    ('uv add "httpx>=0.27" --no-sync --no-build', "allow"),
    ("npm install # --package-lock-only --ignore-scripts", "deny"),
    ("npm install -- --package-lock-only --ignore-scripts", "deny"),
    ("npm install --package-lock-only --ignore-scripts --package-lock-only=false", "deny"),
    ("npm install --package-lock-only --ignore-scripts --no-package-lock-only", "deny"),
    ("npm install --package-lock-only --ignore-scripts=false", "deny"),
    ("npm install --package-lock-only --ignore-scripts --no-ignore-scripts", "deny"),
    ("npm install --package-lock-only --ignore-scripts --ignore-scripts=0", "deny"),
    ("pnpm install --lockfile-only --ignore-scripts --no-lockfile-only", "deny"),
    ("pnpm install --lockfile-only --ignore-scripts --lockfile-only=false", "deny"),
    ("pnpm install -- --lockfile-only --ignore-scripts", "deny"),
    ("bun install --lockfile-only --ignore-scripts --no-ignore-scripts", "deny"),
    ("pip3.12 install x", "deny"),
    ("bun i", "deny"),
    ("bun a x", "deny"),
    ("bun update", "deny"),
    ("npm add x", "deny"),
    ("npm it", "deny"),
    ("npm up", "deny"),
    ("pnpm remove x", "deny"),
    ("yarn", "deny"),
    ("yarn upgrade", "deny"),
    ("pytest -nauto", "deny"),
    ("pytest tests/ -n4", "deny"),
    ("pytest --numprocesses=4", "deny"),
    # G1 — inne ekosystemy instalujące na serwerze.
    ("cargo install x", "deny"),
    ("go install x", "deny"),
    ("apt install x", "deny"),
    ("sudo apt install x", "deny"),
    ("apt-get install x", "deny"),
    ("corepack enable", "deny"),
    # G2 — buildy produkcyjne innych narzędzi.
    ("nuxt build", "deny"),
    ("astro build", "deny"),
    ("tsup", "deny"),
    ("webpack", "deny"),
    ("cargo build", "deny"),
    ("cargo check", "allow"),
    # G3 — launchery JS pobierające paczkę, poza jawną flagą „nie instaluj”.
    ("npx cowsay", "deny"),
    ("bunx cowsay", "deny"),
    ("pnpm dlx x", "deny"),
    ("yarn dlx x", "deny"),
    ("npx --no tsc --noEmit", "allow"),
    ("bunx --no-install tsc", "allow"),
    # G4 — uvx pobiera z sieci; wyjątek tylko dla trybu offline.
    ("uvx ruff", "deny"),
    ("UV_OFFLINE=1 uvx ruff", "allow"),
    # Review #301: wyjątki tylko dla flag PRZED nazwą narzędzia.
    ("uvx ruff --offline", "deny"),
    ("uvx --offline ruff", "allow"),
    ("npx cowsay --no", "deny"),
    ("bunx cowsay --no-install", "deny"),
    ("npx --no -y cowsay", "deny"),
    ("npx -y cowsay", "deny"),
    ("npx --no --yes cowsay", "deny"),
    ("npx --no cowsay", "allow"),
    ("bunx --no-install cowsay", "allow"),
    # Aliasy launcherów: npm exec/x, bun x, pnpx.
    ("npm exec cowsay", "deny"),
    ("npm x cowsay", "deny"),
    ("bun x cowsay", "deny"),
    ("pnpx cowsay", "deny"),
    ("npm exec --no tsc --noEmit", "allow"),
    ("bun x --no-install tsc", "allow"),
    ("npm exec --no -y cowsay", "deny"),
    # Flagi przed `install` (apt) i aliasy remove/install.
    ("apt-get -y install x", "deny"),
    ("apt -y install x", "deny"),
    ("npm uninstall x", "deny"),
    ("npm un x", "deny"),
    ("npm rm x", "deny"),
    ("npm r x", "deny"),
    ("npm cit", "deny"),
    ("npm install-ci-test", "deny"),
    ("bun rm x", "deny"),
    ("pnpm rm x", "deny"),
    ("yarn global add x", "deny"),
    # Goły yarn z flagami instalacji; informacyjne flagi zostają.
    ("yarn --frozen-lockfile", "deny"),
    ("yarn --cwd app", "deny"),
    ("yarn --cwd=app", "deny"),
    ("yarn --cwd app test", "allow"),
    ("yarn -v", "allow"),
    ("yarn --help", "allow"),
    # `--with-editable` jak `--with`.
    ("uv run --no-sync --with-editable . x", "deny"),
    ("uv run --with-editable . python x.py", "deny"),
    # Nadal pozwolone: venv, `uv run --no-sync` bez `--with`, skrypty projektu.
    ("python -m venv --without-pip .venv", "allow"),
    ("uv run --no-sync python -m unittest", "allow"),
    ("bun run test", "allow"),
    ("npm run lint", "allow"),
    # Blisko deny, ale nie deny — czytanie i skrypty projektowe zostają.
    ("uv pip list", "allow"),
    ("pip3 list", "allow"),
    ("bun run install", "allow"),
    ("npm run ci", "allow"),
    ("yarn --version", "allow"),
    ("pytest -q", "allow"),
    ("go build ./...", "allow"),
    ("astro dev", "allow"),
    ("apt list --installed", "allow"),
    ("corepack use pnpm@9", "allow"),
]

VPS = {"KIT_HOST_PROFILE": "vps", "GUIDES_HOST_PROFILE": "", "UV_NO_SYNC": "", "UV_OFFLINE": ""}


def run_server_guard(payload: dict, env: dict[str, str], config: dict | None = None) -> dict:
    """Odpal server-guard; z ``config`` — kopia guarda z ``server-guard.json`` obok."""
    if config is None:
        return run_guard("server-guard.mjs", payload, env)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(GUARDS / "server-guard.mjs", Path(tmp) / "server-guard.mjs")
        (Path(tmp) / "server-guard.json").write_text(json.dumps(config), encoding="utf-8")
        proc = subprocess.run(
            [NODE or "node", str(Path(tmp) / "server-guard.mjs")],
            input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, **env}, check=False,
        )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout).get("hookSpecificOutput", {}) if proc.stdout.strip() else {}


def decision(command: str, env: dict[str, str] = VPS, config: dict | None = None) -> str:
    """Decyzja server-guarda dla komendy Bash."""
    return run_server_guard({"tool_name": "Bash", "tool_input": {"command": command}}, env, config).get(
        "permissionDecision", ""
    )


@unittest.skipUnless(NODE, "brak node")
class ServerGuardTest(unittest.TestCase):
    def test_table_on_vps(self) -> None:
        for command, expected in SERVER_GUARD:
            with self.subTest(command=command):
                self.assertEqual(decision(command), expected)

    def test_python_matcher_agrees_with_js(self) -> None:
        # Render wrapperów używa dopasowania z Pythona — musi się zgadzać z guardem.
        from guides.server_guard import DEFAULTS, check_command

        for command, expected in SERVER_GUARD:
            with self.subTest(command=command):
                denied, _, _ = check_command(command, [dict(r) for r in DEFAULTS])
                self.assertEqual("deny" if denied else "allow", expected)

    def test_rtk_install_names_kit_rule(self) -> None:
        # Powód musi wskazywać regułę kita, nie tylko „wrapper”.
        out = run_server_guard({"tool_name": "Bash", "tool_input": {"command": "rtk bun install"}}, VPS)
        self.assertTrue(out.get("permissionDecisionReason", "").endswith("[bun-pkg]"), out)

    def test_rtk_next_names_next_build_rule(self) -> None:
        out = run_server_guard({"tool_name": "Bash", "tool_input": {"command": "rtk next"}}, VPS)
        self.assertEqual(out.get("permissionDecision"), "deny", out)
        self.assertTrue(out.get("permissionDecisionReason", "").endswith("[next-build]"), out)

    def test_uv_no_sync_env_allows_uv_run(self) -> None:
        self.assertEqual(decision("uv run ruff", {**VPS, "UV_NO_SYNC": "1"}), "allow")
        self.assertEqual(decision("uv sync", {**VPS, "UV_NO_SYNC": "1"}), "deny")

    def test_uv_offline_env_allows_uvx(self) -> None:
        # `uvx` pobiera z sieci; `UV_OFFLINE=1` zostawia tylko cache uv (#301).
        self.assertEqual(decision("uvx ruff", {**VPS, "UV_OFFLINE": "1"}), "allow")
        self.assertEqual(decision("uvx ruff", VPS), "deny")
        self.assertEqual(decision("uv run --with requests python x.py", {**VPS, "UV_OFFLINE": "1"}), "deny")

    @unittest.skipUnless(shutil.which("uvx"), "uvx nie w PATH")
    def test_uvx_offline_does_not_fetch_with_empty_cache(self) -> None:
        # Dowód z review #301: `uvx --offline` z pustym cache uv nie pobiera narzędzia.
        with tempfile.TemporaryDirectory() as root:
            # Cache i katalog narzędzi muszą być osobne — wspólny katalog blokuje uv (lock).
            env = {**os.environ, "UV_CACHE_DIR": os.path.join(root, "cache"), "UV_TOOL_DIR": os.path.join(root, "tools")}
            env.pop("UV_OFFLINE", None)
            proc = subprocess.run(
                ["uvx", "--offline", "ruff", "--version"],
                capture_output=True, text=True, encoding="utf-8", env=env, timeout=120, check=False,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_local_and_guard_off_allow_everything(self) -> None:
        off = {"version": 1, "guard": "off", "defaults": [], "wrappers": []}
        for command, _ in SERVER_GUARD:
            with self.subTest(command=command):
                self.assertEqual(decision(command, {**VPS, "KIT_HOST_PROFILE": "local"}), "allow")
                self.assertEqual(decision(command, VPS, off), "allow")

    def test_project_deny_and_allow_from_profile(self) -> None:
        from guides.server_guard import parse_server_section, render_config

        server = parse_server_section(
            'server:\n  deny:\n    - "bunx eas-cli"\n    - "task lint"\n  allow:\n    - "task lint"\n'
            "    - \"docker compose up\"\n  bogus: 1\n"
        )
        self.assertTrue(any("bogus" in w for w in server["warnings"]))
        config = render_config(tasks={}, packages={}, server=server)
        self.assertEqual(decision("bunx eas-cli build", VPS, config), "deny")
        self.assertEqual(decision("task lint", VPS, config), "allow")
        self.assertEqual(decision("docker compose up", VPS, config), "allow")

    def test_lock_only_deny_reason_names_allowed_form(self) -> None:
        cases = {
            "uv lock": ["--no-build"],
            "uv add httpx": ["--no-sync", "--no-build"],
            "npm install": ["--package-lock-only", "--ignore-scripts"],
            "pnpm install": ["--lockfile-only", "--ignore-scripts"],
            "bun install": ["--lockfile-only", "--ignore-scripts"],
        }
        for command, flags in cases.items():
            with self.subTest(command=command):
                out = run_server_guard({"tool_name": "Bash", "tool_input": {"command": command}}, VPS)
                reason = out.get("permissionDecisionReason", "")
                self.assertEqual(out.get("permissionDecision"), "deny", out)
                for flag in flags:
                    self.assertIn(flag, reason)

    def test_project_deny_blocks_lock_only_form(self) -> None:
        from guides.server_guard import parse_server_section, render_config

        server = parse_server_section('server:\n  deny:\n    - "uv lock --no-build"\n')
        config = render_config(tasks={}, packages={}, server=server)
        self.assertEqual(decision("uv lock --no-build", VPS, config), "deny")
        # Inne formy lock-only zostają dozwolone.
        self.assertEqual(decision("uv add httpx --no-sync --no-build", VPS, config), "allow")

    def test_playwright_mcp_tools_denied(self) -> None:
        for tool in ("mcp__plugin_playwright_playwright__browser_navigate", "mcp__playwright__browser_click"):
            with self.subTest(tool=tool):
                out = run_server_guard({"tool_name": tool, "tool_input": {"url": "http://x"}}, VPS)
                self.assertEqual(out.get("permissionDecision"), "deny")
        # Poza VPS bez decyzji — jawne `allow` zatwierdzałoby narzędzie MCP bez pytania.
        out = run_server_guard({"tool_name": "mcp__playwright__browser_click", "tool_input": {}}, {**VPS, "KIT_HOST_PROFILE": "local"})
        self.assertEqual(out, {})

    def test_unreadable_payload_allowed_off_vps(self) -> None:
        proc = subprocess.run(
            [NODE or "node", str(GUARDS / "server-guard.mjs")], input="{nope", capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, **VPS, "KIT_HOST_PROFILE": "local"}, check=False,
        )
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_embedded_defaults_match_python(self) -> None:
        from guides.server_guard import DEFAULTS

        proc = subprocess.run(
            [NODE or "node", str(GUARDS / "server-guard.mjs")], input="", capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "SERVER_GUARD_DUMP_DEFAULTS": "1"}, check=True,
        )
        self.assertEqual(json.loads(proc.stdout), [dict(r) for r in DEFAULTS])

    def test_dev_containers_are_local(self) -> None:
        from guides.host_profile import detect_host_profile

        env = {"KIT_HOST_PROFILE": "", "GUIDES_HOST_PROFILE": "", "CODESPACES": "true", "GUARD_PLATFORM": "linux",
               "GUARD_CPU_COUNT": "2", "GUARD_MEM_BYTES": str(4 * 1024**3), "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "docker", "GUARD_HAS_DESKTOP": "0", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0"}
        self.assertEqual(
            detect_host_profile(env={"CODESPACES": "true"}, platform="linux", cpu_count=2, mem_total_bytes=4 * 1024**3,
                                swap_total_bytes=0, virt="docker", has_desktop=False, is_ci=False, is_wsl=False),
            "local",
        )
        self.assertEqual(decision("docker compose up", env), "allow")

    def test_heuristic_parity_with_detect_host_profile(self) -> None:
        from guides.host_profile import detect_host_profile

        gib = 1024**3
        # (platform, cpu, mem, swap, virt, desktop, ci, wsl)
        base = ("linux", 1, 4 * gib, 0, "lxc", False, False, False)
        cases = [
            base,
            ("darwin", *base[1:]),
            (*base[:6], True, False),
            (*base[:7], True),
            (base[0], 4, *base[2:]),
            (*base[:2], 16 * gib, *base[3:]),
            (*base[:3], gib, *base[4:]),
            (*base[:4], "none", True, False, False),
            (*base[:4], "none", False, False, False),
            (*base[:4], "", True, False, False),
        ]
        flag = {True: "1", False: "0"}
        for plat, cpu, mem, swap, virt, desktop, ci, wsl in cases:
            with self.subTest(case=(plat, cpu, mem, swap, virt, desktop, ci, wsl)):
                expected = detect_host_profile(
                    env={}, platform=plat, cpu_count=cpu, mem_total_bytes=mem, swap_total_bytes=swap,
                    virt=virt, has_desktop=desktop, is_ci=ci, is_wsl=wsl,
                )
                env = {
                    "KIT_HOST_PROFILE": "", "GUIDES_HOST_PROFILE": "", "UV_NO_SYNC": "",
                    "GUARD_PLATFORM": plat, "GUARD_CPU_COUNT": str(cpu),
                    "GUARD_MEM_BYTES": str(mem), "GUARD_SWAP_BYTES": str(swap),
                    "GUARD_VIRT": virt, "GUARD_HAS_DESKTOP": flag[desktop],
                    "GUARD_IS_CI": flag[ci], "GUARD_IS_WSL": flag[wsl],
                }
                got = decision("docker compose up", env)
                self.assertEqual(got, "deny" if expected == "vps" else "allow")


@unittest.skipUnless(NODE, "brak node")
class ServerGuardWrappersTest(unittest.TestCase):
    """Rozwijanie Taskfile / package.json / `turbo run` przy reloadzie."""

    def _render(self, root: Path) -> dict:
        from guides.server_guard import collect_package_scripts, collect_taskfile_commands, render_config

        return render_config(
            tasks=collect_taskfile_commands(root),
            packages=collect_package_scripts(root),
            server={"guard": "auto", "deny": [], "allow": []},
        )

    def _write(self, root: Path, rel: str, text: str) -> None:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")

    def test_install_gaps_inside_wrappers(self) -> None:
        """Nowe deny (#301) rozwijają się też przez `task` / skrypt `package.json`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "Taskfile.yml", """version: '3'
tasks:
  deps:
    cmds:
      - uv pip sync r.txt
  tools:
    cmds:
      - cargo install x
  offline:
    cmds:
      - uvx --offline ruff check .
""")
            self._write(root, "package.json", json.dumps({"scripts": {
                "fetch": "npm add x", "tool": "npx cowsay", "ok": "npx --no tsc --noEmit"}}))
            config = self._render(root)

        for command in ("task deps", "task tools", "bun run fetch", "bun run tool", "npm run tool"):
            with self.subTest(command=command):
                self.assertEqual(decision(command, VPS, config), "deny")
        for command in ("task offline", "bun run ok", "npm run ok"):
            with self.subTest(command=command):
                self.assertEqual(decision(command, VPS, config), "allow")

    def test_package_json_in_dot_dirs_ignored(self) -> None:
        from guides.server_guard import collect_package_scripts

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "apps/web/package.json", json.dumps({"scripts": {"lint": "eslint src"}}))
            self._write(root, ".ai/headless-runs/run/fixture/package.json", json.dumps({"scripts": {"build": "turbo run build"}}))
            self._write(root, ".worktrees/x/package.json", json.dumps({"scripts": {"build": "next build"}}))

            self.assertEqual(list(collect_package_scripts(root)), ["apps/web/package.json"])

    def test_taskfile_and_monorepo_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "Taskfile.yml", """version: '3'
includes:
  test: ./taskfiles/test.yml
  backend:
    taskfile: ./backend
    dir: ./backend
  web: {taskfile: ./taskfiles/web.yml, dir: ./web}
tasks:
  lint:
    cmds:
      - uv run --no-sync ruff check .
  sync:
    cmds:
      - uv run pytest tests/
  mixed:
    cmds:
      - uv run pytest && docker compose up
  up:
    cmds:
      - cmd: docker compose up -d
  script:
    cmds:
      - |
        echo start
        docker compose build
  all:
    deps: [up]
  ci:
    cmds:
      - task: backend:test
  front:
    cmds:
      - bun run build
""")
            self._write(root, "taskfiles/test.yml", """version: '3'
tasks:
  backend:
    cmds:
      - task: db
  db:
    cmds:
      - docker-compose -f compose.yml run --rm api pytest
""")
            self._write(root, "backend/Taskfile.yml", "version: '3'\ntasks:\n  test:\n    cmds:\n      - docker compose run api pytest\n")
            self._write(root, "taskfiles/web.yml", "version: '3'\ntasks:\n  e2e:\n    cmds:\n      - npx playwright test\n")
            self._write(root, "package.json", json.dumps({"scripts": {
                "build": "turbo run build", "lint": "turbo run lint", "ci": "bun run build",
                "test": "turbo run test", "check": "turbo run lint typecheck"}}))
            self._write(root, "apps/web/package.json", json.dumps({"scripts": {
                "build": "next build", "lint": "eslint src", "test": "playwright test", "typecheck": "tsc --noEmit"}}))
            self._write(root, "node_modules/x/package.json", json.dumps({"scripts": {"boom": "docker build ."}}))

            config = self._render(root)

        deny = {
            "task test:backend", "task test:db", "task up", "task script", "task all", "task ci",
            "task backend:test", "task web:e2e", "task front", "task sync", "task mixed",
            "bun run build", "npm run build", "pnpm run build", "yarn run build", "yarn build",
            "bun --filter web run build", "bun run ci", "npm test", "turbo run test", "turbo run lint test",
            # `rtk npm X` działa jak `npm run X`; wrapper z package.json łapie build (#227).
            "rtk npm build",
        }
        allow = {"task lint", "bun run lint", "bun run boom", "turbo run lint", "bun run check", "npm run typecheck"}
        for command in sorted(deny):
            with self.subTest(command=command):
                self.assertEqual(decision(command, VPS, config), "deny")
        for command in sorted(allow):
            with self.subTest(command=command):
                self.assertEqual(decision(command, VPS, config), "allow")

        out = run_server_guard({"tool_input": {"command": "bun run ci"}}, VPS, config)
        self.assertIn("bun run ci → bun run build → turbo run build → next build", out.get("permissionDecisionReason", ""))
        out = run_server_guard({"tool_input": {"command": "rtk npm build"}}, VPS, config)
        self.assertIn("npm run build → turbo run build → next build", out.get("permissionDecisionReason", ""))
        out = run_server_guard({"tool_input": {"command": "task ci"}}, VPS, config)
        self.assertIn("task ci → task backend:test → docker compose run api pytest", out.get("permissionDecisionReason", ""))

        # Task z samym `uv run` bez flagi przechodzi tylko z `UV_NO_SYNC=1`; ciężki obok — nie.
        no_sync = {**VPS, "UV_NO_SYNC": "1"}
        self.assertEqual(decision("task sync", no_sync, config), "allow")
        self.assertEqual(decision("task mixed", no_sync, config), "deny")
        self.assertEqual(decision("task test:backend", no_sync, config), "deny")


if __name__ == "__main__":
    unittest.main()
