"""
Parsowanie i normalizacja listy klientów AI (`--clients` / GUIDES_CLIENTS).
"""

from __future__ import annotations

# Kanoniczne identyfikatory klientów (kolejność stabilna dla `all`).
KNOWN_CLIENTS: tuple[str, ...] = (
    "cursor",
    "claude",
    "codex",
    "vscode",
    "kiro",
    "kilo",
    "antigravity",
    "opencode",
)

_ALIASES: dict[str, str] = {
    "copilot": "vscode",
    "github-copilot": "vscode",
    "agy": "antigravity",
}


def normalize_client_id(raw: str) -> str:
    """
    Znormalizuj pojedynczy identyfikator klienta (lowercase, aliasy).

    Args:
        raw: Surowy token, np. ``Cursor``, ``copilot``.

    Returns:
        str: Kanoniczne id z ``KNOWN_CLIENTS``.

    Raises:
        ValueError: Gdy id nie jest znane.
    """
    key = raw.strip().lower()
    if not key:
        raise ValueError("pusty identyfikator klienta")
    key = _ALIASES.get(key, key)
    if key not in KNOWN_CLIENTS:
        allowed = ", ".join(KNOWN_CLIENTS)
        raise ValueError(f"nieznany klient `{raw}` (dozwolone: {allowed}, all, alias copilot→vscode)")
    return key


def parse_clients(value: str | None) -> list[str]:
    """
    Parsuj wartość ``--clients`` / ``GUIDES_CLIENTS``.

    Args:
        value: ``all``, pojedynczy klient, albo lista po przecinku.
            ``None`` / pusty string → ``["all"]`` (semantyka: wszystkie).

    Returns:
        list[str]: Albo ``["all"]``, albo posortowana unikalna lista kanonicznych id
        w kolejności ``KNOWN_CLIENTS``.

    Raises:
        ValueError: Gdy któryś token jest nieprawidłowy.
    """
    if value is None or not str(value).strip():
        return ["all"]
    raw = str(value).strip()
    if raw.lower() == "all":
        return ["all"]
    seen: set[str] = set()
    ordered: list[str] = []
    for part in raw.split(","):
        cid = normalize_client_id(part)
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    # Stabilna kolejność jak w KNOWN_CLIENTS
    return [c for c in KNOWN_CLIENTS if c in seen]


def expand_clients(clients: list[str]) -> list[str]:
    """
    Rozwiń ``all`` do pełnej listy ``KNOWN_CLIENTS``.

    Args:
        clients: Wynik ``parse_clients``.

    Returns:
        list[str]: Konkretne id klientów do instalacji.
    """
    if clients == ["all"] or "all" in clients:
        return list(KNOWN_CLIENTS)
    return list(clients)


def format_clients_arg(clients: list[str]) -> str:
    """
    Sformatuj listę do zapisu w mcp.json (``all`` albo ``cursor,claude``).

    Args:
        clients: Wynik ``parse_clients`` (przed expand).

    Returns:
        str: Wartość flagi ``--clients``.
    """
    if clients == ["all"]:
        return "all"
    return ",".join(clients)
