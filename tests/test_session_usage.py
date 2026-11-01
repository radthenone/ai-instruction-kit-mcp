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


if __name__ == "__main__":
    unittest.main()
