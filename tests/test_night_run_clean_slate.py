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

    def test_reads_target_shape_section(self) -> None:
        """Kształt wpisu target z #515 w night-run.clean-slate (#546)."""
        profile = {
            "night-run": {
                "clean-slate": {
                    "target": "claude.heavy",
                    "options": [{"id": "effort", "value": "high"}],
                }
            }
        }
        self.assertEqual(
            clean_slate_config(profile),
            {"target": "claude.heavy", "options": [{"id": "effort", "value": "high"}]},
        )

    def test_missing_or_malformed_section_is_empty(self) -> None:
        for profile in ({}, {"night-run": None}, {"night-run": {"clean-slate": "opus"}}, {"night-run": []}):
            with self.subTest(profile=profile):
                self.assertEqual(clean_slate_config(profile), {})

    def test_ignores_unknown_and_empty_keys(self) -> None:
        profile = {"night-run": {"clean-slate": {"model": "opus", "effort": "", "temperature": 1, "provider": ["x"]}}}
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
        for token in ("# night-run:", "#   clean-slate:", "#     target:", "#     options:"):
            with self.subTest(token=token):
                self.assertIn(token, text)


class TestCleanSlateProcedure(unittest.TestCase):
    def test_ticket_clean_slate_on_demand_and_trigger(self) -> None:
        text = _flat(TICKET)
        self.assertIn("**Clean Slate: tylko na żądanie (`clean-slate: on`):**", text)
        self.assertIn("clean-slate: on", text)
        self.assertIn("hand-back `clean-slate`", text)
        self.assertIn("Clean Slate: użyty", text)
        self.assertIn("gdy wyczerpie się pula 3 albo 6 albo zadziała bezpiecznik", text)

    def test_ticket_keeps_clean_slate_branch_name(self) -> None:
        text = _flat(TICKET)
        self.assertIn(
            "Wyjątek: gdy parametry zlecenia zawierają linię „Clean Slate: użyty”, nie zmieniasz nazwy brancha"
            " na kanoniczną; pracujesz na `<typ>/<N>-<slug>-clean-slate`",
            text,
        )

    def test_trigger_includes_pool_exhaustion_and_loop_guards(self) -> None:
        text = _flat(NIGHT_RUN)
        self.assertIn("gdy wyczerpie się pula 3 albo 6 albo zadziała bezpiecznik", text)
        self.assertIn("najpierw Clean Slate, gdy jeszcze nie użyty i warunek bezpieczeństwa spełniony", text)
        self.assertIn("Bez `clean-slate: on` Clean Slate nie rusza", text)

    def test_orchestrator_rule_with_note_and_model(self) -> None:
        text = _flat(NIGHT_RUN)
        self.assertIn("**Clean Slate: tylko na żądanie (`clean-slate: on`).**", text)
        self.assertIn(NOTE, text)
        self.assertIn("`night-run.clean-slate`", text)
        self.assertIn("Brak bloku przy `clean-slate: on` = model ticketu jak dotąd", text)
        self.assertIn("raz na ticket", text)
        self.assertIn("Twardy sufit kosztu: domyślnie 9 delegacji na ticket (3 + 6)", text)
        self.assertIn("Z `clean-slate: on` 10 delegacji na ticket (3 + 6 + 1 Clean Slate)", text)

    def test_clean_slate_hands_over_coderabbit_round_counter(self) -> None:
        """Nowy subagent po Clean Slate dostaje `coderabbit-rundy` z `## Stan`; limit 6 obejmuje cały ticket (#546)."""
        text = _flat(NIGHT_RUN)
        self.assertIn("linię `coderabbit-rundy: #<N> <R>` z `## Stan`", text)
        self.assertIn("limit 6 obejmuje cały ticket", text)

    def test_reset_safety_condition(self) -> None:
        text = _flat(NIGHT_RUN)
        self.assertIn("`git status --porcelain` pusty", text)
        self.assertIn("`git log origin/<branch>..HEAD` pusty", text)
        self.assertIn("needs-human bez resetu", text)
        self.assertIn("`git switch --no-overwrite-ignore --detach origin/<BASE>`", text)
        self.assertNotIn("`git switch --detach origin/<BASE>`", text)
        self.assertIn("odmowa przełączenia (kolizja z plikiem ignorowanym) → needs-human bez resetu", text)
        self.assertNotIn("reset --hard origin", text)
        self.assertIn("błąd fetch albo komendy", text)
        self.assertIn("własny sufit rund", text)


class TestCleanSlateT3Card(unittest.TestCase):
    def test_maps_to_fresh_delegate_task(self) -> None:
        text = _flat(T3_CARD)
        self.assertIn("## 7. Clean Slate", text)
        self.assertIn("clean-slate: on", text)
        self.assertIn("nowy `clientRequestId`", text)
        self.assertIn("`<nazwa katalogu CTX>-<numer ticketu>-clean-slate`", text)
        self.assertIn("`target.providerInstanceId`", text)
        self.assertIn("`target.model`", text)
        self.assertIn("wpis `target` z #515", text)
        self.assertIn("warunek bezpieczeństwa z `night-run`", text)
        self.assertIn("linię `coderabbit-rundy: #<N> <R>` z `## Stan`", text)
        self.assertIn("limit 6 rund po pushu obejmuje cały ticket", text)
        self.assertIn("10 delegacji na ticket (3 + 6 + 1 Clean Slate)", text)

    def test_records_stage_before_removing_worktree(self) -> None:
        text = _flat(T3_CARD)
        section = text[text.index("## 7. Clean Slate") :]
        steps = [
            "1. zapisuje w `## Stan` etap `clean-slate: w toku` ze starym `taskId`, notatką o błędzie X i ścieżce Y"
            " oraz ścieżką worktree",
            "2. usuwa worktree ticketu (`node .ai/worktree.mjs remove <katalog>`)",
            "3. zapisuje w `## Stan` etap `clean-slate: worktree usunięty`",
            "4. woła świeży `delegate_task`",
            "5. zapisuje nowy `taskId` i nowy `childThreadId` w `## Stan` w miejsce starych",
        ]
        positions = [section.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))

    def test_resume_reads_recorded_stage_and_note(self) -> None:
        section = _flat(T3_CARD)[_flat(T3_CARD).index("## 7. Clean Slate") :]
        self.assertIn("notatkę zapisaną w kroku 1", section)
        self.assertIn("z `## Stan`, nie z pamięci sesji", section)
        self.assertIn("etap `clean-slate: w toku` i worktree istnieje → dokończ usunięcie i przejdź do kroku 3", section)
        self.assertIn("etap `clean-slate: w toku` i worktree już nie istnieje → przejdź do kroku 4", section)
        self.assertIn("ten sam `clientRequestId`", section)
        self.assertIn("nigdy drugi `delegate_task` z innym `clientRequestId` dla tego samego Clean Slate", section)


if __name__ == "__main__":
    unittest.main()
