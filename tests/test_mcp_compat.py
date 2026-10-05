"""Smoke testy CLI / zależności MCP (uvx nie może wciągnąć mcp 2.x)."""

from __future__ import annotations

import importlib.metadata
import unittest
from pathlib import Path

from guides.manifest import find_kit_root, load_manifest


class TestMcpCompat(unittest.TestCase):
    """Kompatybilność z linią MCP Python SDK 1.x (FastMCP)."""

    def test_mcp_major_is_one(self) -> None:
        """Zainstalowany mcp musi być 1.x — FastMCP znika w 2.0."""
        version = importlib.metadata.version("mcp")
        major = int(version.split(".", maxsplit=1)[0])
        self.assertEqual(major, 1, msg=f"Oczekiwano mcp 1.x, jest {version}")

    def test_fastmcp_import(self) -> None:
        """Import ścieżki używanej przez guides.server."""
        from mcp.server.fastmcp import FastMCP

        self.assertTrue(callable(FastMCP))


class TestWorkspaceDiscovery(unittest.TestCase):
    """Wykrywanie kit root i profilu workspace'u."""

    def test_find_kit_root_has_manifest(self) -> None:
        """Kit root zawiera manifest.yaml z sekcjami tiers i bundles."""
        root = find_kit_root(Path(__file__))
        manifest = load_manifest(root)
        self.assertIn("backend", manifest.mappings.tiers)
        self.assertIn("backend", manifest.bundles)


if __name__ == "__main__":
    unittest.main()
