"""
Polityka bramki zapisu plików: decyduje LOKALIZACJA, nigdy rozmiar zmiany.

Bramka miała kiedyś próg na liczbę usuniętych linii netto. Pomiar na realnych
edycjach pokazał, że próg albo nie odpalał się nigdy, albo pytał przy zwykłej
pracy w repo — a w repo od cofania jest git. Te testy pilnują, żeby próg nie
wrócił tylnymi drzwiami: duże usunięcie wewnątrz projektu ma przechodzić bez
promptu, a zapis poza projektem ma pytać zawsze.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "templates" / "shared" / "guards" / "gate-file-writes.mjs"

NODE = shutil.which("node")


def is_ci() -> bool:
    """
    Czy działamy na CI (GitHub Actions ustawia ``CI=true``)?

    Returns:
        bool: ``True`` gdy ``CI`` ustawione na coś innego niż ``0`` / ``false``.
    """
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


def decide(payload: dict[str, object]) -> str:
    """
    Uruchom hooka na payloadzie i zwróć jego ``permissionDecision``.

    Args:
        payload: Payload PreToolUse, tak jak podaje go Claude Code.

    Returns:
        str: ``allow`` albo ``ask``.
    """
    proc = subprocess.run(
        [str(NODE), str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(ROOT),
        timeout=45,
        check=False,
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    return str(json.loads(out)["hookSpecificOutput"]["permissionDecision"])


def raw_decide(payload: bytes) -> str:
    """
    To samo, ale dla surowych bajtów — do przypadku nieczytelnego payloadu.

    Args:
        payload: Dowolne bajty na stdin hooka.

    Returns:
        str: ``allow`` albo ``ask``.
    """
    proc = subprocess.run(
        [str(NODE), str(HOOK)],
        input=payload,
        capture_output=True,
        cwd=str(ROOT),
        timeout=45,
        check=False,
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    return str(json.loads(out)["hookSpecificOutput"]["permissionDecision"])


@unittest.skipUnless(NODE or is_ci(), "brak node — hook nie ma czym wystartować")
class TestGateFileWrites(unittest.TestCase):
    """Bramka rozstrzyga o lokalizacji zapisu, nie o jego rozmiarze."""

    def _in_project(self, name: str) -> str:
        return str(ROOT / name).replace("\\", "/")

    def test_huge_deletion_inside_project_is_allowed(self) -> None:
        """Regresja: próg na usunięte linie nie może wrócić."""
        target = self._in_project("README.md")
        self.assertEqual(
            decide(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": target,
                        "old_string": "\n".join(f"linia {i}" for i in range(500)),
                        "new_string": "",
                    },
                    "cwd": str(ROOT),
                }
            ),
            "allow",
        )

    def test_write_inside_project_is_allowed(self) -> None:
        """Nadpisanie istniejącego pliku w repo — git to cofnie, bez promptu."""
        self.assertEqual(
            decide(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": self._in_project("README.md"), "content": "x"},
                    "cwd": str(ROOT),
                }
            ),
            "allow",
        )

    def test_write_outside_project_asks(self) -> None:
        """Poza repo git nie odzyska niczego — zawsze pytaj."""
        outside = str(Path.home() / ".bashrc").replace("\\", "/")
        self.assertEqual(
            decide(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": outside, "content": "x"},
                    "cwd": str(ROOT),
                }
            ),
            "ask",
        )

    def test_missing_path_is_allowed(self) -> None:
        """Payload bez ścieżki nie jest zapisem — nie ma czego bramkować."""
        self.assertEqual(
            decide({"tool_name": "Write", "tool_input": {}, "cwd": str(ROOT)}),
            "allow",
        )

    def test_unreadable_payload_asks(self) -> None:
        """Fail-closed: nieczytelny payload nie może po cichu poszerzyć dostępu."""
        self.assertEqual(raw_decide(b"not-json"), "ask")


if __name__ == "__main__":
    unittest.main()
