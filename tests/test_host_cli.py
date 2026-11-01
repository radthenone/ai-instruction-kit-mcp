"""``kit-ai host`` — deterministyczne źródło profilu hosta (#314).

CLI ma zwracać dokładnie to, co ``detect_host_profile()``, i zgadzać się z decyzją
aktywacji server-guarda dla tych samych wejść (te same zmienne ``GUARD_*``).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from guides import cli
from guides.host_profile import detect_host_profile

NODE = shutil.which("node")
SERVER_GUARD = Path(__file__).resolve().parents[1] / "templates" / "shared" / "guards" / "server-guard.mjs"


def _guard_decision(command: str, env: dict[str, str]) -> str:
    """Decyzja aktywacji server-guarda dla komendy Bash (prawdziwy proces node)."""
    proc = subprocess.run(
        [NODE or "node", str(SERVER_GUARD)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **env},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout).get("hookSpecificOutput", {}).get("permissionDecision", "")


def _run(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    out = io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=False):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
    return code, out.getvalue()


class TestHostCommand(unittest.TestCase):
    def test_override_local_and_vps(self) -> None:
        for override in ("local", "vps", "VPS"):
            with self.subTest(override=override):
                code, out = _run("host", env={"KIT_HOST_PROFILE": override, "GUIDES_HOST_PROFILE": ""})
                expected = detect_host_profile(env={"KIT_HOST_PROFILE": override})
                self.assertEqual(code, 0, out)
                self.assertEqual(out.splitlines()[0], expected)

    def test_first_line_is_value_only(self) -> None:
        code, out = _run("host", env={"KIT_HOST_PROFILE": "vps"})
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "vps")

    def test_guides_alias_override(self) -> None:
        code, out = _run("host", env={"KIT_HOST_PROFILE": "", "GUIDES_HOST_PROFILE": "local"})
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "local")

    def test_ci_is_local(self) -> None:
        code, out = _run(
            "host",
            env={"KIT_HOST_PROFILE": "", "GUIDES_HOST_PROFILE": "", "CI": "true", "GITHUB_ACTIONS": ""},
        )
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "local")


@unittest.skipUnless(NODE, "brak node")
class TestHostServerGuardParity(unittest.TestCase):
    """Ten sam profil env → ``kit-ai host`` i aktywacja guarda mówią to samo."""

    def test_env_profiles_match_guard_decision(self) -> None:
        gib = 1024**3
        base = ("linux", 1, 4 * gib, 0, "lxc", False, False, False)
        cases = [
            base,
            ("darwin", *base[1:]),
            (*base[:6], True, False),
            (*base[:7], True),
            (base[0], 4, *base[2:]),
            (*base[:2], 16 * gib, *base[3:]),
            (*base[:3], gib, *base[4:]),
            (*base[:4], "none", True, False, False),
            (*base[:4], "none", False, False, False),
            (*base[:4], "", True, False, False),
        ]
        flag = {True: "1", False: "0"}
        for plat, cpu, mem, swap, virt, desktop, ci, wsl in cases:
            with self.subTest(case=(plat, cpu, mem, swap, virt, desktop, ci, wsl)):
                env = {
                    "KIT_HOST_PROFILE": "", "GUIDES_HOST_PROFILE": "",
                    "GUARD_PLATFORM": plat, "GUARD_CPU_COUNT": str(cpu),
                    "GUARD_MEM_BYTES": str(mem), "GUARD_SWAP_BYTES": str(swap),
                    "GUARD_VIRT": virt, "GUARD_HAS_DESKTOP": flag[desktop],
                    "GUARD_IS_CI": flag[ci], "GUARD_IS_WSL": flag[wsl],
                }
                code, out = _run("host", env=env)
                self.assertEqual(code, 0, out)
                host = out.splitlines()[0]
                guard = _guard_decision("docker compose up", env)
                self.assertEqual(
                    host,
                    "vps" if guard == "deny" else "local",
                    (env, out, guard),
                )


if __name__ == "__main__":
    unittest.main()
