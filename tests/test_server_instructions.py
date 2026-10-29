"""Instrukcje serwera MCP niosą wartości z Profilu (#307)."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides import server

KIT_ROOT = Path(__file__).resolve().parents[1]


class TestServerInstructions(unittest.TestCase):
    """Po starcie MCP instructions mówią język, bazę, Tiery i codegen bez wywołań narzędzi."""

    def test_instructions_carry_project_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".ai").mkdir()
            (workspace / ".ai" / "project.profile.yaml").write_text(
                "name: instructions-app\nlanguage: pl\nclients: claude\n"
                "backend: fastapi\nweb: react\nmobile: none\ncodegen: orval\n",
                encoding="utf-8",
            )
            (workspace / ".ai" / "project.md").write_text(
                "# Overlay\n\nbase: dev\n", encoding="utf-8"
            )
            saved = server._kit_root, server._workspace_root, server._language_override
            server._kit_root, server._workspace_root, server._language_override = (
                KIT_ROOT,
                workspace,
                None,
            )
            try:
                resolved = server._get_resolved()
            finally:
                server._kit_root, server._workspace_root, server._language_override = saved

        text = server.build_instructions(resolved)

        self.assertIn("`pl`", text)
        self.assertIn("`dev`", text)
        self.assertIn("backend=`fastapi`", text)
        self.assertIn("`orval`", text)
        self.assertIn("get_bundle", text)
        self.assertIn("`claude`", text)

        saved_instructions = server.mcp._mcp_server.instructions
        try:
            server._set_instructions(text)
            options = server.mcp._mcp_server.create_initialization_options()
        finally:
            server.mcp._mcp_server.instructions = saved_instructions
        self.assertEqual(options.instructions, text)


    def test_instruction_failure_is_logged_to_stderr(self) -> None:
        """Błąd prywatnego API ``mcp`` nie ginie po cichu, a stdout (kanał MCP) zostaje czysty."""
        stderr, stdout = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(server, "_get_resolved"),
            mock.patch.object(server, "build_instructions", return_value="x"),
            mock.patch.object(server, "_set_instructions", side_effect=AttributeError("instructions")),
            contextlib.redirect_stderr(stderr),
            contextlib.redirect_stdout(stdout),
        ):
            server._apply_profile_instructions()

        self.assertIn("AttributeError", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
