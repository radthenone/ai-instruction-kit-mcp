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
]


def expected_gate_push_permission(cwd: Path) -> str:
    """
    Oczekiwane ``permission`` dla gate-push (logika jak w skrypcie hooka).

    Args:
        cwd: Katalog repozytorium, w którym działa hook.

    Returns:
        str: ``ask`` albo ``allow``.
    """
    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "@{u}"],
        cwd=str(cwd),
        capture_output=True,
        check=False,
    )
    if upstream.returncode != 0:
        return "ask"
    local = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    remote = subprocess.run(
        ["git", "rev-parse", "@{u}"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    local_sha = (local.stdout or "").strip()
    remote_sha = (remote.stdout or "").strip()
    if local_sha and remote_sha and local_sha == remote_sha:
        return "allow"
    return "ask"


def is_ci() -> bool:
    """
    Czy działamy na CI (GitHub Actions ustawia ``CI=true``)?

    Na CI brak wymaganego narzędzia jest błędem, nie skipem — cichy skip odtworzyłby
    lukę, przez którą te suity latami nie wykonywały się w pipeline.

    Returns:
        bool: ``True`` gdy ``CI`` ustawione na coś innego niż ``0`` / ``false``.
    """
    value = os.environ.get("CI", "").strip().lower()
    return value not in ("", "0", "false")


def posix_path(path: Path) -> str:
    """
    Ścieżka w formie akceptowanej przez bash także na Windows (Git Bash).

    Args:
        path: Ścieżka do skryptu.

    Returns:
        str: Ścieżka z ukośnikami ``/``.
    """
    return str(path).replace("\\", "/")


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
        if is_ci():
            print("FAIL no bash on CI — hook checks must run", file=sys.stderr)
            return 1
        print("SKIP no bash on PATH / Git for Windows", file=sys.stderr)
        return 0

    failed = 0
    cases = list(CASES)
    cases.append(
        (
            "gate-push.sh",
            {"command": "git push origin feat/x"},
            expected_gate_push_permission(ROOT),
        )
    )
    for script, payload, expect in cases:
        hook = ROOT / ".cursor" / "hooks" / script
        proc = subprocess.run(
            [bash, "--noprofile", "--norc", posix_path(hook)],
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
            elif proc.returncode != 0:
                print(f"FAIL invoke-hook expected exit 0 got={proc.returncode}")
                failed += 1
            else:
                print("OK  [allow/exit0] invoke-hook.js gate-destructive.sh")

        # emitDeny must produce valid JSON when stderr contains control chars.
        # Exit code must be 0 so Cursor failClosed does not hide the JSON payload.
        noisy = ROOT / ".cursor" / "hooks" / "_test_noisy_stderr.sh"
        try:
            noisy.write_text(
                "#!/usr/bin/env bash\n"
                'printf "line1\\nline2\\ttab\\r" >&2\n'
                "exit 1\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["node", str(invoker), noisy.name],
                input=b"{}",
                capture_output=True,
                cwd=str(ROOT),
                timeout=45,
                check=False,
            )
            out = proc.stdout.decode("utf-8", "replace").strip()
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                print(f"FAIL emitDeny control chars → invalid JSON: {out!r}")
                failed += 1
            else:
                if payload.get("permission") != "deny":
                    print(f"FAIL emitDeny expected=deny got={payload.get('permission')}")
                    failed += 1
                elif "\n" not in str(payload.get("user_message", "")):
                    print(f"FAIL emitDeny lost newline in message: {payload!r}")
                    failed += 1
                elif proc.returncode != 0:
                    print(f"FAIL emitDeny expected exit 0 got={proc.returncode}")
                    failed += 1
                else:
                    print("OK  [deny/exit0] invoke-hook.js emitDeny escapes control chars")
        finally:
            if noisy.is_file():
                noisy.unlink()
    elif is_ci():
        print("FAIL brak node / invoke-hook.js na CI — check musi się wykonać", file=sys.stderr)
        failed += 1
    else:
        print("SKIP invoke-hook.js (brak node lub pliku)")

    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print("All bash --noprofile hook checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
