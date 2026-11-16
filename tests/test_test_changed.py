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

import test_changed


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
        self.assertEqual(proc.returncode, 0)
        self.assertIn("test_guards", proc.stdout)
        self.assertIn("test_resolver", proc.stdout)

    def test_mapping_for_templates_and_scripts(self) -> None:
        """
        Mapa wybiera oczekiwane moduły dla:
        - templates/shared/guards/server-guard.mjs
        - scripts/bootstrap-project.sh
        - README.md (fallback grep, bez --all)
        - LICENSE (sam rdzeń)
        - pliku bez trafień grep (ostrzeżenie + --all)
        """
        # 1. templates/shared/guards/server-guard.mjs
        mods_guards, is_all_guards, _ = test_changed.resolve_test_targets(
            ["templates/shared/guards/server-guard.mjs"], root=KIT_ROOT
        )
        self.assertFalse(is_all_guards)
        self.assertIn("test_guards", mods_guards)

        # 2. scripts/bootstrap-project.sh
        mods_boot, is_all_boot, _ = test_changed.resolve_test_targets(
            ["scripts/bootstrap-project.sh"], root=KIT_ROOT
        )
        self.assertFalse(is_all_boot)
        self.assertTrue("test_bootstrap" in mods_boot or "test_bootstrap_clients.sh" in mods_boot)

        # 3. README.md -> fallback grep, bez --all
        mods_readme, is_all_readme, _ = test_changed.resolve_test_targets(
            ["README.md"], root=KIT_ROOT
        )
        self.assertFalse(is_all_readme)
        self.assertTrue(len(mods_readme) > len(test_changed.FAST_CORE))

        # 4. LICENSE -> sam rdzeń
        mods_license, is_all_license, _ = test_changed.resolve_test_targets(
            ["LICENSE"], root=KIT_ROOT
        )
        self.assertFalse(is_all_license)
        self.assertEqual(set(mods_license), set(test_changed.FAST_CORE))

        # 5. Plik bez trafień grep -> ostrzeżenie + --all
        # Nazwa dynamiczna zapobiega trafieniu literału w tests/test_test_changed.py
        dummy_name = f"unmatched_file_{int(time.time() * 1000)}.xyz"
        mods_unknown, is_all_unknown, reasons_unknown = test_changed.resolve_test_targets(
            [dummy_name], root=KIT_ROOT
        )
        self.assertTrue(is_all_unknown)
        self.assertTrue(any("pełnej suity" in r for r in reasons_unknown))
        self.assertTrue(len(mods_unknown) > 20)

    def test_map_guardian_all_guides_and_scripts_covered(self) -> None:
        """
        Strażnik mapy: każdy plik z src/guides/*.py oraz scripts/*
        trafia do jakiegoś modułu testów (konwencja, wyjątek lub fallback grep).
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

    def test_deleted_test_file_is_skipped(self) -> None:
        """Usunięty plik testowy nie jest dodawany do listy wykonania i nie wyzwala --all."""
        mods, reason = test_changed.resolve_modules_for_file("tests/test_deleted_nonexistent.py", root=KIT_ROOT)
        self.assertEqual(mods, [])
        self.assertIn("pominięto", reason)

        selected, is_all, reasons = test_changed.resolve_test_targets(["tests/test_deleted_nonexistent.py"], root=KIT_ROOT)
        self.assertFalse(is_all)
        self.assertEqual(selected, list(test_changed.FAST_CORE))

        # Brakujący plik nietestowy w tests/ nie jest traktowany jako usunięty plik testu
        mods_helper, reason_helper = test_changed.resolve_modules_for_file("tests/_nonexistent_fixture.py", root=KIT_ROOT)
        self.assertNotIn("usunięty plik testu", reason_helper)

    def test_normalize_repo_path(self) -> None:
        """Normalizacja ścieżek CLI z podkatalogów, z kropkami i ukośnikami."""
        self.assertEqual(test_changed.normalize_repo_path("./scripts/test_changed.py", root=KIT_ROOT), "scripts/test_changed.py")
        self.assertEqual(test_changed.normalize_repo_path("scripts/../tests/test_resolver.py", root=KIT_ROOT), "tests/test_resolver.py")
        self.assertEqual(test_changed.normalize_repo_path("tests/test_resolver.py", root=KIT_ROOT), "tests/test_resolver.py")

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
            returncode, last_line, stalled = test_changed.run_with_watchdog(
                cmd, log_path=log_path, stall_seconds=2.0, cwd=KIT_ROOT
            )
            elapsed = time.time() - start_time

            self.assertTrue(stalled)
            self.assertNotEqual(returncode, 0)
            self.assertLess(elapsed, 10.0, "Watchdog powinien ubić proces szybko po stallu")
            self.assertIn("test_frozen_start", last_line)

    def test_pythonpath_includes_tests_directory_in_execution(self) -> None:
        """Podprocesy testowe widzą moduł _shell dzięki PYTHONPATH w run_with_watchdog."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "shell_check.log"
            cmd = [sys.executable, "-c", "import _shell; print('OK_SHELL')"]
            returncode, last_line, stalled = test_changed.run_with_watchdog(
                cmd, log_path=log_path, stall_seconds=10.0, cwd=KIT_ROOT
            )
            self.assertFalse(stalled)
            self.assertEqual(returncode, 0)
            self.assertIn("OK_SHELL", last_line)

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

    def test_cli_invalid_arguments_validation(self) -> None:
        """Walidacja argumentów CLI odrzuca -j 0 i --stall-min <= 0."""
        for invalid_args in (["-j", "0"], ["--stall-min", "-1"], ["--stall-min", "0"]):
            proc = subprocess.run(
                [sys.executable, str(KIT_ROOT / "scripts" / "test_changed.py"), "--dry-run", *invalid_args],
                cwd=str(KIT_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
