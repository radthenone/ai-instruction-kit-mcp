"""Odpowiedzi agenta idą w języku Profilu, niezależnie od języka wejścia (#248).

Dwie warstwy: teksty źródeł (reguła, linie w orkiestratorach, stopka headless) oraz
render bootstrapu u każdego klienta (`--clients all`, pl i en): plik instrukcji niesie
regułę, a hook przypomnienia Claude istnieje tylko przy `language` ≠ en.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, posix_path, resolve_bash

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = KIT_ROOT / "templates"
AGENTS = TEMPLATES / "shared" / "agents"

INDEPENDENCE = "niezależnie od języka wejścia"

# Źródła instrukcji z regułą (kopie u klientów renderuje bootstrap).
INSTRUCTION_SOURCES = (
    KIT_ROOT / "AGENTS.md",
    TEMPLATES / "AGENTS.md",
    TEMPLATES / "shared" / "rules" / "use-guides.md",
    TEMPLATES / "cursor" / "rules" / "use-guides.mdc",
    TEMPLATES / "kiro" / "steering" / "instruction-kit.md",
)

# Orkiestratory, które odpalają subagentów: prompt dla subagenta idzie w języku z get_language.
SUBAGENT_ROLES = (
    "night-run",
    "review-architecture",
    "review-backend",
    "review-bugbot",
    "review-frontend",
    "review-security",
)

# Agenci bez subagentów: linia tylko o języku odpowiedzi i hand-backu.
PLAIN_ROLES = (
    "git-start",
    "git-commit",
    "git-end",
    "git-check",
    "review-edge",
    "review-tests",
    "review-ui",
)

# Render: plik, który klient czyta jako instrukcje, i czy ma w nim być reguła wprost.
RENDER_RULE_FILES = {
    "AGENTS.md": True,
    ".cursor/rules/use-guides.mdc": True,
    ".kiro/steering/instruction-kit.md": True,
}

HOOK_COMMAND = "language-reminder.mjs"


class SourceRuleTest(unittest.TestCase):
    def test_instruction_sources_state_independence_from_input_language(self) -> None:
        for source in INSTRUCTION_SOURCES:
            with self.subTest(source=str(source.relative_to(KIT_ROOT))):
                self.assertIn(INDEPENDENCE, source.read_text(encoding="utf-8"))

    def test_output_and_input_are_split_in_agents_template(self) -> None:
        text = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("wejście: prompty, skille, wyniki narzędzi, powiadomienia, hand-backi", text)

    def test_subagent_orchestrators_name_prompt_handback_and_get_language(self) -> None:
        for name in SUBAGENT_ROLES:
            with self.subTest(agent=name):
                text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("prompt dla subagenta", text)
                self.assertIn("hand-back", text)
                self.assertIn("get_language", text)
                self.assertNotIn("także gdy skill review", text)

    def test_plain_agents_name_language_without_subagent_prompt(self) -> None:
        for name in PLAIN_ROLES:
            with self.subTest(agent=name):
                text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("get_language", text)
                self.assertIn(INDEPENDENCE, text)
                self.assertNotIn("prompt dla subagenta", text)

    def test_night_run_ticket_prompt_forces_handback_language(self) -> None:
        text = (AGENTS / "night-run.md").read_text(encoding="utf-8")
        start = text.index("Ticket #<N>, baza <BASE>")
        self.assertIn("get_language", text[start:])

    def test_headless_md_and_mjs_footer_name_language(self) -> None:
        md = (AGENTS / "headless.md").read_text(encoding="utf-8")
        self.assertIn("get_language", md)
        self.assertIn(INDEPENDENCE, md)
        mjs = (TEMPLATES / "shared" / "headless" / "headless.mjs").read_text(encoding="utf-8")
        self.assertIn("Język odpowiedzi", mjs)


class RenderTest(unittest.TestCase):
    """Bootstrap na prawdziwym profilu: reguła trafia do plików klientów, hook zależy od języka."""

    @classmethod
    def render(cls, language: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix=f"kit-agent-language-{language}-"))
        target = tmp / "generated"
        (target / ".ai").mkdir(parents=True)
        (target / ".ai" / "project.profile.yaml").write_text(
            f"name: language-render\nlanguage: {language}\nclients: all\n\nbackend: fastapi\nweb: react\n"
            "mobile: none\n\ncodegen: none\n",
            encoding="utf-8",
        )
        bash = resolve_bash()
        if not bash:
            shutil.rmtree(tmp, ignore_errors=True)
            if is_ci():
                raise AssertionError("brak bash na CI — render języka musi być sprawdzony")
            raise unittest.SkipTest("brak bash — pomijam render języka")
        result = subprocess.run(
            [
                bash, "--noprofile", "--norc",
                posix_path(KIT_ROOT / "scripts" / "bootstrap-project.sh"),
                str(target), "--clients", "all", "--language", language, "--from", str(KIT_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise AssertionError(f"bootstrap nie wystartował ({result.returncode}): {result.stderr}")
        return tmp

    def test_pl_render_carries_rule_and_claude_hook(self) -> None:
        tmp = self.render("pl")
        try:
            target = tmp / "generated"
            for rel in RENDER_RULE_FILES:
                with self.subTest(file=rel):
                    self.assertIn(INDEPENDENCE, (target / rel).read_text(encoding="utf-8"))
            claude_md = (target / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("@AGENTS.md", claude_md)
            settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for entry in settings["hooks"].get("UserPromptSubmit", [])
                for hook in entry["hooks"]
            ]
            self.assertTrue(any(HOOK_COMMAND in c for c in commands), commands)
            self.assertTrue((target / ".claude" / "hooks" / HOOK_COMMAND).is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_en_render_has_no_claude_language_hook(self) -> None:
        tmp = self.render("en")
        try:
            target = tmp / "generated"
            settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertNotIn("UserPromptSubmit", settings["hooks"])
            self.assertFalse((target / ".claude" / "hooks" / HOOK_COMMAND).exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class LanguageReminderValuesTest(unittest.TestCase):
    """Hook przypomnienia mówi konkretny język i bazę z Profilu (#307)."""

    def _run_hook(self, profile: str, overlay: str) -> subprocess.CompletedProcess[str]:
        tmp = Path(tempfile.mkdtemp(prefix="kit-language-hook-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / ".ai").mkdir(parents=True)
        (tmp / ".ai" / "project.profile.yaml").write_text(profile, encoding="utf-8")
        (tmp / ".ai" / "project.md").write_text(overlay, encoding="utf-8")
        return subprocess.run(
            ["node", str(TEMPLATES / "claude" / HOOK_COMMAND)],
            input="{}",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=tmp,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp)},
            timeout=30,
            check=False,
        )

    def test_hook_names_language_and_base_from_profile(self) -> None:
        if not shutil.which("node"):
            if is_ci():
                self.fail("brak node w CI — hook języka musi się wykonać")
            self.skipTest("brak node w PATH")

        result = self._run_hook(
            "name: t\nlanguage: pl\nbackend: fastapi\nweb: none\nmobile: none\n",
            "# Overlay\n\nbase: dev\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"(?<![a-z])pl(?![a-z])|polsk")
        self.assertRegex(result.stdout, r"(?<![\w/-])dev(?![\w/-])")
        self.assertIn("Priorytet".lower(), result.stdout.lower())

    def _require_node(self) -> None:
        if not shutil.which("node"):
            if is_ci():
                self.fail("brak node w CI — hook języka musi się wykonać")
            self.skipTest("brak node w PATH")

    def test_empty_base_does_not_swallow_next_line(self) -> None:
        """Puste ``base:`` = brak bazy, nie treść następnej linii (np. ``##``)."""
        self._require_node()
        result = self._run_hook(
            "name: t\nlanguage: pl\n", "# Overlay\n\nbase:\n## Komendy\n"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("`##`", result.stdout)
        self.assertIn("brak `base:`", result.stdout)

    def test_language_tag_matches_resolver(self) -> None:
        """``en-US`` to angielski, tak jak w ``normalize_language`` resolvera."""
        self._require_node()
        result = self._run_hook("name: t\nlanguage: en-US\n", "# Overlay\n\nbase: dev\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Project language: `en`", result.stdout)


if __name__ == "__main__":
    unittest.main()
