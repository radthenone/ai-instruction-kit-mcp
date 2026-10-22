"""Night-run budzi orkiestratora tylko przy pracy do zrobienia (#229).

Watchdog w tle + rzadki cron jako fallback, ``CronList`` przed ``CronCreate``,
zero narzędzi na powiadomienie o pracy w tle, ``## Stan`` równolegle z Agent i pomiar
tur orkiestratora w raporcie. Sprawdza szablon i kopie u klientów po reloadzie.
"""

from __future__ import annotations

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
CLAUDE_ONLY = "tylko Claude Code"


class TestNightRunWatchdog(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def _section(self, start: str, end: str) -> str:
        return self.text.split(start, 1)[1].split(end, 1)[0]

    def test_watchdog_runs_in_background_and_wakes_only_on_anomaly(self) -> None:
        self.assertNotIn("### 7. Heartbeat", self.text)
        self.assertNotIn("13,33,53", self.text)
        self.assertIn("### 7. Watchdog i cron", self.text)
        watchdog = self._section("### 7. Watchdog i cron", "## Łańcuch na ticket")
        self.assertIn("run_in_background", watchdog)
        self.assertIn("20 min", watchdog)
        self.assertIn("przyrost logu `/headless`", watchdog)
        self.assertIn("postęp PR", watchdog)
        self.assertIn("tylko przy anomalii", watchdog)
        self.assertIn("Pauza 429 **nie jest** anomalią", watchdog)

    def test_cron_stays_as_fallback(self) -> None:
        watchdog = self._section("### 7. Watchdog i cron", "## Łańcuch na ticket")
        self.assertIn("Cron co 60 min", watchdog)
        self.assertIn("fallback", watchdog)
        self.assertIn("na cronie", watchdog)

    def test_cron_list_before_cron_create_on_resume(self) -> None:
        watchdog = self._section("### 7. Watchdog i cron", "## Łańcuch na ticket")
        self.assertIn("`CronList` przed `CronCreate`", watchdog)
        self.assertLess(watchdog.index("`CronList`"), watchdog.index("`CronCreate`"))
        self.assertIn("także przy wznowieniu sesji", watchdog)

    def test_notification_costs_no_tool_calls(self) -> None:
        self.assertIn("is waiting on its own background work", self.text)
        self.assertIn("nie wywołuje żadnych narzędzi", self.text)
        self.assertIn("odpowiada jedną linią", self.text)
        notification = self.text.split("**Powiadomienie", 1)[1].split("\n\n", 1)[0]
        self.assertIn(CLAUDE_ONLY, notification)

    def test_subagent_keeps_turn_while_headless_runs(self) -> None:
        self.assertIn("Nie kończysz tury, dopóki `/headless` działa w tle", self.text)

    def test_watchdog_relaunched_once_and_skips_429(self) -> None:
        watchdog = self._section("### 7. Watchdog i cron", "## Łańcuch na ticket")
        self.assertIn("Jeden watchdog naraz", watchdog)
        self.assertIn("pauza limitu od", watchdog)
        tick = self.text.split("## Tick watchdoga i crona", 1)[1]
        self.assertIn("odpala watchdoga", tick)

    def test_subagent_waits_with_foreground_bash(self) -> None:
        self.assertIn("pierwszoplanowym Bash z limitem czasu", self.text)

    def test_state_written_in_same_tool_call_as_agent(self) -> None:
        chain = self._section("## Łańcuch na ticket", "## Prompt ticketu")
        step1 = chain.split("1. **Subagent ticketu**", 1)[1].split("2. **Review.**", 1)[0]
        self.assertIn("w tym samym wywołaniu narzędzi co uruchomienie", " ".join(step1.split()))
        self.assertNotIn(CLAUDE_ONLY, step1)

    def test_report_counts_orchestrator_turns_and_cache_read(self) -> None:
        report = self.text.split("## NIGHT-RUN REPORT", 1)[1]
        self.assertIn("Orkiestrator (tylko Claude Code): <tury> tur / <cache_read> cache_read", report)
        measurement = self._section("## Pomiar kosztu ticketu", "## NIGHT-RUN REPORT")
        self.assertIn("transkrypcie sesji głównej", measurement)

    def test_claude_only_rules_are_labelled(self) -> None:
        watchdog = self._section("### 7. Watchdog i cron", "## Łańcuch na ticket")
        self.assertIn(CLAUDE_ONLY, watchdog.splitlines()[0])
        measurement_heading = next(
            ln for ln in self.text.splitlines() if ln.startswith("## Pomiar kosztu ticketu")
        )
        self.assertIn(CLAUDE_ONLY, measurement_heading)

    def test_reload_refreshed_client_copies(self) -> None:
        def body(text: str) -> str:
            lines = text.split("\n---\n", 1)[1].strip().splitlines()
            return "\n".join(ln for ln in lines if not ln.startswith("<!-- "))

        expected = body(self.text)
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(expected, body(copy))


if __name__ == "__main__":
    unittest.main()
