"""Render i walidacja konfiguracji worktree kita — stdlib only.

Jedno źródło domyślnej listy kopiowanych plików (MACHINE_FILES + .env + settings.local.json),
walidacji Profilu i renderowania `.ai/worktree.json`.
"""

from __future__ import annotations

import json
import os
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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Użycie: render_worktree.py WORKSPACE [PROFILE]", file=sys.stderr)
        return 2
    workspace = Path(argv[1]).resolve()
    profile = Path(argv[2]).resolve() if len(argv) > 2 else None
    out = render_worktree_config(workspace, profile)
    rel = out.relative_to(workspace) if out.is_relative_to(workspace) else out
    print(f"  + {rel}")
    return 0
