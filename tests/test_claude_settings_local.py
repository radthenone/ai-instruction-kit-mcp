"""Testy matchera ponytaila w `.claude/settings.local.json` (#316).

`PONYTAIL_SUBAGENT_MATCHER` kit trzyma w `settings.local.json` (poza gitem), nie w
trackowanym `settings.json`. Ręczna wartość użytkownika zostaje nietknięta, a trybu
ponytaila (`PONYTAIL_DEFAULT_MODE`) kit nigdzie nie ustawia — także na VPS.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claude_settings.py"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from claude_settings import build_ponytail_matcher  # noqa: E402
from guides.bootstrap import run_bootstrap  # noqa: E402

STALE = "^(?!(?:git-commit|git-end)$).*"


def run(*args: str) -> None:
    """Uruchom `claude_settings.py` i podnieś wyjątek, gdy zwróci błąd."""
    subprocess.run([sys.executable, str(SCRIPT), *args], check=True, capture_output=True)


class ClaudeSettingsLocalTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "settings.local.json"

    def load(self) -> dict:
        if not self.target.is_file():
            return {}
        return json.loads(self.target.read_text(encoding="utf-8"))

    def test_sync_local_writes_kit_matcher_and_keeps_other_keys(self) -> None:
        """sync-local dopisuje matcher kita obok cudzych kluczy pliku lokalnego."""
        user = {"env": {"OTHER": "1"}, "permissions": {"allow": ["Read"]}}
        self.target.write_text(json.dumps(user), encoding="utf-8")
        run("sync-local", str(self.target))
        data = self.load()
        self.assertEqual(data["env"], {"OTHER": "1", "PONYTAIL_SUBAGENT_MATCHER": build_ponytail_matcher()})
        self.assertEqual(data["permissions"], user["permissions"])

    def test_sync_local_keeps_manual_matcher(self) -> None:
        """Ręczna wartość matchera użytkownika w settings.local.json zostaje."""
        user = {"env": {"PONYTAIL_SUBAGENT_MATCHER": "^custom-agent$"}}
        self.target.write_text(json.dumps(user), encoding="utf-8")
        run("sync-local", str(self.target))
        self.assertEqual(self.load(), user)

    def test_sync_local_refreshes_stale_kit_matcher(self) -> None:
        """Matcher kita ze starej listy agentów odświeża się przy reload."""
        self.target.write_text(json.dumps({"env": {"PONYTAIL_SUBAGENT_MATCHER": STALE}}), encoding="utf-8")
        run("sync-local", str(self.target))
        self.assertEqual(self.load()["env"]["PONYTAIL_SUBAGENT_MATCHER"], build_ponytail_matcher())

    def test_sync_local_does_not_set_ponytail_default_mode(self) -> None:
        """Kit nie wyłącza ponytaila: brak PONYTAIL_DEFAULT_MODE, także na VPS."""
        with mock.patch.dict(os.environ, {"KIT_HOST_PROFILE": "vps"}):
            run("sync-local", str(self.target))
        self.assertNotIn("PONYTAIL_DEFAULT_MODE", self.load()["env"])

    def test_sync_and_prune_local_leave_unreadable_file_untouched(self) -> None:
        """Nieczytelny prywatny plik użytkownika nie jest nadpisywany ani usuwany."""
        self.target.write_text("{ zepsuty json", encoding="utf-8")
        run("sync-local", str(self.target))
        run("prune-local", str(self.target))
        self.assertEqual(self.target.read_text(encoding="utf-8"), "{ zepsuty json")

    def test_prune_local_removes_only_kit_matcher(self) -> None:
        """prune-local zdejmuje matcher kita (pusty plik znika), ręczny zostaje."""
        run("sync-local", str(self.target))
        run("prune-local", str(self.target))
        self.assertFalse(self.target.exists())

        user = {"env": {"PONYTAIL_SUBAGENT_MATCHER": "^custom-agent$", "PONYTAIL_DEFAULT_MODE": "off"}}
        self.target.write_text(json.dumps(user), encoding="utf-8")
        run("prune-local", str(self.target))
        self.assertEqual(self.load(), user)

    def test_reload_writes_matcher_to_local_settings_not_tracked_ones(self) -> None:
        """Reload: matcher w settings.local.json, nie w settings.json; ręczny tryb nietknięty."""
        app_dir = Path(self._tmp.name) / "app"
        (app_dir / ".ai").mkdir(parents=True)
        (app_dir / ".ai" / "project.profile.yaml").write_text(
            "version: '4'\nlanguage: pl\nclients: claude\nstack:\n  backend: none\n  web: none\n  mobile: none\n",
            encoding="utf-8",
        )
        claude_dir = app_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(
            json.dumps({"env": {"PONYTAIL_SUBAGENT_MATCHER": STALE, "INNA": "2"}}), encoding="utf-8"
        )
        local = claude_dir / "settings.local.json"
        local.write_text(json.dumps({"env": {"PONYTAIL_DEFAULT_MODE": "lite"}}), encoding="utf-8")

        with mock.patch.dict(os.environ, {"KIT_HOST_PROFILE": "vps"}):
            run_bootstrap(target=app_dir, kit_root=ROOT, clients="claude", language="pl")

        tracked = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("PONYTAIL_SUBAGENT_MATCHER", tracked["env"])
        self.assertEqual(tracked["env"]["INNA"], "2")
        self.assertEqual(
            json.loads(local.read_text(encoding="utf-8"))["env"],
            {"PONYTAIL_DEFAULT_MODE": "lite", "PONYTAIL_SUBAGENT_MATCHER": build_ponytail_matcher()},
        )
        # Plik z matcherem jest poza gitem w projekcie z kitem (sekcja kita w .gitignore).
        gitignore = (app_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".claude/settings.local.json", gitignore)


if __name__ == "__main__":
    unittest.main()
