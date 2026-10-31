"""Testy zgłoszeń doctora dla pluginu ponytail (#316).

Kryteria akceptacji:
- Przy atrapie zainstalowanego ponytaila bez PONYTAIL_SUBAGENT_MATCHER w hookach jest ostrzeżenie.
- Bez zainstalowanego ponytaila brak ostrzeżenia.
- Ręczna wartość PONYTAIL_SUBAGENT_MATCHER niewykluczająca procedur kita powoduje ostrzeżenie.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from guides.doctor import run_doctor  # noqa: E402


class DoctorPonytailTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "app"
        self.workspace.mkdir()
        self.claude_home = Path(self._tmp.name) / "home_claude"
        self.claude_home.mkdir()

        # Minimalny profil aplikacji
        ai_dir = self.workspace / ".ai"
        ai_dir.mkdir()
        (ai_dir / "project.profile.yaml").write_text(
            "version: '4'\nlanguage: pl\nclients: claude\nstack:\n  backend: none\n  web: none\n  mobile: none\n",
            encoding="utf-8",
        )
        (self.workspace / ".claude").mkdir()
        (self.workspace / ".claude" / "settings.json").write_text("{}", encoding="utf-8")

    def test_no_warning_when_ponytail_not_installed(self) -> None:
        """Bez zainstalowanego ponytaila doctor nie zgłasza żadnych ostrzeżeń o ponytailu."""
        report = run_doctor(self.workspace, kit_root=ROOT, clients="claude", claude_home=self.claude_home)
        kinds = [f.kind for f in report.warnings]
        self.assertNotIn("ponytail-matcher-unsupported", kinds)
        self.assertNotIn("ponytail-matcher-leaks-procedures", kinds)

    def test_warning_when_ponytail_installed_without_subagent_matcher_in_hooks(self) -> None:
        """Gdy ponytail jest zainstalowany, ale hooki nie mają PONYTAIL_SUBAGENT_MATCHER, jest ostrzeżenie."""
        plugin_dir = self.claude_home / "plugins" / "cache" / "ponytail" / "1.0.0"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "ponytail-subagent.js").write_text("// stary hook bez wsparcia matchera\n", encoding="utf-8")

        installed_json = self.claude_home / "plugins" / "installed_plugins.json"
        installed_json.write_text(
            json.dumps({"version": 2, "plugins": {"ponytail@ponytail": [{"installPath": str(plugin_dir)}]}}),
            encoding="utf-8",
        )

        report = run_doctor(self.workspace, kit_root=ROOT, clients="claude", claude_home=self.claude_home)
        kinds = [f.kind for f in report.warnings]
        self.assertIn("ponytail-matcher-unsupported", kinds)

    def test_no_warning_when_ponytail_installed_with_subagent_matcher_in_hooks(self) -> None:
        """Gdy ponytail jest zainstalowany i jego hooki mają PONYTAIL_SUBAGENT_MATCHER, brak ostrzeżenia."""
        plugin_dir = self.claude_home / "plugins" / "cache" / "ponytail" / "4.10.0"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "ponytail-subagent.js").write_text(
            "const matcher = process.env.PONYTAIL_SUBAGENT_MATCHER;\n",
            encoding="utf-8",
        )

        installed_json = self.claude_home / "plugins" / "installed_plugins.json"
        installed_json.write_text(
            json.dumps({"version": 2, "plugins": {"ponytail@ponytail": [{"installPath": str(plugin_dir)}]}}),
            encoding="utf-8",
        )

        report = run_doctor(self.workspace, kit_root=ROOT, clients="claude", claude_home=self.claude_home)
        kinds = [f.kind for f in report.warnings]
        self.assertNotIn("ponytail-matcher-unsupported", kinds)

    def test_warning_when_user_manual_matcher_does_not_exclude_procedures(self) -> None:
        """Gdy użytkownik ręcznie wpisał matcher, który przepuszcza agentów procedur kita, doctor ostrzega."""
        settings = {
            "env": {
                "PONYTAIL_SUBAGENT_MATCHER": ".*"  # przepuszcza wszystko, w tym git-commit
            }
        }
        (self.workspace / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        report = run_doctor(self.workspace, kit_root=ROOT, clients="claude", claude_home=self.claude_home)
        kinds = [f.kind for f in report.warnings]
        self.assertIn("ponytail-matcher-leaks-procedures", kinds)


if __name__ == "__main__":
    unittest.main()
