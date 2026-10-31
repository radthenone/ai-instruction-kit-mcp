"""Testy obsługi .claude/settings.local.json per profil hosta (#316).

Na hoście VPS reload/sync-local dopisuje PONYTAIL_DEFAULT_MODE=off do env.
Na hoście local wpis dodany przez kit znika, a ręczna wartość użytkownika zostaje.
"""

from __future__ import annotations

import contextlib
import io
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
from guides.bootstrap import run_bootstrap  # noqa: E402


def run(*args: str, env: dict[str, str] | None = None) -> None:
    merged_env = {**os.environ, **(env or {})}
    subprocess.run([sys.executable, str(SCRIPT), *args], check=True, capture_output=True, env=merged_env)


class ClaudeSettingsLocalTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "settings.local.json"

    def load(self) -> dict:
        if not self.target.is_file():
            return {}
        return json.loads(self.target.read_text(encoding="utf-8"))

    def test_sync_local_on_vps_adds_ponytail_default_mode_off(self) -> None:
        """Na VPS kit dopisuje tryb off ze znacznikiem pochodzenia."""
        run("sync-local", str(self.target), "vps")
        self.assertEqual(
            self.load(), {"env": {"PONYTAIL_DEFAULT_MODE": "off", "KIT_MANAGED_PONYTAIL_DEFAULT_MODE": "1"}}
        )

    def test_sync_local_on_local_keeps_manual_off_without_kit_marker(self) -> None:
        """Ręczne PONYTAIL_DEFAULT_MODE=off (bez znacznika kita) zostaje na local."""
        user = {"env": {"PONYTAIL_DEFAULT_MODE": "off"}}
        self.target.write_text(json.dumps(user), encoding="utf-8")
        run("sync-local", str(self.target), "local")
        self.assertEqual(self.load(), user)

    def test_sync_local_without_host_detection_leaves_file_unchanged(self) -> None:
        """Brak modułu wykrywania hosta: plik bez zmian, ostrzeżenie na stderr."""
        import claude_settings

        kit = {"env": {"PONYTAIL_DEFAULT_MODE": "off", "KIT_MANAGED_PONYTAIL_DEFAULT_MODE": "1"}}
        self.target.write_text(json.dumps(kit), encoding="utf-8")
        stderr = io.StringIO()
        with mock.patch.dict(sys.modules, {"guides.host_profile": None}), contextlib.redirect_stderr(stderr):
            claude_settings.sync_local_settings(self.target)
        self.assertEqual(self.load(), kit)
        self.assertIn("bez zmian", stderr.getvalue())

    def test_sync_local_on_vps_preserves_user_default_mode(self) -> None:
        self.target.write_text(json.dumps({"env": {"PONYTAIL_DEFAULT_MODE": "lite", "OTHER": "1"}}), encoding="utf-8")
        run("sync-local", str(self.target), "vps")
        data = self.load()
        self.assertEqual(data["env"]["PONYTAIL_DEFAULT_MODE"], "lite")
        self.assertEqual(data["env"]["OTHER"], "1")

    def test_sync_local_on_local_removes_kit_off_entry_and_file_if_empty(self) -> None:
        """Na local wpis kita (ze znacznikiem) znika, pusty plik też."""
        run("sync-local", str(self.target), "vps")
        run("sync-local", str(self.target), "local")
        self.assertFalse(self.target.exists())

    def test_sync_local_on_local_preserves_user_custom_mode_and_other_keys(self) -> None:
        user = {"env": {"PONYTAIL_DEFAULT_MODE": "lite", "OTHER": "1"}, "permissions": {"allow": ["Read"]}}
        self.target.write_text(json.dumps(user), encoding="utf-8")
        run("sync-local", str(self.target), "local")
        self.assertEqual(self.load(), user)

    def test_reload_with_kit_host_profile_vps_and_local(self) -> None:
        """Kryterium akceptacji: przy KIT_HOST_PROFILE=vps reload dodaje wpis, przy local usuwa kitowy."""
        app_dir = Path(self._tmp.name) / "app"
        app_dir.mkdir()
        (app_dir / ".ai").mkdir()
        (app_dir / ".ai" / "project.profile.yaml").write_text(
            "version: '4'\nlanguage: pl\nclients: claude\nstack:\n  backend: none\n  web: none\n  mobile: none\n",
            encoding="utf-8",
        )

        old_profile = os.environ.get("KIT_HOST_PROFILE")
        try:
            # 1. Reload na VPS
            os.environ["KIT_HOST_PROFILE"] = "vps"
            run_bootstrap(
                target=app_dir,
                kit_root=ROOT,
                clients="claude",
                language="pl",
            )
            local_settings = app_dir / ".claude" / "settings.local.json"
            self.assertTrue(local_settings.is_file(), "settings.local.json powinien powstać na VPS")
            data = json.loads(local_settings.read_text(encoding="utf-8"))
            self.assertEqual(data.get("env", {}).get("PONYTAIL_DEFAULT_MODE"), "off")

            # 2. Reload na local -> wpis 'off' dodany przez kit znika
            os.environ["KIT_HOST_PROFILE"] = "local"
            run_bootstrap(
                target=app_dir,
                kit_root=ROOT,
                clients="claude",
                language="pl",
            )
            if local_settings.is_file():
                data = json.loads(local_settings.read_text(encoding="utf-8"))
                self.assertNotIn("PONYTAIL_DEFAULT_MODE", data.get("env", {}))

            # 3. Ręczny wpis użytkownika zostaje na local
            local_settings.parent.mkdir(parents=True, exist_ok=True)
            local_settings.write_text(json.dumps({"env": {"PONYTAIL_DEFAULT_MODE": "lite"}}), encoding="utf-8")
            run_bootstrap(
                target=app_dir,
                kit_root=ROOT,
                clients="claude",
                language="pl",
            )
            data = json.loads(local_settings.read_text(encoding="utf-8"))
            self.assertEqual(data.get("env", {}).get("PONYTAIL_DEFAULT_MODE"), "lite")
        finally:
            if old_profile is None:
                os.environ.pop("KIT_HOST_PROFILE", None)
            else:
                os.environ["KIT_HOST_PROFILE"] = old_profile


if __name__ == "__main__":
    unittest.main()
