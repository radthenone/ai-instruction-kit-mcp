#!/usr/bin/env python3
"""Test gate hooks via bash (--noprofile --norc) and node invoke-hook.js."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES: list[tuple[str, dict[str, str], str]] = [
    ("gate-destructive.sh", {"command": "git status"}, "allow"),
    ("gate-destructive.sh", {"command": "git push --force origin main"}, "deny"),
    ("gate-destructive.sh", {"command": "git push origin +main"}, "deny"),
    ("gate-destructive.sh", {"command": "git push -f origin master"}, "deny"),
    ("gate-destructive.sh", {"command": "git push --force origin feat/x"}, "ask"),
    ("gate-destructive.sh", {"command": "git push origin feat/x"}, "allow"),
    ("gate-destructive.sh", {"command": "git push git+https://example.com/repo.git main"}, "ask"),
    ("gate-destructive.sh", {"command": "git push git+https://example.com/repo.git feat/x"}, "allow"),
    ("gate-destructive.sh", {"command": "git push origin dev"}, "ask"),
    ("gate-push.sh", {"command": "git push origin feat/x"}, "ask"),
]


def resolve_bash() -> str | None:
    """
    Znajdź bash do testów: na Windows preferuj Git Bash, inaczej PATH.

    Returns:
        str | None: Ścieżka do bash albo ``None`` gdy niedostępny.
    """
    if os.name == "nt":
        candidates = [
            Path(r"C:/Program Files/Git/bin/bash.exe"),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Git"
            / "bin"
            / "bash.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    found = shutil.which("bash")
    return found


def main() -> int:
    bash = resolve_bash()
    if not bash:
        print("SKIP no bash on PATH / Git for Windows", file=sys.stderr)
        return 0

    failed = 0
    for script, payload, expect in CASES:
        hook = ROOT / ".cursor" / "hooks" / script
        proc = subprocess.run(
            [bash, "--noprofile", "--norc", str(hook).replace("\\", "/")],
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

    invoker = ROOT / ".cursor" / "hooks" / "invoke-hook.js"
    if invoker.is_file() and shutil.which("node"):
        proc = subprocess.run(
            ["node", str(invoker), "gate-destructive.sh"],
            input=json.dumps({"command": "git status"}).encode("utf-8"),
            capture_output=True,
            cwd=str(ROOT),
            timeout=45,
            check=False,
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        try:
            perm = str(json.loads(out).get("permission", ""))
        except json.JSONDecodeError:
            print(f"FAIL invoke-hook invalid JSON: {out!r}")
            failed += 1
        else:
            if perm != "allow":
                print(f"FAIL invoke-hook expected=allow got={perm}")
                failed += 1
            else:
                print("OK  [allow] invoke-hook.js gate-destructive.sh")
    else:
        print("SKIP invoke-hook.js (brak node lub pliku)")

    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print("All bash --noprofile hook checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
