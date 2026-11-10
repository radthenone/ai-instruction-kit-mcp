"""Testy parsowania ``--clients`` / ``GUIDES_CLIENTS``."""

from __future__ import annotations

import unittest

from guides.clients import (
    KNOWN_CLIENTS,
    expand_clients,
    format_clients_arg,
    normalize_client_id,
    parse_clients,
    parse_codegraph_clients,
)


class TestClientsParse(unittest.TestCase):
    """Normalizacja listy klientów AI."""

    def test_default_all(self) -> None:
        """Brak wartości → all."""
        self.assertEqual(parse_clients(None), ["all"])
        self.assertEqual(parse_clients(""), ["all"])
        self.assertEqual(parse_clients("all"), ["all"])

    def test_single_cursor(self) -> None:
        """Pojedynczy klient."""
        self.assertEqual(parse_clients("cursor"), ["cursor"])

    def test_alias_copilot(self) -> None:
        """Alias copilot → vscode."""
        self.assertEqual(parse_clients("copilot"), ["vscode"])
        self.assertEqual(normalize_client_id("github-copilot"), "vscode")

    def test_list_stable_order(self) -> None:
        """Kolejność jak w KNOWN_CLIENTS, nie jak w wejściu."""
        self.assertEqual(
            parse_clients("antigravity,cursor,claude"),
            ["cursor", "claude", "antigravity"],
        )

    def test_expand_all(self) -> None:
        """all → pełna lista."""
        self.assertEqual(expand_clients(["all"]), list(KNOWN_CLIENTS))

    def test_format_flag(self) -> None:
        """Format do mcp.json."""
        self.assertEqual(format_clients_arg(["all"]), "all")
        self.assertEqual(format_clients_arg(["cursor", "claude"]), "cursor,claude")

    def test_unknown_raises(self) -> None:
        """Nieznany id → ValueError."""
        with self.assertRaises(ValueError):
            parse_clients("anthropic")

    def test_server_source_registers_clients(self) -> None:
        """Kod serwera rejestruje ``--clients`` i tool ``get_clients``."""
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "src" / "guides" / "server.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"--clients"', src)
        self.assertIn("def get_clients", src)
        self.assertIn("GUIDES_CLIENTS", src)
        self.assertIn('"--client"', src)
        self.assertIn("GUIDES_CLIENT", src)




class TestCodegraphClientsParse(unittest.TestCase):
    """Normalizacja listy codegraph_clients z Profilu (#365)."""

    def test_empty_or_none(self) -> None:
        self.assertEqual(parse_codegraph_clients(None), set())
        self.assertEqual(parse_codegraph_clients(""), set())
        self.assertEqual(parse_codegraph_clients([]), set())

    def test_list_of_clients(self) -> None:
        self.assertEqual(
            parse_codegraph_clients(["claude", "codex"]),
            {"claude", "codex"},
        )

    def test_comma_separated_string(self) -> None:
        self.assertEqual(
            parse_codegraph_clients("claude, codex"),
            {"claude", "codex"},
        )

    def test_alias_normalization(self) -> None:
        self.assertEqual(
            parse_codegraph_clients(["copilot", "agy"]),
            {"vscode", "antigravity"},
        )

    def test_all_expands_to_all_known(self) -> None:
        self.assertEqual(
            parse_codegraph_clients("all"),
            set(KNOWN_CLIENTS),
        )

    def test_invalid_client_returns_empty_set(self) -> None:
        self.assertEqual(
            parse_codegraph_clients("not-a-client"),
            set(),
        )

if __name__ == "__main__":
    unittest.main()
