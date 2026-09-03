"""Wykonanie ``scripts/bootstrap-project.sh`` z poziomu serwera MCP.

Skrypt bash zostaje **jedynym źródłem prawdy** o tym, co bootstrap gdzie kładzie.
Ten moduł tylko go uruchamia (Windows: Git Bash, ta sama logika co
``templates/shared/guards/invoke-hook.js``) i — dla trybu dry-run — robi to
w sandboxie, żeby plan zmian pochodził z faktycznego przebiegu skryptu, a nie
z drugiej, rozjeżdżającej się listy ścieżek w Pythonie.
"""

from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_REL_PATH = "scripts/bootstrap-project.sh"

# Powierzchnia repo aplikacji, którą bootstrap czyta lub zapisuje. Sandbox dry-runu
# dostaje kopię dokładnie tych ścieżek — dzięki temu „nie nadpisuj jeśli istnieje"
# (AGENTS.md, BUGBOT.md, .ai/project.md), scalanie `.claude/settings.json` i sprzątanie
# klientów spoza `--clients` zachowują się w planie tak jak zachowają się na żywo.
KIT_SURFACE: tuple[str, ...] = (
    ".agents",
    ".ai",
    ".claude",
    ".codex",
    ".cursor",
    ".github/copilot-instructions.md",
    ".github/prompts",
    ".kilocode",
    ".kiro",
    ".mcp.json",
    ".opencode",
    ".vscode",
    "AGENTS.md",
    "BUGBOT.md",
    "git-hooks",
    "opencode.json",
)

_TIMEOUT_SECONDS = 600


class BootstrapError(RuntimeError):
    """Bootstrap nie mógł zostać uruchomiony albo zakończył się błędem."""


@dataclass
class BootstrapPlan:
    """Różnica między stanem repo a wynikiem przebiegu skryptu w sandboxie."""

    created: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    script_output: str = ""

    @property
    def touches_disk(self) -> bool:
        """Czy realny przebieg w ogóle coś by zmienił."""
        return bool(self.created or self.modified or self.deleted)


def find_bash() -> str:
    """
    Znajdź interpreter bash do uruchomienia skryptu polityki/bootstrapu.

    Na Linuksie i macOS ``bash`` jest w PATH. Windows go tam nie ma, więc (i tylko
    tam) szukamy Git Basha pod typowymi ścieżkami instalacji — ta sama kolejność
    kandydatów co w ``templates/shared/guards/invoke-hook.js``.

    Returns:
        str: Ścieżka do bash.exe (Windows) albo ``"bash"``.
    """
    if os.name != "nt":
        return "bash"
    program_files = os.environ.get("ProgramFiles") or "C:\\Program Files"
    local_app_data = os.environ.get("LocalAppData") or ""
    candidates = [
        Path(program_files) / "Git" / "bin" / "bash.exe",
        Path(program_files) / "Git" / "usr" / "bin" / "bash.exe",
    ]
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Git" / "bin" / "bash.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return "bash"


def _script_path(kit_root: Path) -> Path:
    script = kit_root / SCRIPT_REL_PATH
    if not script.is_file():
        raise BootstrapError(f"Brak skryptu bootstrapu: {script}")
    return script


def build_args(
    *,
    kit_root: Path,
    target: Path,
    clients: str = "all",
    preset: str = "_base",
    language: str = "pl",
    codegen: str = "orval",
    from_src: str | None = None,
    with_overlay: bool = False,
    with_profile: bool = False,
    skip_agents: bool = False,
    keep_unselected_clients: bool = False,
) -> list[str]:
    """
    Zbuduj listę argumentów wywołania ``bootstrap-project.sh``.

    Args:
        kit_root: Root repozytorium instruction-kit (źródło szablonów).
        target: Repo aplikacji, do którego lądują pliki.
        clients: Wartość ``--clients`` (już zwalidowana przez ``guides.clients``).
        preset: Kategoria presetu, np. ``_base``, ``shop``.
        language: Język prozy instrukcji (``pl``/``en``).
        codegen: Generator klienta API (``orval``/``none``/``graphql``).
        from_src: Wartość ``--from``; domyślnie lokalna ścieżka kita.
        with_overlay: Dołóż ``--with-overlay``.
        with_profile: Dołóż ``--with-profile``.
        skip_agents: Dołóż ``--skip-agents``.
        keep_unselected_clients: Nie sprzątaj plików klientów spoza ``--clients``.

    Returns:
        list[str]: Argv dla bash (bez samego interpretera).
    """
    script = _script_path(kit_root)
    args = [
        str(script).replace("\\", "/"),
        str(target).replace("\\", "/"),
        "--preset",
        preset,
        "--language",
        language,
        "--codegen",
        codegen,
        "--clients",
        clients,
        "--from",
        (from_src or str(kit_root)).replace("\\", "/"),
    ]
    if with_overlay:
        args.append("--with-overlay")
    if with_profile:
        args.append("--with-profile")
    if skip_agents:
        args.append("--skip-agents")
    if keep_unselected_clients:
        args.append("--keep-unselected-clients")
    return args


def run_bootstrap(**kwargs) -> str:
    """
    Uruchom bootstrap na wskazanym katalogu (**zapisuje na dysk**).

    Args:
        **kwargs: Jak w :func:`build_args` (``kit_root``, ``target``, flagi).

    Returns:
        str: Stdout skryptu (lista założonych plików).

    Raises:
        BootstrapError: Brak skryptu, brak basha, timeout albo niezerowy exit code.
    """
    argv = build_args(**kwargs)
    bash = find_bash()
    try:
        result = subprocess.run(
            [bash, "--noprofile", "--norc", *argv],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BootstrapError(
            f"Nie znaleziono interpretera bash (`{bash}`). Na Windows zainstaluj Git for Windows."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BootstrapError(
            f"Bootstrap przekroczył {_TIMEOUT_SECONDS}s i został przerwany."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(pusty stderr)"
        raise BootstrapError(
            f"bootstrap-project.sh zakończył się kodem {result.returncode}: {stderr}"
        )
    return (result.stdout or "").strip()


def _seed_sandbox(workspace_root: Path, sandbox: Path) -> None:
    """Skopiuj do sandboxu tylko te ścieżki repo, których dotyka bootstrap."""
    for rel in KIT_SURFACE:
        src = workspace_root / rel
        if not src.exists():
            continue
        dest = sandbox / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def plan_bootstrap(*, workspace_root: Path, **kwargs) -> BootstrapPlan:
    """
    Policz, co bootstrap by zmienił — bez dotykania repo aplikacji.

    Skrypt leci naprawdę, ale na kopii kitowej powierzchni repo w katalogu
    tymczasowym (patrz :data:`KIT_SURFACE`). Wynik porównujemy z oryginałem,
    więc plan zna też pliki, które sprzątanie klientów spoza ``--clients``
    by **usunęło**.

    Args:
        workspace_root: Repo aplikacji (tylko odczyt).
        **kwargs: Jak w :func:`build_args`, bez ``target``.

    Returns:
        BootstrapPlan: Listy created/modified/deleted/unchanged + stdout skryptu.

    Raises:
        BootstrapError: Jak w :func:`run_bootstrap`.
    """
    kwargs.pop("target", None)
    with tempfile.TemporaryDirectory(prefix="guides-bootstrap-dry-") as tmp:
        sandbox = Path(tmp) / "workspace"
        sandbox.mkdir(parents=True)
        _seed_sandbox(workspace_root, sandbox)
        before = _relative_files(sandbox)

        output = run_bootstrap(target=sandbox, **kwargs)

        after = _relative_files(sandbox)
        plan = BootstrapPlan(script_output=output)
        for rel in sorted(after - before):
            plan.created.append(rel)
        for rel in sorted(before - after):
            plan.deleted.append(rel)
        for rel in sorted(before & after):
            same = filecmp.cmp(workspace_root / rel, sandbox / rel, shallow=False)
            (plan.unchanged if same else plan.modified).append(rel)
        return plan
