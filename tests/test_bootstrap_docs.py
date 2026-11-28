"""Testy integracyjne ``scripts/bootstrap-project.sh`` dla ``BUGBOT.md`` i ``AGENTS.md``."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_bootstrap import KIT_ROOT, _BootstrapTestCase

from guides.bootstrap import run_bootstrap
from guides.bugbot_md import extract_brief, extract_brief_rules, extract_rules, is_pristine


class TestBugbotProjectRules(_BootstrapTestCase, unittest.TestCase):
    """BUGBOT.md odświeża się z szablonu, a blok ``project:rules`` zostaje (#240)."""

    def test_block_survives_reload_and_rest_is_refreshed(self) -> None:
        """Blok reguł projektu wraca bajt w bajt, reszta pliku jest z szablonu."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor")
            template = (KIT_ROOT / "templates" / "cursor" / "BUGBOT.md").read_text(
                encoding="utf-8"
            )
            hint = extract_rules(template)
            assert hint is not None
            rules = "\n- Reguła projektu A\n- Reguła projektu B\n"
            for rel in ("BUGBOT.md", ".cursor/BUGBOT.md"):
                path = workspace / rel
                text = path.read_text(encoding="utf-8")
                self.assertIn(hint, text)
                # Zmiana poza blokiem też ma zniknąć przy reloadzie.
                text = text.replace(hint, rules).replace(
                    "- Preferuj minimalny diff", "- moja zmiana kita"
                )
                path.write_text(text, encoding="utf-8", newline="\n")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor")

            for rel in ("BUGBOT.md", ".cursor/BUGBOT.md"):
                text = (workspace / rel).read_text(encoding="utf-8")
                self.assertEqual(extract_rules(text), rules, rel)
                self.assertIn("- Preferuj minimalny diff", text, rel)
                self.assertNotIn("moja zmiana kita", text, rel)

    def test_migration_moves_added_rules_into_block(self) -> None:
        """Stary render + 2 dopisane reguły → bieżący szablon z regułami w bloku."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit_with_history(Path(tmp) / "kit")
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=kit, clients="claude,cursor")

            dest = workspace / "BUGBOT.md"
            for path in (dest, workspace / ".cursor" / "BUGBOT.md"):
                old = path.read_text(encoding="utf-8")
                self.assertNotIn("project:rules", old)
                path.write_text(
                    old + "\n- Reguła projektu A\n- Reguła projektu B\n",
                    encoding="utf-8",
                    newline="\n",
                )

            (kit / "templates" / "cursor" / "BUGBOT.md").write_text(
                (KIT_ROOT / "templates" / "cursor" / "BUGBOT.md").read_text(encoding="utf-8"),
                encoding="utf-8",
                newline="\n",
            )
            self._git(kit, "commit", "-q", "-am", "current template")

            out = run_bootstrap(target=workspace, kit_root=kit, clients="claude,cursor")

            for path in (dest, workspace / ".cursor" / "BUGBOT.md"):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(
                    extract_rules(text), "\n- Reguła projektu A\n- Reguła projektu B\n"
                )
                self.assertIn("## Ogólne", text)
                self.assertNotIn("stara reguła kita", text)
            self.assertIn("Reguła projektu A", out)
            self.assertIn("Reguła projektu B", out)
            # Kopia natywnego BugBota też raportuje przeniesione linie (#240).
            self.assertIn("  ~ BUGBOT.md: reguły", out)
            self.assertIn("  ~ .cursor/BUGBOT.md: reguły", out)


class TestAgentsProjectBlock(_BootstrapTestCase, unittest.TestCase):
    """AGENTS.md: część kita odświeżana przy reloadzie, blok ``project:agents`` zostaje (#269)."""

    OLD_AGENTS = "# AGENTS.md\n\nHooki: `.claude/hooks/gate-push.sh`.\n"

    def _kit_with_old_agents(self, root: Path) -> Path:
        """Kopia kita: commit ze starym ``templates/AGENTS.md``, potem bieżący szablon."""
        kit = self._kit_with_history(root)
        template = kit / "templates" / "AGENTS.md"
        template.write_text(self.OLD_AGENTS, encoding="utf-8", newline="\n")
        self._git(kit, "commit", "-q", "-am", "old agents")
        return kit

    def _restore_current(self, kit: Path) -> None:
        shutil_copy(KIT_ROOT / "templates" / "AGENTS.md", kit / "templates" / "AGENTS.md")
        self._git(kit, "commit", "-q", "-am", "current agents")

    def test_untouched_old_agents_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit_with_old_agents(Path(tmp) / "kit")
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=kit, clients="claude")
            self.assertEqual((workspace / "AGENTS.md").read_text(encoding="utf-8"), self.OLD_AGENTS)
            self._restore_current(kit)

            run_bootstrap(target=workspace, kit_root=kit, clients="claude")

            text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            template = (KIT_ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(is_pristine(text, template, "agents"))
            self.assertNotEqual(extract_brief(text), extract_brief(template))

    def test_own_lines_move_into_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit_with_old_agents(Path(tmp) / "kit")
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=kit, clients="claude")
            agents = workspace / "AGENTS.md"
            agents.write_text(
                self.OLD_AGENTS + "\n- Nasza reguła projektu\n", encoding="utf-8", newline="\n"
            )
            self._restore_current(kit)

            out = run_bootstrap(target=workspace, kit_root=kit, clients="claude")

            text = agents.read_text(encoding="utf-8")
            self.assertEqual(extract_rules(text, "agents"), "\n- Nasza reguła projektu\n")
            self.assertNotIn("gate-push.sh", text)
            self.assertIn("  ~ AGENTS.md: reguły", out)

    def test_block_survives_reload_and_kit_part_is_refreshed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            agents = workspace / "AGENTS.md"
            text = agents.read_text(encoding="utf-8")
            hint = extract_rules(text, "agents")
            assert hint is not None
            rules = "\n- Nasza reguła A\n"
            agents.write_text(
                text.replace(hint, rules).replace("## Code review", "## Code review (stare)"),
                encoding="utf-8",
                newline="\n",
            )

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            text = agents.read_text(encoding="utf-8")
            self.assertEqual(extract_rules(text, "agents"), rules)
            self.assertNotIn("(stare)", text)


def shutil_copy(src: Path, dest: Path) -> None:
    """Skopiuj szablon zachowując metadane."""
    import shutil

    shutil.copy2(src, dest)


class TestAgentsBriefBlock(_BootstrapTestCase, unittest.TestCase):
    """Bootstrap renderuje brief z Profilu i overlayu do bloku ``kit:brief`` (#307)."""

    def test_broken_profile_still_installs_agents_md(self) -> None:
        """Błąd renderowania briefu nie zatrzymuje bootstrapu — AGENTS.md z domyślnym blokiem."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            (workspace / ".ai" / "project.profile.yaml").write_text(
                "name: broken\nlanguage: pl\nclients: claude\nbackend: [oops\n",
                encoding="utf-8",
            )

            run_bootstrap(
                target=workspace, kit_root=KIT_ROOT, clients="claude", language="pl"
            )

            text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            template = (KIT_ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(extract_brief(text), extract_brief(template))

    def test_bootstrap_renders_profile_brief_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            (workspace / ".ai" / "project.profile.yaml").write_text(
                "name: brief-app\nlanguage: pl\nclients: claude\n"
                "backend: fastapi\nweb: none\nmobile: none\ncodegen: none\n",
                encoding="utf-8",
            )
            (workspace / ".ai" / "project.md").write_text(
                "# Overlay\n\nbase: dev\n\n## Komendy\n\n- test: `make test`\n",
                encoding="utf-8",
            )

            run_bootstrap(
                target=workspace, kit_root=KIT_ROOT, clients="claude", language="pl"
            )

            brief = extract_brief((workspace / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIsNotNone(brief)
            assert brief is not None
            self.assertIn("`pl`", brief)
            self.assertIn("`dev`", brief)
            self.assertIn("backend=`fastapi`", brief)
            self.assertIn("`none`", brief)
            self.assertIn("make test", brief)
            self.assertIn("project.md", brief)

    def test_reload_refreshes_brief_after_profile_change(self) -> None:
        """Brief nie jest blokiem projektu — reload podmienia go nowymi wartościami."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(
                "name: brief-app\nlanguage: pl\nclients: claude\n"
                "backend: none\nweb: none\nmobile: none\ncodegen: none\n",
                encoding="utf-8",
            )
            run_bootstrap(
                target=workspace, kit_root=KIT_ROOT, clients="claude", language="pl"
            )
            profile.write_text(
                "name: brief-app\nlanguage: pl\nclients: claude\n"
                "backend: fastapi\nweb: none\nmobile: none\ncodegen: none\n",
                encoding="utf-8",
            )

            run_bootstrap(
                target=workspace, kit_root=KIT_ROOT, clients="claude", language="pl"
            )

            brief = extract_brief((workspace / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIsNotNone(brief)
            assert brief is not None
            self.assertIn("backend=`fastapi`", brief)

    def test_bootstrap_renders_brief_rules_for_language(self) -> None:
        """Bootstrap i reload renderują reguły briefu w AGENTS.md w języku Profilu (#355)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(
                "name: brief-rules-app\nlanguage: en\nclients: claude\n"
                "backend: none\nweb: none\nmobile: none\ncodegen: none\n",
                encoding="utf-8",
            )
            run_bootstrap(
                target=workspace, kit_root=KIT_ROOT, clients="claude", language="en"
            )

            agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            rules = extract_brief_rules(agents_text)
            self.assertIsNotNone(rules)
            assert rules is not None
            self.assertIn("Task classification and MCP rules", rules)
            self.assertIn("in English", rules)
            self.assertNotIn("Zadanie kodowe", rules)
            self.assertNotIn("po polsku", rules)


class TestBugbotTestPolicy(_BootstrapTestCase, unittest.TestCase):
    """Reguła BugBota blokująca nieangielskie nazwy testów w zbootstrapowanym repo (#163)."""

    def test_bugbot_blocks_non_english_test_names(self) -> None:
        """Zbootstrapowany BUGBOT.md ma blokującą regułę na nieangielskie nazwy."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            bugbot = (workspace / "BUGBOT.md").read_text(encoding="utf-8")
            rule = bugbot[bugbot.index("Non-English identifier") - 300:]
            self.assertIn("`test_*`", rule)
            self.assertIn("blocking bug", rule)


if __name__ == "__main__":
    unittest.main()
