"""`kit-ai` z koła, bez klona kita (#121).

Buduje koło (`uv build`), instaluje je do czystego venv i robi `kit-ai install` w pustym
repo. Metadane instalacji z gita (`direct_url.json` z `commit_id`) podmieniamy po
instalacji — tak wygląda koło po `uv tool install git+…@ref`, a test zostaje offline
względem samego kita. Bez `uv` / basha: skip lokalnie, błąd na CI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, resolve_bash

KIT_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _run(*argv: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        list(argv),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=600,
    )
    if result.returncode != 0:
        raise AssertionError(f"{argv} → {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout


class TestWheelInstall(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("uv") or not resolve_bash():
            if is_ci():
                self.fail("brak uv albo bash w CI")
            self.skipTest("brak uv albo bash")

    def test_kit_ai_from_wheel_installs_without_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dist = tmp_path / "dist"
            _run("uv", "build", "--wheel", "-q", "-o", str(dist), cwd=KIT_ROOT)
            wheel = next(dist.glob("*.whl"))
            venv = tmp_path / "venv"
            _run("uv", "venv", "-q", "--python", sys.executable, str(venv))
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            _run("uv", "pip", "install", "-q", "--python", str(python), str(wheel))

            site = Path(
                _run(str(python), "-c", "import guides, pathlib; print(pathlib.Path(guides.__file__).parent.parent)").strip()
            )
            dist_info = next(site.glob("guides_mcp-*.dist-info"))
            (dist_info / "direct_url.json").write_text(
                json.dumps(
                    {
                        "url": "https://github.com/radthenone/ai-instruction-kit-mcp.git",
                        "vcs_info": {"vcs": "git", "commit_id": COMMIT, "requested_revision": "dev-2"},
                    }
                ),
                encoding="utf-8",
            )

            app = tmp_path / "app"
            app.mkdir()
            kit_ai = venv / ("Scripts/kit-ai.exe" if os.name == "nt" else "bin/kit-ai")
            env = {k: v for k, v in os.environ.items() if k not in {"GUIDES_KIT_ROOT", "VIRTUAL_ENV"}}
            _run(str(kit_ai), "install", "--clients", "claude,opencode", "--language", "pl", cwd=app, env=env)

            self.assertTrue((app / ".claude" / "agents" / "git-start.md").is_file())
            self.assertTrue((app / ".claude" / "hooks" / "git-guard.mjs").is_file())
            self.assertTrue((app / ".opencode" / "command" / "git-start.md").is_file())
            mcp = (app / ".mcp.json").read_text(encoding="utf-8")
            self.assertIn('"uvx"', mcp)
            self.assertIn("git+https://github.com/radthenone/ai-instruction-kit-mcp.git@dev-2", mcp)
            stamp = json.loads((app / ".ai" / ".kit-bootstrap.json").read_text(encoding="utf-8"))
            self.assertEqual(stamp["kit_commit"], COMMIT)

            status = _run(str(kit_ai), "status", cwd=app, env=env)
            self.assertIn("aktualny", status)


if __name__ == "__main__":
    unittest.main()
