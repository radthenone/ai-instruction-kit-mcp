"""Testy modułu analizy zużycia tokenów w sesjach Claude Code.

Weryfikuje deduplikację wywołań API po message.id, zliczanie tokenów cache_read
oraz wywołań narzędzi Read i Bash (grep/find/ls).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from session_usage import SessionStats, parse_session_file  # noqa: E402


class TestSessionUsage(unittest.TestCase):
    """Przypadki testowe dla parsowania i agregacji transkryptów sesji."""

    def test_parse_session_deduplicates_messages_and_computes_sums(self) -> None:
        """Weryfikuje deduplikację po message.id i kalkulację sum oraz średnich.

        Args:
            Brak.

        Returns:
            None.
        """
        lines = [
            {
                "type": "assistant",
                "message": {
                    "id": "msg_001",
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 100,
                        "cache_read_input_tokens": 500,
                        "cache_creation_input_tokens": 50,
                    },
                    "content": [{"type": "text", "text": "Pierwsza odpowiedź"}],
                },
            },
            # Zduplikowana linia z tym samym message.id
            {
                "type": "assistant",
                "message": {
                    "id": "msg_001",
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 100,
                        "cache_read_input_tokens": 500,
                        "cache_creation_input_tokens": 50,
                    },
                    "content": [{"type": "text", "text": "Pierwsza odpowiedź"}],
                },
            },
            # Druga unikalna wiadomość
            {
                "type": "assistant",
                "message": {
                    "id": "msg_002",
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 200,
                        "cache_read_input_tokens": 1000,
                        "cache_creation_input_tokens": 100,
                    },
                    "content": [{"type": "text", "text": "Druga odpowiedź"}],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "test_session.jsonl"
            with open(session_file, "w", encoding="utf-8") as f:
                for entry in lines:
                    f.write(json.dumps(entry) + "\n")

            stats = parse_session_file(session_file)

            self.assertEqual(stats.session_id, "test_session")
            self.assertEqual(stats.api_calls, 2)
            self.assertEqual(stats.cache_read_sum, 1500)
            self.assertAlmostEqual(stats.cache_read_avg, 750.0)
            self.assertAlmostEqual(stats.avg_context, 975.0)

    def test_parse_session_counts_tool_calls_with_deduplication(self) -> None:
        """Weryfikuje zliczanie wywołań Read oraz Bash (grep/find/ls) z deduplikacją.

        Args:
            Brak.

        Returns:
            None.
        """
        lines = [
            # Wiadomość z Read i Bash grep
            {
                "type": "assistant",
                "message": {
                    "id": "msg_101",
                    "role": "assistant",
                    "usage": {"input_tokens": 10, "cache_read_input_tokens": 10},
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_read_1",
                            "name": "Read",
                            "input": {"path": "src/main.py"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_bash_1",
                            "name": "Bash",
                            "input": {"command": "grep -rn 'foo' src/"},
                        },
                    ],
                },
            },
            # Powtórzona linia z tym samym message i tool_use IDs
            {
                "type": "assistant",
                "message": {
                    "id": "msg_101",
                    "role": "assistant",
                    "usage": {"input_tokens": 10, "cache_read_input_tokens": 10},
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_read_1",
                            "name": "Read",
                            "input": {"path": "src/main.py"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_bash_1",
                            "name": "Bash",
                            "input": {"command": "grep -rn 'foo' src/"},
                        },
                    ],
                },
            },
            # Kolejna wiadomość: find, ls oraz git status (inny bash) oraz kolejny Read
            {
                "type": "assistant",
                "message": {
                    "id": "msg_102",
                    "role": "assistant",
                    "usage": {"input_tokens": 20, "cache_read_input_tokens": 20},
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_read_2",
                            "name": "Read",
                            "input": {"path": "README.md"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_bash_2",
                            "name": "Bash",
                            "input": {"command": "find . -name '*.md'"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_bash_3",
                            "name": "Bash",
                            "input": {"command": "ls -la docs/"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_bash_4",
                            "name": "Bash",
                            "input": {"command": "git status"},
                        },
                    ],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "tool_session.jsonl"
            with open(session_file, "w", encoding="utf-8") as f:
                for entry in lines:
                    f.write(json.dumps(entry) + "\n")

            stats = parse_session_file(session_file)

            self.assertEqual(stats.read_count, 2)
            # Bash grep (1) + find (1) + ls (1) = 3 wywołania; git status nie powinien być liczony
            self.assertEqual(stats.bash_grep_find_ls, 3)


if __name__ == "__main__":
    unittest.main()
