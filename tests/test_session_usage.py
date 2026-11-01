"""Testy modułu analizy zużycia tokenów w sesjach Claude Code.

Weryfikuje deduplikację wywołań API po message.id, zliczanie tokenów cache_read
oraz wywołań narzędzi Read i Bash (grep/find/ls).
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from session_usage import (  # noqa: E402
    SessionStats,
    find_sessions,
    format_table,
    main,
    parse_session_file,
)


def write_jsonl(path: Path, entries: list[Any]) -> None:
    """Zapisuje listę wpisów (słowników lub ciągów tekstowych) do pliku JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            if isinstance(entry, str):
                f.write(entry + "\n")
            else:
                f.write(json.dumps(entry) + "\n")


def make_message_entry(
    msg_id: str = "msg_001",
    input_tokens: int = 100,
    cache_read: int = 500,
    cache_creation: int = 50,
    content: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Tworzy wpis wiadomości asystenta do testów transkryptu sesji."""
    entry: dict[str, Any] = {
        "type": "assistant",
        "message": {
            "id": msg_id,
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
            "content": content or [{"type": "text", "text": "Odpowiedź testowa"}],
        },
    }
    if session_id:
        entry["sessionId"] = session_id
    return entry


class TestSessionUsage(unittest.TestCase):
    """Przypadki testowe dla parsowania i agregacji transkryptów sesji."""

    def test_parse_session_deduplicates_messages_and_computes_sums(self) -> None:
        """Weryfikuje deduplikację po message.id i kalkulację sum oraz średnich."""
        lines = [
            make_message_entry(msg_id="msg_001", input_tokens=100, cache_read=500, cache_creation=50),
            # Zduplikowana linia z tym samym message.id
            make_message_entry(msg_id="msg_001", input_tokens=100, cache_read=500, cache_creation=50),
            # Druga unikalna wiadomość
            make_message_entry(msg_id="msg_002", input_tokens=200, cache_read=1000, cache_creation=100),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "test_session.jsonl"
            write_jsonl(session_file, lines)

            stats = parse_session_file(session_file)

            self.assertEqual(stats.session_id, "test_session")
            self.assertEqual(stats.api_calls, 2)
            self.assertEqual(stats.cache_read_sum, 1500)
            self.assertAlmostEqual(stats.avg_context, 975.0)

    def test_parse_session_counts_tool_calls_with_deduplication(self) -> None:
        """Weryfikuje zliczanie wywołań Read oraz Bash (grep/find/ls) z deduplikacją."""
        lines = [
            make_message_entry(
                msg_id="msg_101",
                input_tokens=10,
                cache_read=10,
                content=[
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
            ),
            make_message_entry(
                msg_id="msg_101",
                input_tokens=10,
                cache_read=10,
                content=[
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
            ),
            make_message_entry(
                msg_id="msg_102",
                input_tokens=20,
                cache_read=20,
                content=[
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
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "tool_session.jsonl"
            write_jsonl(session_file, lines)

            stats = parse_session_file(session_file)

            self.assertEqual(stats.read_count, 2)
            self.assertEqual(stats.bash_grep_find_ls, 3)

    def test_tool_use_without_id_is_not_deduplicated(self) -> None:
        """Weryfikuje, że wywołania narzędzi bez identyfikatora id nie podlegają deduplikacji."""
        lines = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"path": "a.txt"}},
                    ],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Read", "input": {"path": "b.txt"}},
                    ],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "no_id_tools.jsonl"
            write_jsonl(session_file, lines)

            stats = parse_session_file(session_file)
            self.assertEqual(stats.read_count, 2)

    def test_bash_exploration_matches_only_command_at_segment_start(self) -> None:
        """Weryfikuje, że grep/find/ls są dopasowywane tylko na początku segmentu komendy."""
        ignored_lines = [
            make_message_entry(
                msg_id="msg_ignored",
                content=[
                    {
                        "type": "tool_use",
                        "id": "tool_ignore_1",
                        "name": "Bash",
                        "input": {"command": "git log --grep=x"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_ignore_2",
                        "name": "Bash",
                        "input": {"command": "cat ls.txt"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_ignore_3",
                        "name": "Bash",
                        "input": {"command": "cd docs/ls-tool"},
                    },
                ],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "ignored_bash.jsonl"
            write_jsonl(session_file, ignored_lines)

            stats = parse_session_file(session_file)
            self.assertEqual(stats.bash_grep_find_ls, 0)

        matched_lines = [
            make_message_entry(
                msg_id="msg_matched",
                content=[
                    {
                        "type": "tool_use",
                        "id": "tool_match_1",
                        "name": "Bash",
                        "input": {"command": "cd src && ls"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_match_2",
                        "name": "Bash",
                        "input": {"command": "echo foo | grep bar"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_match_3",
                        "name": "Bash",
                        "input": {"command": "echo 1; find ."},
                    },
                ],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "matched_bash.jsonl"
            write_jsonl(session_file, matched_lines)

            stats = parse_session_file(session_file)
            self.assertEqual(stats.bash_grep_find_ls, 3)

    def test_find_sessions_locates_jsonl_recursively(self) -> None:
        """Weryfikuje rekursywne wyszukiwanie plików .jsonl w zadanym katalogu."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            p1 = root / "proj1"
            p2 = root / "proj2" / "sub"
            p1.mkdir(parents=True)
            p2.mkdir(parents=True)

            (p1 / "session1.jsonl").write_text("{}", encoding="utf-8")
            (p2 / "session2.jsonl").write_text("{}", encoding="utf-8")
            (p1 / "notes.txt").write_text("hello", encoding="utf-8")

            found = find_sessions(root)
            found_names = [p.name for p in found]
            self.assertEqual(sorted(found_names), ["session1.jsonl", "session2.jsonl"])

    def test_format_table_renders_expected_columns(self) -> None:
        """Weryfikuje formatowanie tabeli tekstowej z podsumowaniem sesji."""
        stats1 = SessionStats(
            session_id="sess-001",
            api_calls=10,
            cache_read_sum=50000,
            avg_context=12000.5,
            bash_grep_find_ls=4,
            read_count=2,
        )
        table = format_table([stats1])

        self.assertIn("Session", table)
        self.assertIn("API Calls", table)
        self.assertIn("Cache Read Sum", table)
        self.assertIn("Cache Read Avg", table)
        self.assertIn("Avg Context", table)
        self.assertIn("grep/find/ls", table)
        self.assertIn("Read", table)
        self.assertIn("sess-001", table)
        self.assertIn("50000", table)
        self.assertIn("5000.0", table)

    def test_main_cli_execution(self) -> None:
        """Weryfikuje poprawne wykonanie funkcji main przez CLI z argumentem katalogu."""
        lines = [make_message_entry(msg_id="msg_main", input_tokens=50, cache_read=100, cache_creation=0)]

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "cli_test.jsonl"
            write_jsonl(file_path, lines)

            stdout_capture = io.StringIO()
            with patch("sys.stdout", stdout_capture):
                exit_code = main([tmpdir])

            output = stdout_capture.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("cli_test", output)
            self.assertIn("API Calls", output)


    def test_edge_case_empty_or_nonexistent_directory(self) -> None:
        """Weryfikuje, że dla pustego lub nieistniejącego katalogu main zwraca 0 z komunikatem."""
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = main(["/path/does_not_exist_xyz123"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Nie znaleziono plików sesji (.jsonl) w:", stdout_capture.getvalue())

        with tempfile.TemporaryDirectory() as empty_dir:
            stdout_capture = io.StringIO()
            with patch("sys.stdout", stdout_capture):
                exit_code = main([empty_dir])

            self.assertEqual(exit_code, 0)
            self.assertIn("Nie znaleziono plików sesji (.jsonl) w:", stdout_capture.getvalue())

    def test_edge_case_corrupted_json_and_non_dict_and_unicode_error(self) -> None:
        """Weryfikuje, że uszkodzone linie, linie nie-dict i błędy dekodowania są pomijane."""
        valid_entry = make_message_entry(msg_id="msg_valid", input_tokens=10, cache_read=20)
        lines = [
            "{uszkodzony json",
            "12345",
            "\"tekst bez obiektu\"",
            "",
            valid_entry,
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "corrupted.jsonl"
            write_jsonl(session_file, lines)

            stats = parse_session_file(session_file)
            self.assertEqual(stats.api_calls, 1)
            self.assertEqual(stats.cache_read_sum, 20)

            # Plik z błędnym kodowaniem UTF-8
            binary_file = Path(tmpdir) / "invalid_utf8.jsonl"
            binary_file.write_bytes(b"\xff\xfe\xfd\x80\x81")

            stats_bin = parse_session_file(binary_file)
            self.assertEqual(stats_bin.api_calls, 0)

    def test_edge_case_input_non_dict(self) -> None:
        """Weryfikuje, że input niebędący słownikiem (np. None lub string) nie wywołuje błędu."""
        lines = [
            make_message_entry(
                msg_id="msg_null_input",
                content=[
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": None,
                    },
                    {
                        "type": "tool_use",
                        "id": "t2",
                        "name": "Bash",
                        "input": "string_instead_of_dict",
                    },
                    {
                        "type": "tool_use",
                        "id": "t3",
                        "name": "Read",
                        "input": None,
                    },
                ],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "null_input.jsonl"
            write_jsonl(session_file, lines)

            stats = parse_session_file(session_file)
            self.assertEqual(stats.bash_grep_find_ls, 0)
            self.assertEqual(stats.read_count, 1)


if __name__ == "__main__":
    unittest.main()
