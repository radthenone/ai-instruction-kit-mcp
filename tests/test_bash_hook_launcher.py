#!/usr/bin/env python3
"""Test gate hooks via Git Bash (--noprofile --norc), no PowerShell."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASH = Path(r"C:/Program Files/Git/bin/bash.exe")
CASES: list[tuple[str, dict[str, str], str]] = [
    ("gate-destructive.sh", {"command": "git status"}, "allow"),
    ("gate-destructive.sh", {"command": "git push --force origin main"}, "deny"),
    ("gate-destructive.sh", {"command": "git push origin +main"}, "deny"),
    ("gate-destructive.sh", {"command": "git push -f origin master"}, "deny"),
    ("gate-destructive.sh", {"command": "git push --force origin feat/x"}, "ask"),
    ("gate-destructive.sh", {"command": "git push origin feat/x"}, "allow"),
    ("gate-push.sh", {"command": "git push origin feat/x"}, "ask"),
]


def main() -> int:
    if not BASH.is_file():
        print(f"FAIL missing bash: {BASH}", file=sys.stderr)
        return 1

    failed = 0
    for script, payload, expect in CASES:
        hook = ROOT / ".cursor" / "hooks" / script
        proc = subprocess.run(
            [str(BASH), "--noprofile", "--norc", str(hook).replace("\\", "/")],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            cwd=str(ROOT),
            timeout=45,
            check=False,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        try:
            perm = str(json.loads(out).get("permission", ""))
        except json.JSONDecodeError:
            print(f"FAIL invalid JSON {script}: {out!r} err={proc.stderr!r}")
            failed += 1
            continue
        if perm != expect:
            print(f"FAIL expected={expect} got={perm} {script} {payload}")
            failed += 1
            continue
        print(f"OK  [{perm}] {script}")

    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print("All bash --noprofile hook checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
