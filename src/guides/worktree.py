"""Render i walidacja konfiguracji worktree kita — stdlib only.

Jedno źródło domyślnej listy kopiowanych plików (MACHINE_FILES + .env + settings.local.json),
walidacji Profilu i renderowania `.ai/worktree.json`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

KNOWN_WORKTREE_KEYS = ("copy", "link", "setup", "venv")
VALID_VENV_VALUES = ("auto", "overlay", "none")
DEFAULT_VENV = "auto"

MACHINE_FILES: tuple[str, ...] = (
    ".mcp.json",
    ".cursor/mcp.json",
    ".vscode/mcp.json",
    ".codex/config.toml",
    ".kiro/settings/mcp.json",
    ".kilocode/mcp.json",
    ".agents/mcp_config.json",
    "opencode.json",
    ".ai/.kit-bootstrap.json",
    ".ai/.kit-doctor.json",
)

EXTRA_COPY_FILES: tuple[str, ...] = (
    ".env",
    ".claude/settings.local.json",
)


HOOK_BEGIN = "# >>> instruction-kit: worktree sync >>>"
HOOK_END = "# <<< instruction-kit: worktree sync <<<"
HOOK_TEMPLATE = Path("templates/shared/worktree/post-checkout.sh")
_HOOK_RE = re.compile(rf"^{re.escape(HOOK_BEGIN)}\n.*?^{re.escape(HOOK_END)}\n?", re.S | re.M)


def _has_parent_dir_ref(path_str: str) -> bool:
    """Sprawdź, czy ścieżka zawiera segment '..'."""
    parts = Path(path_str).parts
    return ".." in parts


def parse_worktree_section(text: str) -> dict[str, Any]:
    """Wyciągnij i zwaliduj sekcję `worktree:` z tekstu profilu (tolerancyjny podzbiór YAML).

    Returns:
        dict: `{"copy": list[str] | None, "link": list[str], "setup": list[str], "venv": str, "warnings": list[str]}`
    """
    result: dict[str, Any] = {
        "copy": None,
        "link": [],
        "setup": [],
        "venv": DEFAULT_VENV,
        "warnings": [],
    }
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "worktree:" and len(line) - len(line.lstrip()) == 0:
            start = i
            break
    if start is None:
        return result

    current_list: str | None = None
    for line in lines[start + 1:]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        stripped = line.strip()
        if indent == 2 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key not in KNOWN_WORKTREE_KEYS:
                result["warnings"].append(f"nieznany klucz `worktree.{key}` — pominięto")
                current_list = None
            elif key == "venv":
                if value in VALID_VENV_VALUES:
                    result["venv"] = value
                else:
                    result["warnings"].append(
                        f"zły typ/wartość `worktree.venv: {value}` — ma być `auto`, `overlay` albo `none`"
                    )
                current_list = None
            elif value:
                result["warnings"].append(f"zły typ `worktree.{key}: {value}` — ma być listą")
                current_list = None
            else:
                current_list = key
                if key == "copy":
                    result["copy"] = []
                elif key == "link":
                    result["link"] = []
                elif key == "setup":
                    result["setup"] = []
        elif stripped.startswith("-") and current_list:
            item = stripped[1:].strip().strip("'\"")
            if current_list in ("copy", "link"):
                if _has_parent_dir_ref(item):
                    result["warnings"].append(
                        f"ścieżka z `..` w `worktree.{current_list}` zabroniona: {item}"
                    )
                else:
                    result[current_list].append(item)
            elif current_list == "setup":
                # Sprawdzenie czy element jest stringiem/poleceniem
                try:
                    # YAML mógł podać liczbę itp.
                    if item.isdigit():
                        result["warnings"].append(
                            f"zły typ elementu w `worktree.setup`: {item} — ma być stringiem"
                        )
                    else:
                        result["setup"].append(item)
                except Exception:
                    result["setup"].append(item)
        elif indent == 2:
            current_list = None

    return result


def resolve_worktree_config(
    profile_data: dict[str, Any] | None,
    workspace_root: Path,
) -> dict[str, Any]:
    """Zbuduj rozwiązaną konfigurację worktree dla danego repozytorium."""
    workspace_root = workspace_root.resolve()
    raw_worktree = (profile_data or {}).get("worktree")
    
    copy_list: list[str] | None = None
    link_list: list[str] = []
    setup_list: list[str] = []
    venv_val = DEFAULT_VENV

    if isinstance(raw_worktree, dict):
        if "copy" in raw_worktree and isinstance(raw_worktree["copy"], list):
            copy_list = [str(x) for x in raw_worktree["copy"] if not _has_parent_dir_ref(str(x))]
        if "link" in raw_worktree and isinstance(raw_worktree["link"], list):
            link_list = [str(x) for x in raw_worktree["link"] if not _has_parent_dir_ref(str(x))]
        if "setup" in raw_worktree and isinstance(raw_worktree["setup"], list):
            setup_list = [str(x) for x in raw_worktree["setup"]]
        if "venv" in raw_worktree and str(raw_worktree["venv"]) in VALID_VENV_VALUES:
            venv_val = str(raw_worktree["venv"])

    if copy_list is None:
        # Bez filtra istnienia: wynik nie zależy od tego, które pliki są w repo (deterministyczny JSON).
        copy_list = [*MACHINE_FILES, *EXTRA_COPY_FILES]

    return {
        "copy": copy_list,
        "link": link_list,
        "setup": setup_list,
        "venv": venv_val,
    }


def render_worktree_config(workspace_root: Path, profile_path: Path | None = None) -> Path:
    """Zapisz rozwiązaną konfigurację do `.ai/worktree.json`."""
    workspace_root = workspace_root.resolve()
    profile_data: dict[str, Any] = {}
    if profile_path is None:
        profile_path = workspace_root / ".ai" / "project.profile.yaml"

    if profile_path.is_file():
        parsed = parse_worktree_section(profile_path.read_text(encoding="utf-8"))
        profile_data = {"worktree": parsed}

    config = resolve_worktree_config(profile_data, workspace_root)
    out_dir = workspace_root / ".ai"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "worktree.json"
    out_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out_file


def check_worktree_drift(workspace_root: Path, profile_path: Path | None = None) -> list[str]:
    """Sprawdź, czy `.ai/worktree.json` istnieje i jest zgodny z konfiguracją w profilu."""
    workspace_root = workspace_root.resolve()
    json_path = workspace_root / ".ai" / "worktree.json"
    if not json_path.is_file():
        return ["brak `.ai/worktree.json` — uruchom `kit-ai reload`"]

    if profile_path is None:
        profile_path = workspace_root / ".ai" / "project.profile.yaml"

    parsed: dict[str, Any] = {"copy": None, "link": [], "setup": [], "venv": DEFAULT_VENV, "warnings": []}
    has_worktree = False
    if profile_path.is_file():
        text = profile_path.read_text(encoding="utf-8")
        has_worktree = any(line.strip() == "worktree:" for line in text.splitlines())
        parsed = parse_worktree_section(text)

    try:
        current = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"niepoprawny JSON w `.ai/worktree.json`: {exc}"]

    if has_worktree:
        if parsed.get("copy") is not None and current.get("copy") != parsed.get("copy"):
            return ["rozjazd z Profilem — uruchom `kit-ai reload`"]
        if current.get("link") != parsed.get("link"):
            return ["rozjazd z Profilem — uruchom `kit-ai reload`"]
        if current.get("setup") != parsed.get("setup"):
            return ["rozjazd z Profilem — uruchom `kit-ai reload`"]
        if current.get("venv") != parsed.get("venv"):
            return ["rozjazd z Profilem — uruchom `kit-ai reload`"]
    else:
        if current.get("link") != [] or current.get("setup") != [] or current.get("venv") != DEFAULT_VENV:
            return ["rozjazd z Profilem — uruchom `kit-ai reload`"]

    return []


def post_checkout_hook_path(workspace_root: Path) -> Path | None:
    """
    Ścieżka hooka `post-checkout` repo, z uwzględnieniem `core.hooksPath`.

    Args:
        workspace_root: Root repo aplikacji.

    Returns:
        Path | None: Plik hooka (może nie istnieć); ``None``, gdy ``workspace_root``
            nie jest rootem repo git (np. katalog w cudzym repo albo brak gita).
    """
    workspace_root = workspace_root.resolve()

    def git(*args: str) -> str | None:
        try:
            res = subprocess.run(
                ["git", *args], cwd=workspace_root, capture_output=True, text=True, check=False
            )
        except OSError:
            return None
        return res.stdout.strip() if res.returncode == 0 else None

    top = git("rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != workspace_root:
        return None
    hooks = git("rev-parse", "--git-path", "hooks")
    if not hooks:
        return None
    return (workspace_root / Path(hooks).expanduser()).resolve() / "post-checkout"


SHELL_SHEBANG = "#!/bin/sh"
_SHELLS = ("sh", "bash", "dash", "zsh", "ksh")


def render_hook_block(kit_root: Path) -> str:
    """
    Blok kita do hooka `post-checkout`: treść szablonu między markerami.

    Args:
        kit_root: Root kita (z ``templates/shared/worktree/post-checkout.sh``).

    Returns:
        str: Blok z markerami, końce linii LF, zakończony znakiem nowej linii.
    """
    body = (kit_root / HOOK_TEMPLATE).read_text(encoding="utf-8").replace("\r\n", "\n")
    return f"{HOOK_BEGIN}\n{body.rstrip()}\n{HOOK_END}\n"


def _read_hook(path: Path) -> str:
    """Treść hooka z końcami linii LF; pusty string, gdy pliku nie ma."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else ""


def _is_shell_shebang(line: str) -> bool:
    """Czy shebang wskazuje powłokę POSIX, w której zadziała blok kita."""
    words = line[2:].split()
    if words and Path(words[0]).name == "env":
        words = words[1:]
    return bool(words) and Path(words[0]).name in _SHELLS


def install_worktree_hook(workspace_root: Path, kit_root: Path) -> Path | None:
    """
    Dopisz albo podmień blok kita w hooku `post-checkout`; cudza treść zostaje.

    Blok idzie zaraz po shebangu, przed cudzą treścią, bo ta może kończyć się ``exec``.
    Cudzego hooka w innym języku niż powłoka (np. ``#!/usr/bin/env python3``) nie rusza.

    Args:
        workspace_root: Root repo aplikacji.
        kit_root: Root kita (z szablonem hooka).

    Returns:
        Path | None: Ścieżka hooka z blokiem kita; ``None``, gdy to nie repo git
            albo cudzy hook nie jest skryptem powłoki.
    """
    path = post_checkout_hook_path(workspace_root)
    if path is None:
        return None
    block = render_hook_block(kit_root)
    text = _read_hook(path)
    if _HOOK_RE.search(text):
        new = _HOOK_RE.sub(lambda _m: block, text, count=1)
    elif not text.strip():
        new = f"{SHELL_SHEBANG}\n{block}"
    else:
        shebang, _, rest = text.partition("\n")
        if not _is_shell_shebang(shebang):
            return None
        new = f"{shebang}\n{block}{rest}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def remove_worktree_hook(workspace_root: Path) -> Path | None:
    """
    Usuń blok kita z hooka `post-checkout`; plik znika, gdy poza blokiem został sam shebang kita.

    Args:
        workspace_root: Root repo aplikacji.

    Returns:
        Path | None: Ścieżka zmienionego albo usuniętego hooka; ``None``, gdy nie było bloku.
    """
    path = post_checkout_hook_path(workspace_root)
    if path is None:
        return None
    text = _read_hook(path)
    if not _HOOK_RE.search(text):
        return None
    rest = _HOOK_RE.sub("", text, count=1)
    if rest.strip() in ("", SHELL_SHEBANG):
        path.unlink()
    else:
        path.write_text(rest, encoding="utf-8", newline="\n")
    return path


def check_worktree_hook(workspace_root: Path, kit_root: Path | None) -> list[tuple[Path, str]]:
    """
    Zgłoszenia doctora: brak bloku kita w `post-checkout` albo jego stara wersja.

    Args:
        workspace_root: Root repo aplikacji.
        kit_root: Root kita; bez niego (albo bez szablonu) sprawdzany jest tylko brak bloku.

    Returns:
        list[tuple[Path, str]]: Pary (ścieżka hooka, komunikat); pusta, gdy blok jest aktualny
            albo to nie repo git.
    """
    path = post_checkout_hook_path(workspace_root)
    if path is None:
        return []
    match = _HOOK_RE.search(_read_hook(path))
    if match is None:
        return [(
            path,
            "brak bloku kita w hooku `post-checkout` — nowe worktree nie dostaną plików"
            " z `worktree:`; uruchom `kit-ai reload`",
        )]
    if kit_root is not None and (kit_root / HOOK_TEMPLATE).is_file():
        if match.group(0) != render_hook_block(kit_root):
            return [(path, "stara wersja bloku kita w hooku `post-checkout` — uruchom `kit-ai reload`")]
    return []


def _relative_hooks_path(workspace_root: Path) -> str | None:
    """Względny ``core.hooksPath`` (git rozwiązuje go od roota każdego worktree osobno)."""
    try:
        res = subprocess.run(
            ["git", "config", "core.hooksPath"], cwd=workspace_root,
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    value = res.stdout.strip()
    return value if value and not Path(value).expanduser().is_absolute() else None


def main(argv: list[str], kit_root: Path | None = None) -> int:
    """
    CLI: ``WORKSPACE [PROFILE]`` renderuje `.ai/worktree.json` i hook `post-checkout`;
    ``--remove-hook WORKSPACE`` zdejmuje blok kita z hooka.

    Args:
        argv: ``sys.argv`` wrappera ``scripts/render_worktree.py``.
        kit_root: Root kita z szablonem hooka; ``None`` = sam render `.ai/worktree.json`.

    Returns:
        int: Kod wyjścia (0 = OK, 2 = błędne wywołanie).
    """
    if len(argv) >= 3 and argv[1] == "--remove-hook":
        workspace = Path(argv[2]).resolve()
        if remove_worktree_hook(workspace) is not None:
            print("  - hook post-checkout (blok kita)")
        return 0
    if len(argv) < 2:
        print("Użycie: render_worktree.py WORKSPACE [PROFILE] | --remove-hook WORKSPACE", file=sys.stderr)
        return 2
    workspace = Path(argv[1]).resolve()
    profile = Path(argv[2]).resolve() if len(argv) > 2 else None
    out = render_worktree_config(workspace, profile)
    rel = out.relative_to(workspace) if out.is_relative_to(workspace) else out
    print(f"  + {rel}")
    if kit_root is None or post_checkout_hook_path(workspace) is None:
        return 0
    if install_worktree_hook(workspace, kit_root) is None:
        print("  ! hook post-checkout nie jest skryptem powłoki — blok kita nie dopisany", file=sys.stderr)
        return 0
    print("  + hook post-checkout (sync plików do nowego worktree)")
    relative = _relative_hooks_path(workspace)
    if relative:
        print(
            f"  ! core.hooksPath={relative} jest względny: nowe worktree czytają hooki z własnego"
            f" `{relative}`, więc sync zadziała tylko po commicie bloku kita",
            file=sys.stderr,
        )
    return 0
