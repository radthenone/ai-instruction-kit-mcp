"""Testy obsługi .claude/settings.local.json per profil hosta (#316).

Na hoście VPS reload/sync-local dopisuje PONYTAIL_DEFAULT_MODE=off do env.
Na hoście local wpis dodany przez kit znika, a ręczna wartość użytkownika zostaje.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claude_settings.py"
sys.path.insert(0, str(ROOT / "src"))
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
        run("sync-local", str(self.target), "vps")
        self.assertEqual(self.load(), {"env": {"PONYTAIL_DEFAULT_MODE": "off"}})

    def test_sync_local_on_vps_preserves_user_default_mode(self) -> None:
        self.target.write_text(json.dumps({"env": {"PONYTAIL_DEFAULT_MODE": "lite", "OTHER": "1"}}), encoding="utf-8")
        run("sync-local", str(self.target), "vps")
        data = self.load()
        self.assertEqual(data["env"]["PONYTAIL_DEFAULT_MODE"], "lite")
        self.assertEqual(data["env"]["OTHER"], "1")

    def test_sync_local_on_local_removes_kit_off_entry_and_file_if_empty(self) -> None:
        self.target.write_text(json.dumps({"env": {"PONYTAIL_DEFAULT_MODE": "off"}}), encoding="utf-8")
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
