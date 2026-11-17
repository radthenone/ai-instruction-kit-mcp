"""Clean Slate w ``/night-run`` (#502): świeży subagent po 2. rundzie naprawczej.

Sprawdzamy odczyt opcjonalnej sekcji ``night-run.clean-slate`` z Profilu (i linię
w nagłówku CTX), regułę po 2. rundzie z warunkiem bezpieczeństwa resetu, format
notatki dla nowego subagenta oraz mapowanie na świeży ``delegate_task`` w karcie T3.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.night_ctx import clean_slate_config, render_night_ctx

KIT_ROOT = Path(__file__).resolve().parents[1]
SHARED = KIT_ROOT / "templates" / "shared"
NIGHT_RUN = SHARED / "agents" / "night-run.md"
TICKET = SHARED / "agents" / "night-run-ticket.md"
T3_CARD = SHARED / "night-run" / "t3.md"
PROFILE_TEMPLATE = KIT_ROOT / "templates" / "project.profile.yaml"
NOTE = "Poprzednie podejście zawiodło z powodu błędu X. Zacznij od czystej karty i unikaj ścieżki Y"


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class TestCleanSlateProfile(unittest.TestCase):
    def test_reads_section(self) -> None:
        profile = {
            "night-run": {
                "clean-slate": {"provider": "claudeAgent", "model": "claude-opus-5-5", "effort": "high"}
            }
        }
        self.assertEqual(
            clean_slate_config(profile),
            {"provider": "claudeAgent", "model": "claude-opus-5-5", "effort": "high"},
        )

    def test_missing_or_malformed_section_is_empty(self) -> None:
        for profile in ({}, {"night-run": None}, {"night-run": {"clean-slate": "opus"}}, {"night-run": []}):
            with self.subTest(profile=profile):
                self.assertEqual(clean_slate_config(profile), {})

    def test_ignores_unknown_and_empty_keys(self) -> None:
        profile = {"night-run": {"clean-slate": {"model": "opus", "effort": "", "temperature": 1}}}
        self.assertEqual(clean_slate_config(profile), {"model": "opus"})

    def test_ctx_header_line_only_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ai").mkdir()
            profile = root / ".ai" / "project.profile.yaml"
            profile.write_text("name: demo\nlanguage: pl\n", encoding="utf-8")
            self.assertNotIn("Clean Slate", render_night_ctx(root, host="local"))
            profile.write_text(
                "name: demo\nlanguage: pl\nnight-run:\n  clean-slate:\n    model: opus\n    effort: high\n",
                encoding="utf-8",
            )
            out = render_night_ctx(root, host="local")
            self.assertIn("- Clean Slate: model `opus`, effort `high` — źródło: Profil", out)

    def test_profile_template_documents_section(self) -> None:
        text = PROFILE_TEMPLATE.read_text(encoding="utf-8")
        for token in ("# night-run:", "#   clean-slate:", "#     provider:", "#     model:", "#     effort:"):
            with self.subTest(token=token):
                self.assertIn(token, text)


class TestCleanSlateProcedure(unittest.TestCase):
    def test_ticket_hands_back_after_second_round(self) -> None:
        text = _flat(TICKET)
        self.assertIn("**Clean Slate:**", text)
        self.assertIn("po 2. nieudanej rundzie naprawczej", text)
        self.assertIn("hand-back `clean-slate`", text)
        self.assertIn("Clean Slate: użyty", text)

    def test_orchestrator_rule_with_note_and_model(self) -> None:
        text = _flat(NIGHT_RUN)
        self.assertIn("**Clean Slate**", text)
        self.assertIn(NOTE, text)
        self.assertIn("`night-run.clean-slate`", text)
        self.assertIn("Brak sekcji = model jak dotąd", text)
        self.assertIn("raz na ticket", text)

    def test_reset_safety_condition(self) -> None:
        text = _flat(NIGHT_RUN)
        self.assertIn("`git status --porcelain` pusty", text)
        self.assertIn("`git log origin/<branch>..HEAD` pusty", text)
        self.assertIn("inaczej needs-human bez resetu", text)
        self.assertIn("`git switch --detach origin/<BASE>`", text)
        self.assertNotIn("reset --hard origin", text)


class TestCleanSlateT3Card(unittest.TestCase):
    def test_maps_to_fresh_delegate_task(self) -> None:
        text = _flat(T3_CARD)
        self.assertIn("## 7. Clean Slate", text)
        self.assertIn("nowy `clientRequestId`", text)
        self.assertIn("`<nazwa katalogu CTX>-<numer ticketu>-clean-slate`", text)
        self.assertIn("`target.providerInstanceId`", text)
        self.assertIn("`target.model`", text)
        self.assertIn('`{id: "effort"', text)
        self.assertIn("warunek bezpieczeństwa z `night-run`", text)


if __name__ == "__main__":
    unittest.main()
