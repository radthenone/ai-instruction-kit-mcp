"""Testy kontraktu szablonu night-run dla reloadu plików kita po MERGED (#467).

Sprawdzają:
- krok reloadu po MERGED w night-run.md,
- warunek źródła kita (manifest.yaml w root) i ścieżek templates/ oraz src/guides/,
- pominięcie w repo aplikacji (brak manifest.yaml w root),
- warunek czystego drzewa (git status --porcelain puste) przed pullem; brudne drzewo -> pominięcie z wpisem w raporcie,
- przy czystym drzewie: git fetch origin, git pull --ff-only origin "$BASE" na bazie (bez przełączania branchy), potem kit-ai reload .,
- orkiestrator czyta ponownie zmienione sekcje procedury; subagenci i agenci /git-* biorą nową wersję przy starcie,
- błąd reloadu -> wpis w raporcie nocy i utworzenie nowego issue (gh issue create),
- obecność szwów reloadu we wszystkich kopiach u klientów (COPIES).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)


def _section(text: str, start: str, end: str) -> str:
    """Zwraca fragment tekstu między nagłówkami z normalizacją białych znaków."""
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


class TestNightRunKitReloadContract(unittest.TestCase):
    def setUp(self) -> None:
        self.night_run = TEMPLATE.read_text(encoding="utf-8")
        self.chain = _section(self.night_run, "## Łańcuch na ticket", "## Zlecenie ticketu")

    def test_reload_step_defined_after_merged(self) -> None:
        """Krok reloadu znajduje się w łańcuchu po MERGED."""
        self.assertIn("MERGED", self.chain)
        self.assertRegex(self.chain, r"(?i)reload.*kit|odświeżeni.*kit")
        merged_pos = self.chain.index("MERGED")
        reload_match = re.search(r"(?i)reload.*kit|odświeżeni.*kit", self.chain)
        self.assertIsNotNone(reload_match)
        assert reload_match is not None
        self.assertGreater(reload_match.start(), merged_pos)

    def test_kit_source_and_paths_condition(self) -> None:
        """Warunek repo kita (manifest.yaml w root) oraz ścieżek templates/ i src/guides/, pominięcie w repo aplikacji."""
        self.assertIn("manifest.yaml", self.chain)
        self.assertIn("templates/", self.chain)
        self.assertIn("src/guides/", self.chain)
        self.assertRegex(self.chain, r"(?:repo aplikacji|brak `?manifest\.yaml`?).*(?:pominięt|pominiet)")

    def test_clean_working_tree_condition_and_dirty_tree_skip(self) -> None:
        """Warunek czystego drzewa (git status --porcelain puste); brudne drzewo -> pominięcie z wpisem w raporcie."""
        self.assertIn("git status --porcelain", self.chain)
        self.assertRegex(
            self.chain,
            r"(?:brudne drzewo|niepuste).*(?:pominięc|pominiet|pomiń|pomin).*(?:raporc|wpis)",
        )

    def test_pull_ff_only_and_reload_command(self) -> None:
        """Przy czystym drzewie: git fetch origin, git pull --ff-only origin \"$BASE\" na bazie (bez przełączania branchy), potem kit-ai reload ."""
        self.assertIn("git fetch origin", self.chain)
        self.assertIn('git pull --ff-only origin "$BASE"', self.chain)
        self.assertRegex(self.chain, r"bez przełączania branchy|bez przelaczania branchy")
        self.assertIn("kit-ai reload .", self.chain)

    def test_orchestrator_re_reads_and_subagents_take_new_version(self) -> None:
        """Orkiestrator czyta ponownie zmienione sekcje procedury; subagenci i agenci /git-* biorą nową wersję sami przy starcie."""
        self.assertRegex(
            self.chain,
            r"(?:orkiestrator.*czyta ponownie|ponown.*czyta.*procedur)",
        )
        self.assertRegex(
            self.chain,
            r"(?:subagenci|agenci.*\/git-\*).*(?:biorą nową wersję|biora nowa wersje|przy starcie)",
        )

    def test_reload_error_handling_creates_issue(self) -> None:
        """Błąd reloadu -> wpis w raporcie nocy i utworzenie nowego issue przez gh issue create."""
        self.assertRegex(
            self.chain,
            r"(?:błąd reloadu|blad reloadu|błąd.*reload).*(?:raporc|wpis)",
        )
        self.assertIn("gh issue create", self.chain)

    def test_all_rendered_client_copies_contain_reload_rules(self) -> None:
        """Kopie wyrenderowane dla klientów zawierają kluczowe szwy kontraktu reloadu kita."""
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                chain = _section(copy, "## Łańcuch na ticket", "## Zlecenie ticketu")
                self.assertIn("manifest.yaml", chain)
                self.assertIn("templates/", chain)
                self.assertIn("src/guides/", chain)
                self.assertIn("git status --porcelain", chain)
                self.assertIn('git pull --ff-only origin "$BASE"', chain)
                self.assertIn("kit-ai reload .", chain)
                self.assertIn("gh issue create", chain)


if __name__ == "__main__":
    unittest.main()
