"""Testy weryfikujące reguły briefu kita: get_overlay, docstringi, Host i klasyfikację (#324)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from guides import server
from guides.host_profile import detect_host_profile

KIT_ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class TestKitBrief(unittest.TestCase):
    """Brief i instrukcje MCP zawierają wymóg get_overlay, regułę docstringów i Host (#324)."""

    def _build_test_resolved(self, workspace: Path, language: str = "pl"):
        """
        Zbuduj rozwiązany profil dla testowego workspace'u.

        Args:
            workspace: Ścieżka katalogu roboczego testu.
            language: Język projektu (domyślnie pl).

        Returns:
            ResolvedProfile: Rozwiązany profil workspace'u.
        """
        ai_dir = workspace / ".ai"
        ai_dir.mkdir(parents=True, exist_ok=True)
        (ai_dir / "project.profile.yaml").write_text(
            f"name: brief-test-app\nlanguage: {language}\nclients: claude\n"
            "backend: fastapi\nweb: react\nmobile: none\ncodegen: orval\n",
            encoding="utf-8",
        )
        (ai_dir / "project.md").write_text("# Overlay\n\nbase: dev\n", encoding="utf-8")

        saved = server._kit_root, server._workspace_root, server._language_override
        server._kit_root, server._workspace_root, server._language_override = (
            KIT_ROOT,
            workspace,
            None,
        )
        try:
            return server._get_resolved()
        finally:
            server._kit_root, server._workspace_root, server._language_override = saved

    def test_mcp_instructions_contain_overlay_docstring_and_host_rules(self) -> None:
        """Instrukcje MCP zawierają regułę get_overlay, format docstringów, Host i klasyfikację (#324)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            resolved = self._build_test_resolved(workspace)

        instructions = server.build_instructions(resolved)

        # (1) Klasyfikacja: zadanie kodowe i proceduralne
        self.assertIn("src/", instructions)
        self.assertIn("tests/", instructions)
        self.assertIn("/git-", instructions)
        self.assertIn("/review-", instructions)
        self.assertIn("/night-run", instructions)

        # (2) Wymóg get_overlay przed pierwszą edycją oraz warunki bez wywołań MCP
        self.assertIn("get_overlay", instructions)
        self.assertRegex(instructions, r"(?i)pierwszą edycją")
        self.assertIn("get_bundle", instructions)

        # (3) Format docstringów
        self.assertIn("Args/Returns", instructions)
        self.assertRegex(instructions, r"(?i)docstring")

        # (4) Host
        expected_host = detect_host_profile()
        self.assertIn(f"- **Host:** `{expected_host}`", instructions)

        # (5) Zakaz instalacji na VPS poza lockfile-only (#317)
        self.assertIn("lockfile-only", instructions)
        self.assertIn("VPS", instructions)

    def test_language_reminder_contains_overlay_docstring_and_host_rules(self) -> None:
        """Hook language-reminder.mjs wypisuje regułę get_overlay, docstringi, Host i klasyfikację (#324)."""
        if not NODE:
            self.skipTest("Brak środowiska node do uruchomienia hooka language-reminder.mjs")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            ai_dir = workspace / ".ai"
            ai_dir.mkdir(parents=True, exist_ok=True)
            (ai_dir / "project.profile.yaml").write_text(
                "name: hook-test-app\nlanguage: pl\nclients: claude\n",
                encoding="utf-8",
            )
            (ai_dir / "project.md").write_text("# Overlay\n\nbase: dev\n", encoding="utf-8")

            hook_path = KIT_ROOT / "templates" / "claude" / "language-reminder.mjs"
            env = {
                **os.environ,
                "CLAUDE_PROJECT_DIR": str(workspace),
                "KIT_HOST_PROFILE": "vps",
            }
            proc = subprocess.run(
                [NODE, str(hook_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = proc.stdout

        # Weryfikacja wymaganych elementów w wyjściu hooka
        self.assertIn("Host: `vps`", output)
        self.assertIn("get_overlay", output)
        self.assertIn("Args/Returns", output)
        self.assertIn("src/", output)
        self.assertIn("/git-", output)
        self.assertIn("lockfile-only", output)


if __name__ == "__main__":
    unittest.main()
