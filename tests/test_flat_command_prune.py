"""Płaskie komendy kita znikają przy reloadzie po nazwie (#533).

Kit pisze komendy tylko w formie natywnej klienta: plugin ``kit-ai`` dla Claude
(``.claude/skills/kit-ai/``) i ``.opencode/commands/kit-ai/`` dla OpenCode. Stare płaskie
``.claude/commands/<nazwa>.md`` i ``.opencode/command/<nazwa>.md`` reload kasuje po nazwach
kita — także wtedy, gdy klient jest odznaczony w Profilu. Plik obcy o innej nazwie zostaje.
"""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from test_bootstrap import _BootstrapTestCase

from guides import cli

# Nazwa z agentów kita (`git-start`) i nazwa z listy dawnych komend (`review-backend`).
KIT_FLAT_CLAUDE = (".claude/commands/git-start.md", ".claude/commands/review-backend.md")
KIT_FLAT_OPENCODE = (
    ".opencode/command/git-start.md",
    ".opencode/command/teacher-backend.md",
    # `/goal` i `/loop` od #567 są w `.opencode/commands/kit-ai/` — płaskie znikają jak reszta.
    ".opencode/command/goal.md",
    ".opencode/command/loop.md",
)
FOREIGN_FLAT = (".claude/commands/moja.md", ".opencode/command/moja.md")
# Forma natywna `/kit-ai/goal`, `/kit-ai/loop` (#567) — plugin kit-loop.js czyta te nazwy.
OPENCODE_KEPT = (".opencode/commands/kit-ai/goal.md", ".opencode/commands/kit-ai/loop.md")


def _quiet_main(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class TestFlatCommandPrune(_BootstrapTestCase):
    """Reload kasuje płaskie pliki kita po nazwie i zostawia pliki obce."""

    def _seed_flat(self, app: Path) -> None:
        for rel in (*KIT_FLAT_CLAUDE, *KIT_FLAT_OPENCODE, *FOREIGN_FLAT):
            (app / rel).parent.mkdir(parents=True, exist_ok=True)
            (app / rel).write_text(f"{rel}\n", encoding="utf-8")

    def _select_clients(self, app: Path, clients: str) -> None:
        profile = app / ".ai" / "project.profile.yaml"
        text = profile.read_text(encoding="utf-8")
        text, count = re.subn(r"^clients: .*$", f"clients: {clients}", text, flags=re.MULTILINE)
        # Bez tej asercji zmiana formatu profilu cicho wyłączyłaby scenariusz odznaczenia.
        self.assertEqual(count, 1, "w profilu nie ma jednej linii `clients:`")
        profile.write_text(text, encoding="utf-8")

    def test_renamed_skill_flat_file_is_removed_for_opencode(self) -> None:
        """Skill kita sprzed zmiany nazwy (`retro` → `kit-retro`) znika z płaskiego katalogu opencode."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "opencode")[0], 0)
            old = app / ".opencode/command/retro.md"
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_text(
                "Klasyfikacja znalezisk z wyniku skanu sesji agentów (`kit-ai retro scan`) — stary skill\n",
                encoding="utf-8",
            )

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertFalse(old.exists())

    def test_foreign_flat_file_with_renamed_skill_name_stays(self) -> None:
        """Cudzy `retro.md` (bez markera kita) zostaje — kasowanie po nazwie nie dotyczy skilli zmienionych nazw."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "opencode")[0], 0)
            foreign = app / ".opencode/command/retro.md"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_text("retro z mattpocock-skills\n", encoding="utf-8")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "retro z mattpocock-skills\n")

    def test_selected_clients_reload_removes_flat_kit_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude,opencode")[0], 0)
            self._seed_flat(app)

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            for rel in (*KIT_FLAT_CLAUDE, *KIT_FLAT_OPENCODE):
                self.assertFalse((app / rel).exists(), rel)
            for rel in (*FOREIGN_FLAT, *OPENCODE_KEPT):
                self.assertTrue((app / rel).is_file(), rel)

    def test_unselected_opencode_reload_removes_flat_kit_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude,opencode")[0], 0)
            self._seed_flat(app)
            self._select_clients(app, "claude")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            for rel in KIT_FLAT_OPENCODE:
                self.assertFalse((app / rel).exists(), rel)
            self.assertTrue((app / ".opencode/command/moja.md").is_file())

    def test_reload_keeps_files_behind_command_dir_symlink_outside_workspace(self) -> None:
        """`.opencode/command` jako dowiązanie poza workspace — pliki w celu zostają (#566)."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude,opencode")[0], 0)
            self._seed_flat(app)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            kit_names = ("git-start.md", "teacher-backend.md")
            for name in kit_names:
                (outside / name).write_text("cudzy\n", encoding="utf-8")
            (outside / "retro.md").write_text(
                "Klasyfikacja znalezisk z wyniku skanu sesji agentów (`kit-ai retro scan`)\n",
                encoding="utf-8",
            )
            command_dir = app / ".opencode/command"
            for p in command_dir.iterdir():
                p.unlink()
            command_dir.rmdir()
            command_dir.symlink_to(outside, target_is_directory=True)

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            for name in (*kit_names, "retro.md"):
                self.assertTrue((outside / name).is_file(), name)
            # Pliki w workspace dalej znikają.
            for rel in KIT_FLAT_CLAUDE:
                self.assertFalse((app / rel).exists(), rel)

    def test_unselected_claude_reload_removes_flat_kit_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "claude,opencode")[0], 0)
            self._seed_flat(app)
            self._select_clients(app, "opencode")

            code, out = _quiet_main("reload", str(app))

            self.assertEqual(code, 0, out)
            for rel in KIT_FLAT_CLAUDE:
                self.assertFalse((app / rel).exists(), rel)
            self.assertTrue((app / ".claude/commands/moja.md").is_file())


if __name__ == "__main__":
    unittest.main()
