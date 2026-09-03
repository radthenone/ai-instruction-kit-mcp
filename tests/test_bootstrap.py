"""Testy bootstrap_workspace — instalacja plików kita z poziomu serwera MCP.

Suita odpala **prawdziwy** ``scripts/bootstrap-project.sh`` (na kopii w katalogu
tymczasowym), bo cała wartość tego narzędzia polega na tym, że skrypt zostaje
jedynym źródłem prawdy o rozkładzie plików. Bez basha: skip lokalnie, błąd na CI —
ta sama polityka co w `test_shell_suites`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_bash_hook_launcher import is_ci, resolve_bash

from guides import server
from guides.bootstrap import BootstrapError, find_bash, plan_bootstrap, run_bootstrap

KIT_ROOT = Path(__file__).resolve().parents[1]


def _snapshot(root: Path) -> dict[str, bytes]:
    """Zawartość wszystkich plików pod ``root`` — do porównania „nic nie ruszono”."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class _BootstrapTestCase(unittest.TestCase):
    """Wspólny strażnik dostępności basha."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI — bootstrap musi się wykonać")
            self.skipTest("brak bash / Git for Windows w PATH")


class TestFindBash(_BootstrapTestCase):
    def test_find_bash_points_at_existing_interpreter(self) -> None:
        """Na Windows to ma być konkretny bash.exe, nie samo słowo `bash`."""
        bash = find_bash()
        self.assertTrue(bash)
        if bash != "bash":
            self.assertTrue(Path(bash).is_file())


class TestDryRun(_BootstrapTestCase):
    def test_dry_run_does_not_touch_workspace(self) -> None:
        """Plan powstaje z przebiegu w sandboxie — repo aplikacji zostaje nietknięte."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "README.md").write_text("app\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)

            self.assertIn(".claude/hooks/gate-destructive.sh", plan.created)
            self.assertIn(".claude/settings.json", plan.created)
            self.assertIn(".ai/.kit-bootstrap.json", plan.created)
            self.assertEqual(plan.modified, [])
            self.assertEqual(plan.deleted, [])

    def test_dry_run_reports_deletions_from_client_pruning(self) -> None:
        """Sprzątanie klientów spoza --clients też widać w planie, zanim skasuje."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".cursor" / "hooks").mkdir(parents=True)
            (workspace / ".cursor" / "mcp.json").write_text("{}\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)
            self.assertIn(".cursor/mcp.json", plan.deleted)


class TestRealRun(_BootstrapTestCase):
    def test_run_installs_hooks_settings_and_stamp(self) -> None:
        """Kryterium ukończenia z issue #31 — hooki, PreToolUse i stamp na dysku."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertTrue((workspace / ".claude" / "hooks" / "gate-destructive.sh").is_file())
            self.assertTrue((workspace / ".ai" / ".kit-bootstrap.json").is_file())
            settings = (workspace / ".claude" / "settings.json").read_text(encoding="utf-8")
            self.assertIn("PreToolUse", settings)

    def test_missing_script_is_an_error(self) -> None:
        """Kit bez skryptu bootstrapu — jasny błąd zamiast cichego nic."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_kit = Path(tmp) / "kit"
            fake_kit.mkdir()
            with self.assertRaises(BootstrapError) as ctx:
                run_bootstrap(target=Path(tmp) / "app", kit_root=fake_kit)
            self.assertIn("bootstrap-project.sh", str(ctx.exception))


class TestServerTool(_BootstrapTestCase):
    """Narzędzie MCP — domyślki, bramka dry-run i odmowy."""

    def setUp(self) -> None:
        super().setUp()
        self._saved = (
            server._profile_path,
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._preset,
        )
        server._profile_path = KIT_ROOT / "profiles" / "_base.yaml"
        server._kit_root = KIT_ROOT
        server._clients = ["claude"]
        server._preset = "_base"
        self._tmp = tempfile.mkdtemp(prefix="guides-tool-test-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.workspace = Path(self._tmp) / "app"
        self.workspace.mkdir()
        server._workspace_root = self.workspace

    def tearDown(self) -> None:
        (
            server._profile_path,
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._preset,
        ) = self._saved

    def test_default_call_is_dry_run(self) -> None:
        """Bez argumentów narzędzie planuje, nie instaluje."""
        before = _snapshot(self.workspace)
        out = server.bootstrap_workspace()
        self.assertIn("dry run", out)
        self.assertIn(".ai/.kit-bootstrap.json", out)
        self.assertEqual(_snapshot(self.workspace), before)

    def test_explicit_dry_run_false_installs(self) -> None:
        """Zapis wymaga jawnego dry_run=False."""
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("zainstalowano", out)
        self.assertTrue((self.workspace / ".ai" / ".kit-bootstrap.json").is_file())
        self.assertTrue((self.workspace / ".claude" / "hooks" / "gate-destructive.sh").is_file())

    def test_report_has_no_empty_sections(self) -> None:
        """Każdy nagłówek `##` w raporcie musi mieć pod sobą wyliczenie."""
        server.bootstrap_workspace(dry_run=False)
        out = server.bootstrap_workspace()

        self.assertIn("Bez zmian:", out)
        self.assertNotIn("## Bez zmian", out)
        lines = out.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("## "):
                continue
            body = [rest for rest in lines[index + 1 :] if rest.strip()]
            self.assertTrue(body and body[0].startswith("- `"), msg=f"pusta sekcja: {line}")

    def test_missing_workspace_errors_instead_of_writing_cwd(self) -> None:
        """Brak --workspace: błąd, a bieżący katalog procesu zostaje nietknięty."""
        server._workspace_root = None
        cwd_sentinel = Path(self._tmp) / "cwd"
        cwd_sentinel.mkdir()
        previous = Path.cwd()
        os.chdir(cwd_sentinel)
        self.addCleanup(os.chdir, previous)

        out = server.bootstrap_workspace(dry_run=False)

        self.assertIn("błąd", out)
        self.assertIn("--workspace", out)
        self.assertEqual(_snapshot(cwd_sentinel), {})

    def test_workspace_equal_to_kit_is_refused(self) -> None:
        """Bootstrap repo kita samym sobą to pomyłka, nie funkcja."""
        server._workspace_root = KIT_ROOT
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("błąd", out)
        self.assertIn("ten sam katalog", out)

    def test_invalid_clients_is_reported_not_raised(self) -> None:
        """Zła wartość --clients wraca jako komunikat narzędzia."""
        out = server.bootstrap_workspace(clients="nieistniejacy-klient")
        self.assertIn("błąd", out)


if __name__ == "__main__":
    unittest.main()
