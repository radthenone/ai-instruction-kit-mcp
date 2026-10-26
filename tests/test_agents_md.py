"""Odświeżanie części kitowej ``AGENTS.md`` z blokiem ``project:agents`` (#269).

Ten sam model co ``BUGBOT.md`` (``guides.bugbot_md``): część kita z szablonu przy
każdym reloadzie, własna treść projektu w chronionym bloku. Blok ``## Agent skills``
(kontrakt Matta, ``matt_contract``) to treść kita spoza szablonu — nie trafia do bloku
projektu i nie wywołuje migracji.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.bugbot_md import SyncResult, extract_rules, is_pristine, render, sync_file

CURRENT = """# AGENTS.md

## Warstwy

- reguła kita (nowa)

## Reguły projektu

<!-- project:agents -->
<!-- Wpisz tu reguły własne projektu — ten blok przechodzi przez `kit-ai reload` bez zmian. -->
<!-- /project:agents -->
"""

# Stara wersja szablonu: bez bloku, ze starymi guardami.
OLD = """# AGENTS.md

## Warstwy

- reguła kita (stara): `gate-push.sh`
"""

AGENT_SKILLS = """## Agent skills

### Issue tracker

GitHub issues (`gh` CLI). See `docs/agents/issue-tracker.md`.
"""


class TestAgentsSync(unittest.TestCase):
    def _sync(self, dest_text: str, history: list[str]) -> tuple[str, SyncResult]:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "AGENTS.md"
            source = Path(tmp) / "template.md"
            dest.write_text(dest_text, encoding="utf-8", newline="\n")
            source.write_text(CURRENT, encoding="utf-8", newline="\n")
            result = sync_file(dest, source, history=history, label="AGENTS.md", block="agents")
            return dest.read_text(encoding="utf-8"), result

    def test_untouched_old_file_is_replaced_with_current_template(self) -> None:
        text, _ = self._sync(OLD, [CURRENT, OLD])

        self.assertEqual(text, CURRENT)

    def test_own_lines_move_into_project_agents_block(self) -> None:
        text, result = self._sync(OLD + "\n## Nasze\n\n- Nasza reguła A\n", [CURRENT, OLD])

        self.assertEqual(result.action, "migrated")
        self.assertEqual(extract_rules(text, "agents"), "\n## Nasze\n\n- Nasza reguła A\n")
        self.assertNotIn("gate-push.sh", text)
        self.assertIn("- reguła kita (nowa)", text)
        self.assertIn("project:agents", result.message)

    def test_block_survives_and_kit_part_is_refreshed(self) -> None:
        rules = "\n- Nasza reguła B\n"
        dest = render(CURRENT, "", rules, block="agents").replace("(nowa)", "(zmieniona ręcznie)")

        text, result = self._sync(dest, [])

        self.assertEqual(result.action, "refreshed")
        self.assertEqual(extract_rules(text, "agents"), rules)
        self.assertIn("- reguła kita (nowa)", text)

    def test_agent_skills_section_stays_outside_block(self) -> None:
        """Blok Matta dopisany po szablonie nie jest „własną linią” projektu."""
        text, result = self._sync(OLD + "\n" + AGENT_SKILLS, [CURRENT, OLD])

        self.assertEqual(text, CURRENT + "\n" + AGENT_SKILLS)
        self.assertEqual(result.moved, [])

    def test_current_file_with_agent_skills_is_unchanged(self) -> None:
        text, result = self._sync(CURRENT + "\n" + AGENT_SKILLS, [])

        self.assertEqual(result.action, "unchanged")
        self.assertEqual(text, CURRENT + "\n" + AGENT_SKILLS)

    def test_edited_kit_lines_without_block_are_uncertain_one_line(self) -> None:
        dest = OLD.replace("(stara)", "(po naszemu)")

        text, result = self._sync(dest, [CURRENT, OLD])

        self.assertEqual(result.action, "uncertain")
        self.assertEqual(text, dest)
        self.assertEqual(len(result.message.splitlines()), 1, result.message)
        self.assertIn("AGENTS.md", result.message)
        self.assertIn("project:agents", result.message)
        self.assertIn('/kit-project-edit "napraw zgłoszenia doctora"', result.message)

    def test_real_template_has_block_and_is_pristine(self) -> None:
        template = (
            Path(__file__).resolve().parents[1] / "templates" / "AGENTS.md"
        ).read_text(encoding="utf-8")

        self.assertIsNotNone(extract_rules(template, "agents"))
        self.assertTrue(is_pristine(render(template, "", block="agents"), template, "agents"))


if __name__ == "__main__":
    unittest.main()
