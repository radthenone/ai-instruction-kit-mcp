"""Parytet detekcji hosta: Python (``host_profile.py``) ↔ JS (``host-profile.mjs``).

ADR-0011: hooki używają modułu JS, ``kit-ai host`` i watchdog używają Pythona.
Test odpala oba na tej samej tabeli zmiennych ``GUARD_*`` (wszystkie ustawione,
więc wynik nie zależy od maszyny) i wymaga identycznej decyzji. Bez node test
jest pomijany (na CI node jest wymagany).
"""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from guides import host_profile
from guides.host_profile import detect_host_profile

ROOT = Path(__file__).resolve().parents[1]
HOST_PROFILE_MJS = ROOT / "templates" / "shared" / "guards" / "host-profile.mjs"
NODE = shutil.which("node")

_NODE_RUNNER = """
import { pathToFileURL } from "node:url";
const modulePath = process.argv[1];
const { detectHostProfile } = await import(pathToFileURL(modulePath).href);
let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) input += chunk;
const rows = JSON.parse(input);
process.stdout.write(JSON.stringify(rows.map((env) => detectHostProfile(env))));
"""


def _table() -> list[dict[str, str]]:
    """Wszystkie kombinacje ``GUARD_*`` z poprawnymi wartościami (deterministyczne)."""
    rows: list[dict[str, str]] = []
    options = itertools.product(
        ["linux", "win32"],  # GUARD_PLATFORM
        ["0", "1"],  # GUARD_IS_CI
        ["0", "1"],  # GUARD_IS_WSL
        ["1", "2", "4"],  # GUARD_CPU_COUNT
        ["1000000000", "16000000000"],  # GUARD_MEM_BYTES
        ["0", "1000"],  # GUARD_SWAP_BYTES
        ["none", "kvm", "unknown"],  # GUARD_VIRT
        ["0", "1"],  # GUARD_HAS_DESKTOP
    )
    for plat, ci, wsl, cpu, mem, swap, virt, desktop in options:
        rows.append(
            {
                "GUARD_PLATFORM": plat,
                "GUARD_IS_CI": ci,
                "GUARD_IS_WSL": wsl,
                "GUARD_CPU_COUNT": cpu,
                "GUARD_MEM_BYTES": mem,
                "GUARD_SWAP_BYTES": swap,
                "GUARD_VIRT": virt,
                "GUARD_HAS_DESKTOP": desktop,
            }
        )
    # Devcontainer i nadpisanie profilu: sprawdzane osobno, bo wpływają na kolejność reguł.
    rows.append({**rows[0], "CODESPACES": "1"})
    rows.append({**rows[0], "KIT_HOST_PROFILE": "vps"})
    rows.append({**rows[0], "GUIDES_HOST_PROFILE": "local"})
    return rows


@unittest.skipUnless(NODE, "node nie jest zainstalowany")
class TestHostParity(unittest.TestCase):
    def test_python_and_js_agree_on_every_row(self) -> None:
        rows = _table()
        proc = subprocess.run(
            [NODE, "--input-type=module", "-e", _NODE_RUNNER, str(HOST_PROFILE_MJS)],
            input=json.dumps(rows),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js_results = json.loads(proc.stdout)
        self.assertEqual(len(js_results), len(rows))

        mismatches = [
            (row, detect_host_profile(env=row), js)
            for row, js in zip(rows, js_results)
            if detect_host_profile(env=row) != js
        ]
        self.assertEqual(mismatches, [], f"rozjazd Python/JS (wiersz, python, js): {mismatches[:3]}")


@unittest.skipUnless(NODE, "node nie jest zainstalowany")
class TestJsEmptyGuardValuesFallBack(unittest.TestCase):
    """Ta sama reguła po stronie JS: pusta zmienna = realny pomiar (``real`` w testach)."""

    def _js(self, env: dict[str, str], real: dict) -> str:
        script = (
            'const { detectHostProfile } = await import(process.argv[1]);'
            'process.stdout.write(detectHostProfile(JSON.parse(process.argv[2]), JSON.parse(process.argv[3])));'
        )
        proc = subprocess.run(
            [NODE, "--input-type=module", "-e", script, HOST_PROFILE_MJS.as_uri(),
             json.dumps(env), json.dumps(real)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_empty_cpu_uses_measured_cpu_count(self) -> None:
        env = {"GUARD_PLATFORM": "linux", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0",
               "GUARD_CPU_COUNT": "", "GUARD_MEM_BYTES": "1000000000", "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "kvm", "GUARD_HAS_DESKTOP": "0"}
        self.assertEqual(self._js(env, {"cpuCount": 1}), "vps")
        self.assertEqual(self._js(env, {"cpuCount": 8}), "local")

    def test_non_integer_mem_falls_back_to_meminfo(self) -> None:
        env = {"GUARD_PLATFORM": "linux", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0",
               "GUARD_CPU_COUNT": "1", "GUARD_MEM_BYTES": "1e9", "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "kvm", "GUARD_HAS_DESKTOP": "0"}
        self.assertEqual(self._js(env, {"meminfo": {"mem": 1_000_000_000, "swap": 0}}), "vps")
        self.assertEqual(self._js(env, {"meminfo": {"mem": None, "swap": None}}), "local")


class TestEmptyGuardValuesFallBack(unittest.TestCase):
    """Pusta lub nieparsowalna zmienna ``GUARD_*`` = brak zmiennej → realny pomiar (ADR-0011)."""

    def test_empty_cpu_uses_measured_cpu_count(self) -> None:
        env = {"GUARD_PLATFORM": "linux", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0",
               "GUARD_CPU_COUNT": "", "GUARD_MEM_BYTES": "1000000000", "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "kvm", "GUARD_HAS_DESKTOP": "0"}
        with mock.patch.object(host_profile.os, "cpu_count", return_value=1):
            self.assertEqual(detect_host_profile(env=env), "vps")
        with mock.patch.object(host_profile.os, "cpu_count", return_value=8):
            self.assertEqual(detect_host_profile(env=env), "local")

    def test_non_integer_mem_falls_back_to_meminfo(self) -> None:
        env = {"GUARD_PLATFORM": "linux", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0",
               "GUARD_CPU_COUNT": "1", "GUARD_MEM_BYTES": "1e9", "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "kvm", "GUARD_HAS_DESKTOP": "0"}
        with mock.patch.object(host_profile, "_read_meminfo", return_value=(1_000_000_000, 0)):
            self.assertEqual(detect_host_profile(env=env), "vps")
        with mock.patch.object(host_profile, "_read_meminfo", return_value=(None, None)):
            self.assertEqual(detect_host_profile(env=env), "local")

    def test_empty_platform_uses_real_platform(self) -> None:
        env = {"GUARD_PLATFORM": "", "GUARD_IS_CI": "0", "GUARD_IS_WSL": "0",
               "GUARD_CPU_COUNT": "1", "GUARD_MEM_BYTES": "1000000000", "GUARD_SWAP_BYTES": "0",
               "GUARD_VIRT": "kvm", "GUARD_HAS_DESKTOP": "0"}
        with mock.patch.object(host_profile.sys, "platform", "linux"):
            self.assertEqual(detect_host_profile(env=env), "vps")
        with mock.patch.object(host_profile.sys, "platform", "win32"):
            self.assertEqual(detect_host_profile(env=env), "local")


if __name__ == "__main__":
    unittest.main()
