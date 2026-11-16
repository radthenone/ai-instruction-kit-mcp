"""
Testy kontraktu dla szybkiego lokalnego runnera testów (scripts/test_changed.py).
Issue #419.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

try:
    import test_changed
except ImportError:
    test_changed = None


class TestTestChangedContract(unittest.TestCase):
    """Testy kontraktu i kryteriów ukończenia dla scripts/test_changed.py."""

    def setUp(self) -> None:
        if test_changed is None:
            self.fail("Moduł scripts/test_changed.py nie istnieje")

    def test_fast_core_defined(self) -> None:
        """Szybki rdzeń zawsze zawiera test_resolver, test_manifest_mappings, test_mcp_compat."""
        core = set(test_changed.FAST_CORE)
        self.assertIn("test_resolver", core)
        self.assertIn("test_manifest_mappings", core)
        self.assertIn("test_mcp_compat", core)

    def test_dry_run_for_server_guard(self) -> None:
        """
        --dry-run dla src/guides/server_guard.py -> test_guards + szybki rdzeń.
        """
        selected, is_all, reasons = test_changed.resolve_test_targets(
            ["src/guides/server_guard.py"], root=KIT_ROOT
        )
        self.assertFalse(is_all)
        self.assertIn("test_guards", selected)
        for core_mod in test_changed.FAST_CORE:
            self.assertIn(core_mod, selected)
        self.assertTrue(any("server_guard" in r for r in reasons))

        # Sprawdzenie wywołania CLI --dry-run
        proc = subprocess.run(
            [sys.executable, str(KIT_ROOT / "scripts" / "test_changed.py"), "--dry-run", "src/guides/server_guard.py"],
            cwd=str(KIT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"stdout: {proc.stdout}, stderr: {proc.stderr}")
        self.assertIn("test_guards", proc.stdout)
        self.assertIn("test_resolver", proc.stdout)

    def test_mapping_for_expected_modules(self) -> None:
        """
        Mapa wybiera oczekiwane moduły dla:
        - templates/shared/guards/*
        - scripts/bootstrap-project.sh
        - README.md (fallback grep, bez --all)
        - LICENSE (sam rdzeń)
        - pliku bez trafień grep (ostrzeżenie + --all)
        """
        # 1. templates/shared/guards/git-guard.mjs
        selected, is_all, _ = test_changed.resolve_test_targets(
            ["templates/shared/guards/git-guard.mjs"], root=KIT_ROOT
        )
        self.assertFalse(is_all)
        self.assertTrue(any("guard" in m for m in selected))

        # 2. scripts/bootstrap-project.sh
        selected, is_all, _ = test_changed.resolve_test_targets(
            ["scripts/bootstrap-project.sh"], root=KIT_ROOT
        )
        self.assertFalse(is_all)
        self.assertTrue(any("bootstrap" in m for m in selected))

        # 3. README.md (fallback grep, bez --all)
        selected, is_all, _ = test_changed.resolve_test_targets(
            ["README.md"], root=KIT_ROOT
        )
        self.assertFalse(is_all)
        self.assertGreater(len(selected), len(test_changed.FAST_CORE))
        # Upewnij się, że nie wybrano wszystkich testów z tests/
        all_test_files = [p.stem for p in (KIT_ROOT / "tests").glob("test_*.py") if p.name != "_shell.py"]
        self.assertLess(len(selected), len(all_test_files))

        # 4. LICENSE (sam szybki rdzeń)
        selected, is_all, _ = test_changed.resolve_test_targets(
            ["LICENSE"], root=KIT_ROOT
        )
        self.assertFalse(is_all)
        self.assertEqual(set(selected), set(test_changed.FAST_CORE))

        # 5. Plik bez trafień grep (ostrzeżenie + --all)
        unknown_dummy = "un" + "known_nonexistent_xyz987.foo"
        selected, is_all, reasons = test_changed.resolve_test_targets(
            [unknown_dummy], root=KIT_ROOT
        )
        self.assertTrue(is_all)
        self.assertTrue(any("ostrzeżenie" in r.lower() or "warning" in r.lower() or "brak" in r.lower() or "all" in r.lower() for r in reasons))

    def test_map_guardian_covers_all_guides_and_scripts(self) -> None:
        """
        Strażnik mapy (decyzja 4): każdy src/guides/*.py i scripts/* trafia do
        jakiegoś modułu testów (konwencja, wyjątek albo fallback grep).
        """
        uncovered: list[str] = []
        guides = sorted((KIT_ROOT / "src" / "guides").glob("*.py"))
        scripts = sorted(p for p in (KIT_ROOT / "scripts").iterdir() if p.is_file())

        for target in guides + scripts:
            rel_path = str(target.relative_to(KIT_ROOT)).replace("\\", "/")
            modules, _ = test_changed.resolve_modules_for_file(rel_path, root=KIT_ROOT)
            if not modules:
                uncovered.append(rel_path)

        self.assertEqual(
            uncovered,
            [],
            msg=f"Pliki bez pokrycia w testach (strażnik mapy): {uncovered}",
        )

    def test_watchdog_kills_on_frozen_log(self) -> None:
        """
        Watchdog na sztucznie zamrożonym logu zwraca kod != 0 i ubija proces.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "test.log"
            # Skrypt który wypisuje linię a potem śpi w nieskończoność
            sleep_code = "import sys, time; sys.stdout.write('test_frozen_start\\n'); sys.stdout.flush(); time.sleep(60)"
            cmd = [sys.executable, "-c", sleep_code]

            start_time = time.time()
            returncode, last_line = test_changed.run_with_watchdog(
                cmd, log_path=log_path, stall_seconds=0.2, cwd=KIT_ROOT
            )
            elapsed = time.time() - start_time

            self.assertNotEqual(returncode, 0)
            self.assertLess(elapsed, 10.0, "Watchdog powinien ubić proces szybko po stallu")
            self.assertIn("test_frozen_start", last_line)

    def test_cli_all_flag(self) -> None:
        """Flaga --all wybiera wszystkie moduły z tests/."""
        proc = subprocess.run(
            [sys.executable, str(KIT_ROOT / "scripts" / "test_changed.py"), "--dry-run", "--all"],
            cwd=str(KIT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("wymuszono flagę --all", proc.stdout)
        self.assertIn("test_guards", proc.stdout)
        self.assertIn("test_resolver", proc.stdout)

    def test_cli_clean_tree_runs_fast_core(self) -> None:
        """Brak zmienionych plików wybiera sam szybki rdzeń."""
        selected, is_all, reasons = test_changed.resolve_test_targets([], root=KIT_ROOT)
        self.assertFalse(is_all)
        self.assertEqual(set(selected), set(test_changed.FAST_CORE))


if __name__ == "__main__":
    unittest.main()
