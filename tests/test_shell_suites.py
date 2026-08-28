"""
Adapter: wciąga zewnętrzne suity (bash / standalone python) do `unittest discover`.

`tests/*.sh` oraz `tests/test_bash_hook_launcher.py` nie definiują klas `TestCase`,
więc `unittest discover` je pomijał — CI nigdy ich nie uruchamiał, mimo że README
opisuje je jako suitę regresji. Ten moduł jest jedynym miejscem, przez które
zewnętrzna suita wchodzi do zwykłego przebiegu testów.

Dwa strażniki pilnują, żeby luka nie wróciła: `test_every_shell_suite_is_declared`
(nowy `*.sh`) i `test_every_standalone_py_suite_is_declared` (nowy `test_*.py` bez
klasy `TestCase`). Trzeci warunek — że suita naprawdę się wykonała, a nie po cichu
pominęła — pilnuje `is_ci()` po stronie samych suit.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

# Jedno źródło prawdy dla wykrywania Git Bash, CI i formy ścieżki dla basha.
from test_bash_hook_launcher import is_ci, posix_path, resolve_bash

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"

# Bootstrap odpala kilka pełnych instalacji (uvx-free, ale wiele procesów Pythona).
#
# 300 s to ~2,5× zapas nad najwolniejszą zmierzoną suitą (bootstrap: 121 s na
# Windows, reszta poniżej 60 s). Poprzednie 600 s znaczyło, że przy zamulonej
# maszynie suita mieliła dziesięć minut, zanim powiedziała cokolwiek — a i tak
# kończyła się błędem. Limit ma zamieniać zamulenie w szybki komunikat, nie
# przykrywać je czekaniem.
SUITE_TIMEOUT_SECONDS = 300

BASH_SUITES: tuple[str, ...] = (
    "test_gate_destructive.sh",
    "test_guard_adapter.sh",
    "test_bootstrap_clients.sh",
)

# Skrypty `python` z własnym `main()` zamiast `TestCase` — uruchamiane jako podproces,
# żeby nie zależeć od tego, czy ich moduł da się bezpiecznie zaimportować.
STANDALONE_PY_SUITES: tuple[str, ...] = ("test_bash_hook_launcher.py",)

# Ten moduł sam jest oparty na TestCase, więc nie może być swoją własną suitą.
_SELF = Path(__file__).name


def _defines_test_case(path: Path) -> bool:
    """
    Czy plik definiuje klasę dziedziczącą po ``unittest.TestCase``?

    Parsowanie AST zamiast importu — plik może mieć skutki uboczne na poziomie modułu.

    Args:
        path: Ścieżka do pliku ``.py``.

    Returns:
        bool: ``True`` gdy `unittest discover` sam zbierze z niego testy.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
            if name == "TestCase":
                return True
    return False


class TestExternalSuites(unittest.TestCase):
    """Zewnętrzne suity uruchamiane jako podprocesy w ramach `unittest discover`."""

    def _run_suite(self, argv: list[str], name: str) -> None:
        """
        Uruchom suitę i oblej test, gdy jej kod wyjścia != 0.

        Args:
            argv: Komenda do uruchomienia.
            name: Nazwa pliku suity (do komunikatu błędu).
        """
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUITE_TIMEOUT_SECONDS,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                f"{name} zakończył się kodem {proc.returncode}\n"
                f"--- stdout ---\n{proc.stdout}\n"
                f"--- stderr ---\n{proc.stderr}"
            )

    def test_bash_suites_pass(self) -> None:
        """
        Każdy `tests/*.sh` przechodzi.

        Lokalnie skip, gdy brak basha (goły Windows). Na CI brak basha to błąd —
        cichy skip odtworzyłby dokładnie tę lukę, którą ten moduł zamyka.
        """
        bash = resolve_bash()
        if not bash:
            if is_ci():
                self.fail("brak bash w środowisku CI — suity powłoki muszą się wykonać")
            self.skipTest("brak bash / Git for Windows w PATH")
        for name in BASH_SUITES:
            script = TESTS_DIR / name
            with self.subTest(suite=name):
                self.assertTrue(script.is_file(), f"brak {script}")
                self._run_suite(
                    [bash, "--noprofile", "--norc", posix_path(script)],
                    name,
                )

    def test_standalone_py_suites_pass(self) -> None:
        """
        Standalone skrypty python w `tests/` kończą się kodem 0.

        Same pilnują, czy wolno im coś pominąć — `is_ci()` w ich `main()` zamienia
        skip w błąd na CI, więc exit 0 tutaj naprawdę znaczy „wykonało się".
        """
        for name in STANDALONE_PY_SUITES:
            script = TESTS_DIR / name
            with self.subTest(suite=name):
                self.assertTrue(script.is_file(), f"brak {script}")
                self._run_suite([sys.executable, str(script)], name)

    def test_every_shell_suite_is_declared(self) -> None:
        """Nowy `tests/*.sh` musi trafić do `BASH_SUITES` — inaczej CI go nie odpali."""
        on_disk = {path.name for path in TESTS_DIR.glob("*.sh")}
        undeclared = sorted(on_disk - set(BASH_SUITES))
        self.assertEqual(
            undeclared,
            [],
            msg=(
                "Skrypty powłoki poza CI — dopisz je do BASH_SUITES w "
                f"tests/test_shell_suites.py: {undeclared}"
            ),
        )

    def test_every_standalone_py_suite_is_declared(self) -> None:
        """
        `tests/test_*.py` bez klasy `TestCase` musi trafić do `STANDALONE_PY_SUITES`.

        Dokładnie ta forma (`main()` zamiast `TestCase`) była trzecią suitą, której
        `unittest discover` nie zbierał — bez tego strażnika luka wraca przy kolejnym
        takim pliku.
        """
        undeclared = sorted(
            path.name
            for path in TESTS_DIR.glob("test_*.py")
            if path.name != _SELF
            and path.name not in STANDALONE_PY_SUITES
            and not _defines_test_case(path)
        )
        self.assertEqual(
            undeclared,
            [],
            msg=(
                "Skrypty python bez TestCase nie są zbierane przez unittest discover — "
                "dopisz je do STANDALONE_PY_SUITES w tests/test_shell_suites.py: "
                f"{undeclared}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
