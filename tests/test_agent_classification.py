"""Testy klasyfikacji agentów kita (procedura vs kod, #316).

Każdy agent instalowany przez kit ma przypisaną klasyfikację `procedure` lub `code`.
Agenci `subagent-backend` i `subagent-frontend` to `code`, a wszyscy pozostali to `procedure`.
Brak klasyfikacji powoduje błąd testu.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from guides.agent_classes import agent_classifications, ponytail_matcher  # noqa: E402

SHARED_AGENTS = ROOT / "templates" / "shared" / "agents"

CODE_AGENTS = frozenset({"subagent-backend", "subagent-frontend"})
VALID_CLASSIFICATIONS = frozenset({"procedure", "code"})


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    return meta


def get_agent_classification(agent_file: Path) -> str:
    meta = parse_frontmatter(agent_file.read_text(encoding="utf-8"))
    classification = meta.get("classification")
    if not classification:
        raise ValueError(f"Agent {agent_file.name} nie ma pola 'classification:' we frontmatterze")
    return classification.lower()


class AgentClassificationTest(unittest.TestCase):
    def test_every_shared_agent_has_valid_classification(self) -> None:
        agents = sorted(SHARED_AGENTS.glob("*.md"))
        self.assertGreater(len(agents), 0, "Brak agentów w templates/shared/agents")
        missing_or_invalid: list[str] = []

        for agent in agents:
            try:
                classification = get_agent_classification(agent)
                if classification not in VALID_CLASSIFICATIONS:
                    missing_or_invalid.append(
                        f"{agent.name}: nieznana klasyfikacja '{classification}'"
                    )
            except ValueError as e:
                missing_or_invalid.append(str(e))

        self.assertEqual(
            missing_or_invalid,
            [],
            "Wszyscy agenci kita muszą mieć prawidłową klasyfikację (procedure|code)",
        )

    def test_only_subagent_backend_and_frontend_are_classified_as_code(self) -> None:
        agents = sorted(SHARED_AGENTS.glob("*.md"))
        code_found: set[str] = set()

        for agent in agents:
            classification = get_agent_classification(agent)
            if classification in ("code",):
                code_found.add(agent.stem)
            else:
                self.assertIn(
                    classification,
                    ("procedure",),
                    f"Agent {agent.stem} ma niespodziewaną klasyfikację",
                )

        self.assertEqual(
            code_found,
            CODE_AGENTS,
            "Tylko subagent-backend i subagent-frontend mogą mieć klasyfikację 'code'",
        )


class SharedClassificationModuleTest(unittest.TestCase):
    def test_unknown_or_missing_classification_raises(self) -> None:
        """Nieznana albo brakująca klasyfikacja to błąd, nie cichy fallback."""
        for front in ("classification: kod\n", ""):
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, "x.md").write_text(f"---\nname: x\n{front}---\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    agent_classifications(Path(tmp))

    def test_matcher_with_no_procedure_agents_raises(self) -> None:
        """Pusta lista procedur nie może dać matchera `.*`."""
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "subagent-backend.md").write_text("---\nclassification: code\n---\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ponytail_matcher(Path(tmp))


if __name__ == "__main__":
    unittest.main()
