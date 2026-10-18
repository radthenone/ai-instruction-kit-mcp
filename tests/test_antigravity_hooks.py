"""`scripts/antigravity_hooks.py` wprost: scalanie / prune klucza `kit-guards` (#201)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = KIT_ROOT / "scripts" / "antigravity_hooks.py"
TEMPLATE = KIT_ROOT / "templates" / "antigravity" / "hooks.json"
USER = {"mine": {"Stop": [{"type": "command", "command": "true"}]}}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


class AntigravityHooksScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="agy-hooks-"))
        self.target = self.dir / "hooks.json"

    def install(self) -> subprocess.CompletedProcess:
        proc = _run("install", str(self.target), str(TEMPLATE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def backups(self) -> list[Path]:
        return sorted(self.dir.glob("hooks.json.bak*"))

    def test_broken_json_goes_to_bak(self) -> None:
        self.target.write_text("{ nie json", encoding="utf-8")
        self.install()
        self.assertEqual([b.read_text(encoding="utf-8") for b in self.backups()], ["{ nie json"])
        self.assertIn("kit-guards", json.loads(self.target.read_text(encoding="utf-8")))

    def test_non_object_top_level_goes_to_bak(self) -> None:
        self.target.write_text("[1, 2]", encoding="utf-8")
        self.install()
        self.assertEqual(len(self.backups()), 1)
        self.assertIn("kit-guards", json.loads(self.target.read_text(encoding="utf-8")))

    def test_bom_file_is_merged_not_backed_up(self) -> None:
        self.target.write_bytes(b"\xef\xbb\xbf" + json.dumps(USER).encode())
        self.install()
        self.assertEqual(self.backups(), [])
        data = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertIn("mine", data)
        self.assertIn("kit-guards", data)

    def test_prune_handles_bom(self) -> None:
        self.target.write_bytes(b"\xef\xbb\xbf" + json.dumps({**USER, "kit-guards": {}}).encode())
        self.assertEqual(_run("prune", str(self.target)).returncode, 0)
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), USER)

    def test_prune_leaves_broken_file_untouched(self) -> None:
        self.target.write_text("{ nie json", encoding="utf-8")
        self.assertEqual(_run("prune", str(self.target)).returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "{ nie json")
        self.assertEqual(self.backups(), [])

    def test_install_is_idempotent(self) -> None:
        self.target.write_text(json.dumps(USER), encoding="utf-8")
        self.install()
        first = self.target.read_text(encoding="utf-8")
        self.install()
        self.assertEqual(self.target.read_text(encoding="utf-8"), first)
        self.assertEqual(self.backups(), [])

    def test_second_bak_keeps_first(self) -> None:
        self.target.write_text("pierwszy", encoding="utf-8")
        self.install()
        self.target.write_text("drugi", encoding="utf-8")
        self.install()
        contents = sorted(b.read_text(encoding="utf-8") for b in self.backups())
        self.assertEqual(contents, ["drugi", "pierwszy"])


if __name__ == "__main__":
    unittest.main()
