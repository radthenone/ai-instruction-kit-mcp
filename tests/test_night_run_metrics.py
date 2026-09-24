"""
Snippet pomiaru kosztu z night-run.md (#75) — uruchamiany na prawdziwym formacie
transkryptu subagenta Claude Code.

Snippet żyje w treści agenta, nie w skrypcie, więc test wyciąga go z pliku:
zmiana w agencie bez działającego snippetu nie przejdzie CI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guides.manifest import find_kit_root

AGENT = find_kit_root(Path(__file__)) / "templates" / "shared" / "agents" / "night-run.md"


def _line(ts: str, msg_id: str, model: str, usage: dict) -> str:
    return json.dumps(
        {"type": "assistant", "timestamp": ts, "message": {"id": msg_id, "model": model, "usage": usage}}
    )


class NightRunMetricsSnippet(unittest.TestCase):
    def test_counts_turns_by_message_id_and_skips_synthetic(self) -> None:
        match = re.search(r"python3 -c '(.*?)'", AGENT.read_text(encoding="utf-8"), re.S)
        assert match, "brak snippetu python3 -c w night-run.md"
        u1 = {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": 10}
        u2 = {"input_tokens": 3, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 3000, "output_tokens": 20}
        lines = [
            json.dumps({"type": "user", "timestamp": "2026-09-24T03:00:00.000Z", "message": {"content": "N = 1"}}),
            # Jedna odpowiedź modelu = kilka linii z tym samym id i tym samym usage.
            _line("2026-09-24T03:01:00.000Z", "m1", "claude-opus-5-5", u1),
            _line("2026-09-24T03:01:01.000Z", "m1", "claude-opus-5-5", u1),
            _line("2026-09-24T03:10:00.000Z", "m2", "claude-opus-5-5", u2),
            _line("2026-09-24T03:20:00.000Z", "s1", "<synthetic>", {"input_tokens": 0, "output_tokens": 0}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent-abc.jsonl"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out = subprocess.run(
                [sys.executable, "-c", match.group(1), str(path)], capture_output=True, text=True, check=True
            ).stdout
        row = out.strip().splitlines()[-1]
        self.assertEqual(
            row, "| agent-abc.jsonl | claude-opus-5-5 | 2 | 5 | 150 | 4000 | 30 | 3053 | 20 min |"
        )


if __name__ == "__main__":
    unittest.main()
