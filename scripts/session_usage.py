"""Analiza zużycia tokenów w transkryptach sesji Claude Code.

Moduł przetwarza pliki JSONL sesji Claude Code, deduplikuje wywołania API
według message.id oraz wylicza statystyki zużycia tokenów i narzędzi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionStats:
    """Statystyki pojedynczej sesji Claude Code."""

    session_id: str
    file_path: Path
    api_calls: int = 0
    cache_read_sum: int = 0
    cache_read_avg: float = 0.0
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
    api_calls = 0
    total_cache_read = 0
    total_context = 0

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
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
    except OSError:
        pass

    cache_read_avg = (total_cache_read / api_calls) if api_calls > 0 else 0.0
    avg_context = (total_context / api_calls) if api_calls > 0 else 0.0

    return SessionStats(
        session_id=session_id,
        file_path=path,
        api_calls=api_calls,
        cache_read_sum=total_cache_read,
        cache_read_avg=cache_read_avg,
        avg_context=avg_context,
        bash_grep_find_ls=0,
        read_count=0,
    )
