"""Nagłówek kontekstu nocy ``/kit-ai:night-run`` — jedno deterministyczne źródło (#314).

Orkiestrator nie wnioskuje już ``Host`` z treści bundla: uruchamia ``kit-ai night-ctx``
i wkleja wynik bez zmian. Ten sam moduł liczy BASE wspólną regułą bazy, bramki szybkie
z overlayu albo CI i język z Profilu. Watchdog nocy porównuje ``host=`` ze znacznika
z bieżącym ``kit-ai host``.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

# council ładuje scripts/model_tiers.py (wspólny resolver wpisu target z #515)
from guides.council import ProfileError, parse_profile, resolve_target
from guides.host_profile import get_host_profile
from guides.resolver import (
    PROFILE_REL_PATH,
    normalize_language,
    overlay_base,
    overlay_commands,
)

NIGHT_CTX_VERSION = "v1"
DEFAULT_GATES = ("ruff check", "pytest <pliki dotknięte ticketem>")
CI_TRIGGERS = ("pull_request", "pull_request_target", "push")
_CI_EXCLUDE = re.compile(r"\b(deploy|publish|release|secret)\b", re.IGNORECASE)
_GATE_LIMIT = 4
_GATE_TICK = re.compile(r"`([^`]+)`")
CLEAN_SLATE_KEYS = (
    "target",
    "providerInstanceId",
    "model",
    "options",
    "provider",
    "effort",
)


def marker(host: str) -> str:
    """Linia-znacznik generatora nagłówka (watchdog czyta z niej ``host=``)."""
    return f"<!-- kit-ai night-ctx {NIGHT_CTX_VERSION} host={host} -->"


def _git(repo: Path, *args: str) -> str | None:
    """Wynik ``git`` w repo albo ``None`` (brak repo / błąd komendy)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
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


def _is_strict_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """Czy ``ancestor`` jest ścisłym przodkiem ``descendant`` (nie tym samym commitem)."""
    if not _is_ancestor(repo, ancestor, descendant):
        return False
    left = _git(repo, "rev-parse", "--verify", "--quiet", ancestor)
    right = _git(repo, "rev-parse", "--verify", "--quiet", descendant)
    return bool(left and right and left != right)


def base_branch(workspace: Path, overlay_text: str) -> tuple[str, str]:
    """BASE i powód — ta sama reguła co w ``/kit-ai:git-start`` i ``/kit-ai:night-run``.

    Returns:
        tuple: ``(gałąź, powód)`` — ``base: z project.md``, ``dev aktywny``,
            ``dev w tyle`` albo ``brak dev``.
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
    if _is_strict_ancestor(workspace, "origin/dev", f"origin/{default}"):
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


def overlay_gates(overlay_text: str) -> list[str]:
    """Komendy z sekcji ``## Komendy`` overlayu — same komendy z backticków."""
    gates: list[str] = []
    for entry in overlay_commands(overlay_text, limit=_GATE_LIMIT):
        gates.extend(_GATE_TICK.findall(entry) or [entry])
    return gates


def quick_gates(workspace: Path, overlay_text: str) -> tuple[list[str], str]:
    """Bramki szybkie (overlay + CI, bez duplikatów) i ich źródło.

    Brak obu źródeł → jawne założenie, żeby nagłówek nie udawał danych z repo.
    """
    overlay = overlay_gates(overlay_text)
    ci = ci_gates(workspace)
    gates: list[str] = []
    for gate in (*overlay, *ci):
        if gate not in gates:
            gates.append(gate)
    sources = [name for name, items in (("overlay", overlay), ("CI", ci)) if items]
    if not gates:
        return list(DEFAULT_GATES), "założenie (brak overlayu i CI)"
    return gates[:_GATE_LIMIT], " + ".join(sources)


def _profile(workspace: Path) -> dict[str, object]:
    """Profil projektu albo pusty słownik (brak / nieczytelny plik)."""
    path = workspace / PROFILE_REL_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def clean_slate_config(
    profile: Mapping[str, object], targets: Mapping[str, Mapping[str, dict]] | None = None
) -> dict[str, Any]:
    """Model i opcje Clean Slate z ``night-run.clean-slate`` w Profilu (#502, #546).

    Wspiera kształt wpisu ``target`` z #515 (ref ``target: <klient>.<tier>`` z opcjonalnym
    nadpisaniem ``model`` / ``options`` albo pełny wpis ``{providerInstanceId, model, options}``)
    oraz wsteczną zgodność z ``provider`` / ``model`` / ``effort``. Ref przechodzi przez
    ``resolve_target`` (jak w council), więc wynik ma ``providerInstanceId`` / ``model`` /
    ``options``, a ``model`` / ``options`` z sekcji wygrywają z wpisem w ``targets``.

    Args:
        profile: Wczytany Profil projektu.
        targets: Wynik ``parse_profile`` (klucz ``targets``); brak = pusty.

    Returns:
        dict: Niepuste pola konfiguracji; brak albo zły typ sekcji → ``{}``.

    Raises:
        ProfileError: Ref ``target`` bez wpisu w ``targets`` (komunikat z nazwą refu).
    """
    night = profile.get("night-run")
    section = night.get("clean-slate") if isinstance(night, dict) else None
    if not isinstance(section, dict):
        return {}
    res: dict[str, Any] = {}
    for key in CLEAN_SLATE_KEYS:
        if key not in section or section[key] is None:
            continue
        val = section[key]
        if key == "options":
            if isinstance(val, (list, dict)) and val:
                res[key] = val
        elif isinstance(val, (str, int, float)):
            s = str(val).strip()
            if s:
                res[key] = s
    if "target" in res:
        entry = {key: res[key] for key in ("target", "model", "options") if key in res}
        resolved = resolve_target(entry, dict(targets or {}))
        return {key: val for key, val in resolved.items() if val}
    return res


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
    profile_path = workspace / PROFILE_REL_PATH
    language = normalize_language(str(profile.get("language", "pl")))
    name = str(profile.get("name") or workspace.name)
    base, base_reason = base_branch(workspace, overlay_text)
    gates, gate_source = quick_gates(workspace, overlay_text)
    gate_text = ", ".join(f"`{gate}`" for gate in gates)
    try:
        try:
            clean_slate = clean_slate_config(profile)
        except ProfileError:
            # Blok targets czytamy tylko dla refu, żeby błąd w nim nie psuł nagłówka bez Clean Slate.
            clean_slate = clean_slate_config(profile, parse_profile(profile_path.read_text(encoding="utf-8"))[0])
    except (OSError, ProfileError) as err:
        clean_slate_lines = [f"- Clean Slate: błąd Profilu — {err}"]
    else:
        clean_slate_lines = (
            [
                "- Clean Slate: "
                + ", ".join(f"{key} `{value}`" for key, value in clean_slate.items())
                + " — źródło: Profil"
            ]
            if clean_slate
            else []
        )
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
            *clean_slate_lines,
            "- Pełny zestaw testów: tylko CI",
            "",
        ]
    )
