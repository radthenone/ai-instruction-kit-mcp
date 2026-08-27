"""
`.claude/settings.json` należy do użytkownika — trzyma jego `permissions`, `env`
i własne hooki. Kit dokłada tam tylko swoje wpisy guardraili i tylko je zabiera.

Te testy pilnują obu stron kontraktu: instalacja niczego cudzego nie gubi, a prune
zostawia plik dokładnie w stanie sprzed instalacji.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claude_settings.py"
TEMPLATE = ROOT / "templates" / "claude" / "settings.json"

USER_SETTINGS = {
    "permissions": {"allow": ["Read", "Grep"]},
    "env": {"MOJA_ZMIENNA": "1"},
    "hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": "moj-wlasny-skrypt.sh"}]}],
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "moj-lint.sh"}]}
        ],
    },
}


def run(*args: str) -> None:
    """
    Uruchom `claude_settings.py` i podnieś wyjątek, gdy zwróci błąd.

    Args:
        *args: Argumenty skryptu (tryb, ścieżki).
    """
    subprocess.run([sys.executable, str(SCRIPT), *args], check=True, capture_output=True)


class ClaudeSettingsMergeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "settings.json"

    def write_user_settings(self) -> None:
        self.target.write_text(json.dumps(USER_SETTINGS, indent=2), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.target.read_text(encoding="utf-8"))

    def test_install_on_missing_file_creates_it(self) -> None:
        run("install", str(self.target), str(TEMPLATE))
        events = self.load()["hooks"]["PreToolUse"]
        commands = [h["command"] for e in events for h in e["hooks"]]
        self.assertTrue(any("gate-destructive.sh" in c for c in commands))
        self.assertTrue(any("gate-file-writes.mjs" in c for c in commands))

    def test_install_preserves_unrelated_user_config(self) -> None:
        self.write_user_settings()
        run("install", str(self.target), str(TEMPLATE))
        data = self.load()

        self.assertEqual(data["permissions"], USER_SETTINGS["permissions"])
        self.assertEqual(data["env"], USER_SETTINGS["env"])
        self.assertEqual(data["hooks"]["SessionStart"], USER_SETTINGS["hooks"]["SessionStart"])

        user_commands = [
            h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]
        ]
        self.assertIn("moj-lint.sh", user_commands)

    def test_reinstall_does_not_duplicate_kit_entries(self) -> None:
        self.write_user_settings()
        run("install", str(self.target), str(TEMPLATE))
        first = self.load()["hooks"]["PreToolUse"]
        run("install", str(self.target), str(TEMPLATE))
        second = self.load()["hooks"]["PreToolUse"]
        self.assertEqual(len(first), len(second))

    def test_prune_restores_original_user_settings(self) -> None:
        self.write_user_settings()
        before = self.load()
        run("install", str(self.target), str(TEMPLATE))
        run("prune", str(self.target))
        self.assertEqual(self.load(), before)

    def test_prune_removes_file_when_only_kit_entries_remain(self) -> None:
        run("install", str(self.target), str(TEMPLATE))
        self.assertTrue(self.target.is_file())
        run("prune", str(self.target))
        self.assertFalse(self.target.exists())

    def test_unreadable_settings_do_not_abort_install(self) -> None:
        # Uszkodzony JSON nie może wywalić bootstrapu — kit zaczyna od pustego stanu.
        self.target.write_text("{ to nie jest json", encoding="utf-8")
        run("install", str(self.target), str(TEMPLATE))
        self.assertIn("PreToolUse", self.load()["hooks"])


if __name__ == "__main__":
    unittest.main()
