"""Tani status "czy kit się zmienił od bootstrapu" — bez czytania treści modułów."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

STAMP_REL_PATH = ".ai/.kit-bootstrap.json"

# Ścieżki które bootstrap-project.sh faktycznie kopiuje/renderuje do konsumenta —
# tylko te obchodzą "czy trzeba re-bootstrapować" (treść modules/*.md kit czyta live,
# nie kopiuje, więc nie wchodzi do tej listy).
_TRACKED_GLOBS: tuple[str, ...] = (
    "templates/shared/agents/*.md",
    "templates/*/mcp.json",
    "templates/*/mcp_config.json",
    "templates/codex/config.toml",
    "templates/opencode/opencode.json",
    "templates/AGENTS.md",
    "templates/project.md",
    "scripts/bootstrap-project.sh",
    "scripts/render_agent_commands.py",
)


def _read_stamp(workspace_root: Path) -> dict | None:
    path = workspace_root / STAMP_REL_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _git(kit_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(kit_root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def check_kit_updates(kit_root: Path, workspace_root: Path) -> str:
    """
    Porównaj commit kita zapisany przy ostatnim bootstrapie z aktualnym HEAD.

    Tanie: tylko `git rev-parse`/`git diff --name-only` na kicie + jeden odczyt
    pliku stamp — bez czytania treści modułów instrukcji.

    Args:
        kit_root: Root instruction-kit (lokalny klon, z --from/kit_root MCP).
        workspace_root: Root repo aplikacji (gdzie leży `.ai/.kit-bootstrap.json`).

    Returns:
        str: Markdown — status "aktualny" / "kit się zmienił" / brak stampu / brak
            lokalnej historii git do porównania.
    """
    stamp = _read_stamp(workspace_root)
    if stamp is None:
        return (
            "# Kit status: brak stampu\n\n"
            f"Nie znaleziono `{STAMP_REL_PATH}` w repo aplikacji — projekt nie był "
            "bootstrapowany wersją kita ze stampem (albo plik usunięty). "
            "Uruchom `bootstrap-project.sh` żeby go założyć."
        )

    stamp_commit = stamp.get("kit_commit") or ""
    kit_from = stamp.get("kit_from", "—")
    bootstrapped_at = stamp.get("bootstrapped_at", "—")

    if not stamp_commit:
        return (
            "# Kit status: brak historii git\n\n"
            f"Kit źródło: `{kit_from}` (nie lokalny klon git przy bootstrapie — "
            "brak commitu do porównania). Re-bootstrapuj ręcznie okresowo, albo "
            "sklonuj kit lokalnie żeby dostać porównanie."
        )

    current_commit = _git(kit_root, "rev-parse", "HEAD")
    if current_commit is None:
        return (
            "# Kit status: kit_root nie jest (już) repo git\n\n"
            f"Ścieżka: `{kit_root}`. Nie można porównać — sprawdź ręcznie."
        )

    if current_commit == stamp_commit:
        return (
            "# Kit status: aktualny\n\n"
            f"- Bootstrapowano: {bootstrapped_at}\n"
            f"- Commit: `{stamp_commit[:12]}`\n"
            "- Nic nowego w kicie od ostatniego bootstrapu."
        )

    count = _git(kit_root, "rev-list", "--count", f"{stamp_commit}..{current_commit}")
    changed_files: list[str] = []
    for pattern in _TRACKED_GLOBS:
        out = _git(
            kit_root, "diff", "--name-only", f"{stamp_commit}..{current_commit}", "--", pattern
        )
        if out:
            changed_files.extend(line for line in out.splitlines() if line)

    lines = [
        "# Kit status: ZMIENIŁ SIĘ od ostatniego bootstrapu",
        "",
        f"- Bootstrapowano: {bootstrapped_at} (`{stamp_commit[:12]}`)",
        f"- Teraz: `{current_commit[:12]}`"
        + (f" ({count} commitów później)" if count else ""),
        "",
    ]
    if changed_files:
        lines.append("## Pliki które re-bootstrap by nadpisał:")
        lines.append("")
        lines.extend(f"- `{f}`" for f in sorted(set(changed_files)))
        lines.append("")
        lines.append(
            "Uruchom ponownie `bootstrap-project.sh` (te same flagi co poprzednio) "
            "żeby dostać aktualizację. **Nadpisze** `.claude/agents/`, `.cursor/agents/`, "
            "`.claude/commands/`, `mcp.json` — jeśli je ręcznie edytowałeś, zrób "
            "`git diff` najpierw."
        )
    else:
        lines.append(
            "Kit ma nowe commity, ale żaden nie dotyka plików które bootstrap kopiuje "
            "do tego repo (agents/commands/mcp.json) — re-bootstrap niepotrzebny. "
            "Moduły instrukcji (`modules/*.md`) i tak są czytane live, bez kopii."
        )

    return "\n".join(lines)
