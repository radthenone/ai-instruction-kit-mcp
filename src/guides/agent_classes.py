"""
Klasyfikacja agentów kita (`classification: procedure | code`, #316).

Jedno źródło dla `scripts/claude_settings.py` (matcher ponytaila w `.claude/settings.local.json`)
i `kit-ai doctor`. Agent bez pola albo z nieznaną wartością to błąd — nowy agent kita
musi dostać klasyfikację w szablonie.
"""

from __future__ import annotations

import re
from pathlib import Path

CLASSIFICATIONS = frozenset({"procedure", "code"})
MATCHER_KEY = "PONYTAIL_SUBAGENT_MATCHER"

# Wzorzec matchera kita: rozpoznaje też wartości wyrenderowane z innej listy agentów.
KIT_MATCHER_RE = re.compile(r"\^\(\?!\(\?:[a-z0-9|-]+\)\$\)\.\*")
_AGENT_NAME_RE = re.compile(r"[a-z0-9-]+")


def _classification(agent_file: Path) -> str | None:
    """Wartość `classification:` z frontmattera albo ``None``."""
    lines = agent_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("classification:"):
            return line.partition(":")[2].strip()
    return None


def agent_classifications(agents_dir: Path) -> dict[str, str]:
    """
    Klasyfikacja każdego agenta z katalogu szablonów.

    Args:
        agents_dir: Katalog szablonów agentów (`templates/shared/agents`).

    Returns:
        dict[str, str]: Nazwa agenta → `procedure` albo `code`.

    Raises:
        ValueError: Agent bez klasyfikacji, z nieznaną wartością albo z nazwą spoza `[a-z0-9-]`.
    """
    result: dict[str, str] = {}
    for src in sorted(agents_dir.glob("*.md")):
        value = _classification(src)
        if value not in CLASSIFICATIONS:
            raise ValueError(f"{src.name}: classification musi być procedure|code, jest {value!r}")
        if not _AGENT_NAME_RE.fullmatch(src.stem):
            raise ValueError(f"{src.name}: nazwa agenta spoza [a-z0-9-]")
        result[src.stem] = value
    return result


def procedure_agents(agents_dir: Path) -> list[str]:
    """Posortowane nazwy agentów `procedure`."""
    return sorted(name for name, value in agent_classifications(agents_dir).items() if value == "procedure")


def ponytail_matcher(agents_dir: Path) -> str:
    """
    Regex `PONYTAIL_SUBAGENT_MATCHER`: pasuje do wszystkiego poza agentami procedur.

    Raises:
        ValueError: Brak agentów procedur — matcher byłby `.*` i nic by nie wykluczał.
    """
    names = procedure_agents(agents_dir)
    if not names:
        raise ValueError(f"brak agentów procedure w {agents_dir}")
    return f"^(?!(?:{'|'.join(names)})$).*"
