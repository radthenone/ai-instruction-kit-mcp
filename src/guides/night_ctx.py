"""Nagłówek kontekstu nocy ``/night-run`` — jedno deterministyczne źródło (#314).

Orkiestrator nie wnioskuje już ``Host`` z treści bundla: uruchamia ``kit-ai night-ctx``
i wkleja wynik bez zmian. Ten sam moduł liczy BASE wspólną regułą bazy, bramki szybkie
z overlayu albo CI i język z Profilu. Watchdog nocy porównuje ``host=`` ze znacznika
z bieżącym ``kit-ai host``.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from guides.host_profile import get_host_profile
from guides.resolver import (
    PROFILE_REL_PATH,
    normalize_language,
    overlay_base,
    overlay_commands,
)

NIGHT_CTX_VERSION = "v1"
MARKER_RE = re.compile(r"<!--\s*kit-ai night-ctx v(\d+) host=(vps|local)\s*-->")
DEFAULT_GATES = ("ruff check", "pytest <pliki dotknięte ticketem>")
CI_TRIGGERS = ("pull_request", "pull_request_target", "push")
_CI_EXCLUDE = re.compile(r"\b(deploy|publish|release|secret)\b", re.IGNORECASE)
_GATE_LIMIT = 4


def marker(host: str) -> str:
    """Linia-znacznik generatora nagłówka (watchdog czyta z niej ``host=``)."""
    return f"<!-- kit-ai night-ctx {NIGHT_CTX_VERSION} host={host} -->"


def _git(repo: Path, *args: str) -> str | None:
    """Wynik ``git`` w repo albo ``None`` (brak repo / błąd komendy)."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _default_branch(repo: Path) -> str:
    """Gałąź domyślna z ``origin/HEAD``; bez niej ``main`` / ``master``."""
    ref = _git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if ref and "/" in ref:
        return ref.split("/", 1)[1]
    for candidate in ("main", "master"):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"origin/{candidate}"):
            return candidate
    return "main"


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """Czy ``ancestor`` jest przodkiem ``descendant`` (``git merge-base``)."""
    return _git(repo, "merge-base", "--is-ancestor", ancestor, descendant) is not None


def base_branch(workspace: Path, overlay_text: str) -> tuple[str, str]:
    """BASE i powód — ta sama reguła co w ``/git-start`` i ``/night-run``.

    Returns:
        tuple: ``(gałąź, powód)`` — ``base: z project.md``, ``dev aktywny``,
            ``dev w tyle``, ``brak dev`` albo ``dev zrównany``.
    """
    forced = overlay_base(overlay_text)
    if forced:
        return forced, "base: z project.md"
    if _git(workspace, "rev-parse", "--git-dir") is None:
        return "main", "brak repo gita (założenie)"
    default = _default_branch(workspace)
    dev = _git(workspace, "rev-parse", "--verify", "--quiet", "origin/dev")
    if not dev:
        return default, "brak dev"
    default_sha = _git(workspace, "rev-parse", "--verify", "--quiet", f"origin/{default}")
    if not default_sha:
        return "dev", "dev aktywny"
    if dev == default_sha:
        return default, "dev zrównany"
    if _is_ancestor(workspace, "origin/dev", f"origin/{default}"):
        return default, "dev w tyle"
    return "dev", "dev aktywny"


def _ci_triggers(raw: object) -> bool:
    """Czy workflow odpala się na ``pull_request`` / ``push``."""
    if isinstance(raw, dict):
        keys = raw.keys()
    elif isinstance(raw, (list, tuple)):
        keys = raw
    elif isinstance(raw, str):
        keys = [raw]
    else:
        return False
    return any(str(key) in CI_TRIGGERS for key in keys)


def ci_gates(workspace: Path) -> list[str]:
    """Kroki ``run:`` z workflow na PR/push, bez deploy / publikacji / sekretów."""
    workflows = workspace / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    gates: list[str] = []
    for path in sorted(workflows.glob("*.y*ml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        # PyYAML czyta niecytowane ``on:`` jako klucz boolean ``True`` (YAML 1.1).
        if not _ci_triggers(data.get("on", data.get(True))):
            continue
        jobs = data.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job in jobs.values():
            steps = job.get("steps") if isinstance(job, dict) else None
            for step in steps or []:
                if not isinstance(step, dict):
                    continue
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                command = next((ln.strip() for ln in run.splitlines() if ln.strip()), "")
                if not command or _CI_EXCLUDE.search(command):
                    continue
                if _CI_EXCLUDE.search(str(step.get("name", ""))):
                    continue
                if command not in gates:
                    gates.append(command)
    return gates[:_GATE_LIMIT]


def quick_gates(workspace: Path, overlay_text: str) -> tuple[list[str], str]:
    """Bramki szybkie i ich źródło: overlay → CI → jawne założenie."""
    commands = overlay_commands(overlay_text, limit=_GATE_LIMIT)
    if commands:
        return commands, "overlay"
    commands = ci_gates(workspace)
    if commands:
        return commands, "CI"
    return list(DEFAULT_GATES), "założenie (brak overlayu i CI)"


def _profile(workspace: Path) -> dict[str, object]:
    """Profil projektu albo pusty słownik (brak / nieczytelny plik)."""
    path = workspace / PROFILE_REL_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def render_night_ctx(workspace: Path, *, host: str | None = None) -> str:
    """Złóż nagłówek CTX nocy ze znacznikiem generatora."""
    workspace = workspace.resolve()
    host = get_host_profile() if host is None else host
    overlay_path = workspace / ".ai" / "project.md"
    try:
        overlay_text = overlay_path.read_text(encoding="utf-8")
    except OSError:
        overlay_text = ""
    profile = _profile(workspace)
    language = normalize_language(str(profile.get("language", "pl")))
    name = str(profile.get("name") or workspace.name)
    base, base_reason = base_branch(workspace, overlay_text)
    gates, gate_source = quick_gates(workspace, overlay_text)
    gate_text = ", ".join(f"`{gate}`" for gate in gates)
    return "\n".join(
        [
            f"# Kontekst nocy — {name}",
            "",
            marker(host),
            "",
            f"- BASE: `{base}` — źródło: {base_reason}",
            f"- Host: `{host}` — źródło: `kit-ai host` (`detect_host_profile()`)",
            f"- Bramki szybkie: {gate_text} — źródło: {gate_source}",
            f"- Język: `{language}` — źródło: Profil",
            "- Pełny zestaw testów: tylko CI",
            "",
        ]
    )
