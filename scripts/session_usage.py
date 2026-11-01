"""Analiza zużycia tokenów w transkryptach sesji Claude Code.

Moduł przetwarza pliki JSONL sesji Claude Code, deduplikuje wywołania API
według message.id oraz wylicza statystyki zużycia tokenów i narzędzi.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BASH_EXPLORATION_PATTERN = re.compile(r"(?:^|[;&|])\s*(?:grep|find|ls)(?![\w-])")
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class SessionStats:
    """Statystyki pojedynczej sesji Claude Code."""

    session_id: str
    api_calls: int = 0
    cache_read_sum: int = 0
    avg_context: float = 0.0
    bash_grep_find_ls: int = 0
    read_count: int = 0


def parse_session_file(file_path: Path | str) -> SessionStats:
    """Parsuje pojedynczy plik transkryptu sesji JSONL.

    Args:
        file_path: Ścieżka do pliku transkryptu sesji JSONL.

    Returns:
        SessionStats: Obiekt zagregowanych statystyk sesji.
    """
    path = Path(file_path).resolve()
    session_id = path.stem

    seen_message_ids: set[str] = set()
    seen_tool_ids: set[str] = set()
    api_calls = 0
    total_cache_read = 0
    total_context = 0
    bash_grep_find_ls = 0
    read_count = 0

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if not isinstance(data, dict):
                    continue

                if "sessionId" in data and isinstance(data["sessionId"], str) and data["sessionId"]:
                    session_id = data["sessionId"]

                message = data.get("message")
                if isinstance(message, dict):
                    msg_id = message.get("id")
                    usage = message.get("usage")

                    if msg_id and isinstance(usage, dict):
                        if msg_id not in seen_message_ids:
                            seen_message_ids.add(msg_id)
                            api_calls += 1

                            cache_read = int(usage.get("cache_read_input_tokens") or 0)
                            input_tokens = int(usage.get("input_tokens") or 0)
                            cache_creation = int(usage.get("cache_creation_input_tokens") or 0)

                            total_cache_read += cache_read
                            total_context += input_tokens + cache_read + cache_creation

                    content = message.get("content")
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                tool_id = item.get("id")
                                if tool_id:
                                    if tool_id in seen_tool_ids:
                                        continue
                                    seen_tool_ids.add(tool_id)

                                tool_name = item.get("name")
                                if tool_name == "Read":
                                    read_count += 1
                                elif tool_name == "Bash":
                                    raw_input = item.get("input")
                                    command = ""
                                    if isinstance(raw_input, dict):
                                        command = str(raw_input.get("command") or "")
                                    if BASH_EXPLORATION_PATTERN.search(command):
                                        bash_grep_find_ls += 1
    except (OSError, UnicodeDecodeError):
        pass

    avg_context = (total_context / api_calls) if api_calls > 0 else 0.0

    return SessionStats(
        session_id=session_id,
        api_calls=api_calls,
        cache_read_sum=total_cache_read,
        avg_context=avg_context,
        bash_grep_find_ls=bash_grep_find_ls,
        read_count=read_count,
    )


def find_sessions(directory: Path | str) -> list[Path]:
    """Wyszukuje pliki sesji .jsonl w podanej lokalizacji.

    Args:
        directory: Katalog lub plik do przeszukania.

    Returns:
        list[Path]: Posortowana lista odnalezionych ścieżek do plików .jsonl.
    """
    path = Path(directory).expanduser().resolve()
    if not path.exists():
        return []

    if path.is_file():
        return [path] if path.suffix == ".jsonl" else []

    return sorted(path.rglob("*.jsonl"))


def format_table(stats_list: list[SessionStats]) -> str:
    """Formatuje listę statystyk sesji w czytelną tabelę tekstową.

    Args:
        stats_list: Lista obiektów statystyk sesji.

    Returns:
        str: Tekstowa reprezentacja tabeli.
    """
    headers = [
        "Session",
        "API Calls",
        "Cache Read Sum",
        "Cache Read Avg",
        "Avg Context",
        "grep/find/ls (Bash)",
        "Read",
    ]

    rows: list[list[str]] = []
    for s in stats_list:
        cache_read_avg = (s.cache_read_sum / s.api_calls) if s.api_calls > 0 else 0.0
        rows.append(
            [
                s.session_id,
                str(s.api_calls),
                str(s.cache_read_sum),
                f"{cache_read_avg:.1f}",
                f"{s.avg_context:.1f}",
                str(s.bash_grep_find_ls),
                str(s.read_count),
            ]
        )

    # Obliczanie szerokości kolumn
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(cell))

    def format_row(row_items: list[str]) -> str:
        # Pierwsza kolumna wyrównana do lewej, kolumny numeryczne do prawej
        formatted_cells: list[str] = []
        for i, val in enumerate(row_items):
            if i == 0:
                formatted_cells.append(val.ljust(col_widths[i]))
            else:
                formatted_cells.append(val.rjust(col_widths[i]))
        return " | ".join(formatted_cells)

    separator = "-+-".join("-" * w for w in col_widths)

    lines = [
        format_row(headers),
        separator,
    ]
    for row in rows:
        lines.append(format_row(row))

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Punkt wejścia CLI dla skryptu analizy zużycia sesji.

    Args:
        argv: Lista argumentów wiersza poleceń (opcjonalnie).

    Returns:
        int: Kod zakończenia procesu (0 w przypadku sukcesu).
    """
    parser = argparse.ArgumentParser(
        description="Analiza transkryptów sesji Claude Code pod kątem cache_read i wywołań narzędzi."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(DEFAULT_PROJECTS_DIR),
        help=f"Katalog z projektami sesji Claude Code (domyślnie: {DEFAULT_PROJECTS_DIR})",
    )

    args = parser.parse_args(argv)
    target_path = Path(args.directory).expanduser()

    session_files = find_sessions(target_path)
    if not session_files:
        print(f"Nie znaleziono plików sesji (.jsonl) w: {target_path}")
        return 0

    stats_list = [parse_session_file(f) for f in session_files]
    table = format_table(stats_list)
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
