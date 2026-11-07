"""Hook ``SessionEnd`` kita uruchamia ``kit-ai retro scan`` po sesji Claude (#371).

Sprawdzamy podpięcie w szablonie Claude, zarządzanie wpisem przez ``claude_settings.py``
(bez duplikacji przy reinstalacji), zachowanie skryptu wobec wejścia hooka oraz to, że
błąd skanera nigdy nie blokuje zamknięcia sesji.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_TEMPLATE = KIT_ROOT / "templates" / "claude" / "settings.json"
CLAUDE_SETTINGS = KIT_ROOT / "scripts" / "claude_settings.py"
HOOK_TEMPLATE = KIT_ROOT / "templates" / "shared" / "guards" / "retro-session-end.mjs"
BOOTSTRAP = KIT_ROOT / "scripts" / "bootstrap-project.sh"
NODE = shutil.which("node")
SESSION = "11111111-2222-4333-8444-555555555555"


def _session_end_commands(settings: dict) -> list[str]:
    entries = settings.get("hooks", {}).get("SessionEnd", [])
    return [hook["command"] for entry in entries for hook in entry.get("hooks", [])]


class ClaudeWiringTests(unittest.TestCase):
    def test_claude_template_registers_retro_hook_on_session_end(self) -> None:
        commands = _session_end_commands(json.loads(CLAUDE_TEMPLATE.read_text(encoding="utf-8")))
        self.assertEqual(len(commands), 1)
        self.assertIn("$CLAUDE_PROJECT_DIR/.claude/hooks/retro-session-end.mjs", commands[0])

    def test_install_is_idempotent_and_prune_removes_the_retro_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            for _ in range(2):
                subprocess.run(
                    [sys.executable, str(CLAUDE_SETTINGS), "install", str(target), str(CLAUDE_TEMPLATE)],
                    check=True,
                )
            installed = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(_session_end_commands(installed)), 1)
            subprocess.run([sys.executable, str(CLAUDE_SETTINGS), "prune", str(target)], check=True)
            remaining = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            self.assertEqual(_session_end_commands(remaining), [])

    def test_bootstrap_copies_the_hook_into_claude_hooks(self) -> None:
        script = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertRegex(
            script,
            r'cp "\$SHARED_GUARDS/retro-session-end\.mjs" "\$TARGET/\.claude/hooks/retro-session-end\.mjs"',
        )


@unittest.skipUnless(NODE, "brak node")
class SessionEndScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.record = self.root / "args.txt"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        if os.name == "nt":
            # spawnSync bez powłoki na Windows nie uruchomi skryptu `sh`. Fałszywy kit-ai to kopia binarki Node,
            # a preload z NODE_OPTIONS zapisuje argumenty i kończy proces. Działa tylko dla argv0 „kit-ai”,
            # więc hook (argv0 „node”) przechodzi bez zmian.
            shutil.copy2(NODE, self.bin / "kit-ai.exe")
            self.preload = self.bin / "record-args.cjs"
            self.preload.write_text(
                'const path = require("node:path");\n'
                'if (path.basename(process.argv0).toLowerCase().startsWith("kit-ai")) {\n'
                # Node rozwija argv[1] („retro”, traktowane jako skrypt) do ścieżki; nazwę odtwarzamy z basename.
                '  const args = [path.basename(process.argv[1]), ...process.argv.slice(2)];\n'
                '  require("node:fs").writeFileSync(process.env.RETRO_RECORD, args.join("\\n") + "\\n");\n'
                "  process.exit(0);\n"
                "}\n",
                encoding="utf-8",
            )
        else:
            fake = self.bin / "kit-ai"
            fake.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$RETRO_RECORD"\n', encoding="utf-8")
            fake.chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, payload: str, *, path: str | None = None) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "PATH": path if path is not None else f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "RETRO_RECORD": str(self.record),
        }
        if os.name == "nt":
            env["NODE_OPTIONS"] = f"--require {self.preload}"
        return subprocess.run(
            [str(NODE), str(HOOK_TEMPLATE)], input=payload, capture_output=True, text=True, env=env, timeout=30, check=False
        )

    def test_passes_session_and_repo_to_kit_ai_retro_scan(self) -> None:
        result = self._run(json.dumps({"session_id": SESSION, "cwd": str(self.repo)}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record.read_text(encoding="utf-8").splitlines(), ["retro", "scan", "--session", SESSION, str(self.repo)])

    def test_missing_kit_ai_is_a_silent_success(self) -> None:
        result = self._run(json.dumps({"session_id": SESSION, "cwd": str(self.repo)}), path="/nonexistent-bin")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse(self.record.exists())

    def test_unsafe_session_id_never_reaches_kit_ai(self) -> None:
        result = self._run(json.dumps({"session_id": "../escape", "cwd": str(self.repo)}))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.record.exists())

    def test_invalid_stdin_still_exits_zero(self) -> None:
        result = self._run("not json")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.record.exists())


class RepoCopyTests(unittest.TestCase):
    def test_hook_template_is_registered_as_claude_guard(self) -> None:
        self.assertTrue(HOOK_TEMPLATE.is_file())
        self.assertIsNotNone(re.search(r"SessionEnd", CLAUDE_TEMPLATE.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
