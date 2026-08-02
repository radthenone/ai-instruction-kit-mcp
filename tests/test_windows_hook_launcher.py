#!/usr/bin/env python3
"""Test Windows Cursor hook launcher (run-hook.ps1) without opening consoles."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / ".cursor" / "hooks" / "run-hook.ps1"
CASES: list[tuple[str, str, str]] = [
    ("gate-destructive.sh", '{"command":"git status"}', "allow"),
    ("gate-destructive.sh", '{"command":"git push --force origin main"}', "deny"),
    ("gate-destructive.sh", '{"command":"git push -f origin master"}', "deny"),
    ("gate-destructive.sh", '{"command":"git push origin +main"}', "deny"),
    ("gate-destructive.sh", '{"command":"git push origin feat/x"}', "allow"),
    ("gate-destructive.sh", '{"command":"git push --force origin feat/x"}', "ask"),
    ("gate-push.sh", '{"command":"git push origin feat/x"}', "ask"),
]


def run_case(script: str, payload: str) -> tuple[int, str, str]:
    """Uruchom run-hook.ps1 z JSON na stdin; zwróć (code, stdout, stderr)."""
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
            "-Script",
            script,
        ],
        input=payload.encode("utf-8"),
        capture_output=True,
        cwd=str(ROOT),
        timeout=60,
        check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
        "utf-8", "replace"
    )


def main() -> int:
    if not PS1.is_file():
        print(f"FAIL missing {PS1}", file=sys.stderr)
        return 1

    failed = 0
    for script, payload, expect in CASES:
        code, out, err = run_case(script, payload)
        text = out.strip()
        try:
            data = json.loads(text)
            perm = str(data.get("permission", ""))
        except json.JSONDecodeError:
            print(f"FAIL invalid JSON script={script} payload={payload!r} out={text!r} err={err!r}")
            failed += 1
            continue

        if perm != expect:
            print(
                f"FAIL expected={expect} got={perm} script={script} "
                f"payload={payload!r} out={text!r} err={err!r} code={code}"
            )
            failed += 1
            continue

        print(f"OK  [{perm}] {script} :: {payload}")

    if failed:
        print(f"\n{failed} failed", file=sys.stderr)
        return 1
    print("\nAll Windows hook launcher checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
