"""Kontrola zielonej bazy night-run: `headSha` z CI musi być HEAD bazy (#411).

Push na `dev` nie uruchamia `ci.yml`, więc `gh run list --branch dev` czyta stary,
zielony run z innego commita. Seam: tekst szablonu `templates/shared/agents/night-run.md`
(krok „Baza zielona”), parytet kopii pilnuje `test_generated_artifacts.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"


def _section(text: str, start: str, end: str) -> str:
    """Zwraca fragment szablonu między znacznikami, z normalizacją białych znaków."""
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


class TestNightRunBaseCheck(unittest.TestCase):
    def setUp(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.section = _section(text, "### 3. Baza zielona", "### 4. Kolejka")

    def test_ci_run_head_sha_is_compared_with_base_head(self) -> None:
        self.assertIn("Porównaj `headSha` z `git rev-parse origin/$BASE`", self.section)

    def test_red_halts_only_when_head_sha_matches_base(self) -> None:
        self.assertIn("Zgodne (run na HEAD bazy): czerwony → **halt** (przypadek C)", self.section)
        # Stary czerwony run z innego commita nie może blokować nocy (na dev nic go nie odświeży).
        self.assertNotIn("Czerwony → **halt**", self.section)

    def test_mismatched_head_sha_falls_back_to_fast_gates_not_halt(self) -> None:
        self.assertIn("Różne (run z innego commita", self.section)
        self.assertIn("ani zielony, ani czerwony nie rozstrzyga → bramki szybkie na `origin/$BASE`", self.section)


if __name__ == "__main__":
    unittest.main()
