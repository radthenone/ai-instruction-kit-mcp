"""Tani status "czy kit się zmienił od bootstrapu" — bez czytania treści modułów."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

STAMP_REL_PATH = ".ai/.kit-bootstrap.json"

# Ścieżki które bootstrap-project.sh **nadpisuje** przy każdym przebiegu. Zmiana
# któregokolwiek z tych plików w kicie znaczy: re-bootstrap wciągnie ją sam.
# (Treść modules/*.md nie wchodzi tu wcale — kit czyta ją live, nie kopiuje.)
_OVERWRITTEN_GLOBS: tuple[str, ...] = (
    "templates/shared/agents/*.md",
    "templates/shared/guards/*",
    "templates/shared/skills/*/*.md",
    "templates/*/mcp.json",
    "templates/*/mcp_config.json",
    "templates/codex/config.toml",
    "templates/opencode/opencode.json",
    "templates/vscode/github/copilot-instructions.md",
    "templates/cursor/rules/*.mdc",
    "scripts/bootstrap-project.sh",
    "scripts/render_agent_commands.py",
    "scripts/install_shared_skills.py",
    "scripts/claude_settings.py",
)

# Ścieżki kopiowane **tylko gdy plik u konsumenta jeszcze nie istnieje** (`if [[ ! -f …]]`
# w bootstrap-project.sh). Re-bootstrap ich NIE ruszy, żeby nie zdeptać lokalnych
# treści projektu — więc gdy zmienią się w kicie, trzeba je przenieść ręcznie.
# Rozdzielenie od listy wyżej jest po to, żeby status nie obiecywał nadpisania,
# którego bootstrap nie zrobi.
_MANUAL_GLOBS: tuple[str, ...] = (
    "templates/AGENTS.md",
    "templates/project.md",
    "templates/project.profile.yaml",
    "templates/cursor/BUGBOT.md",
    "templates/git-hooks/pre-push",
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


# Ile czekamy na jedno wywolanie gita. Repo na dysku sieciowym albo zimny cache
# systemu plikow potrafia przekroczyc sekunde, wiec prog jest z zapasem — to i tak
# tylko zabezpieczenie przed zawieszeniem, nie budzet wydajnosciowy.
_GIT_TIMEOUT_SECONDS = 20

# Ostatni powod, dla ktorego `_git` zwrocil None. Bez tego kazda awaria — brak gita
# w PATH, timeout, katalog bez `.git`, odmowa "dubious ownership" — konczyla sie tym
# samym komunikatem "kit_root nie jest (juz) repo git", ktory dla trzech z tych
# czterech przyczyn jest po prostu nieprawdziwy i wysyla czytelnika w zla strone.
_last_git_error: str | None = None


def _git(kit_root: Path, *args: str) -> str | None:
    """
    Uruchom gita w ``kit_root`` i zwroc stdout albo ``None`` przy dowolnej awarii.

    Powod awarii laduje w ``_last_git_error`` — wywolujacy raportuje go uzytkownikowi,
    zamiast zgadywac, ze kazde ``None`` znaczy "to nie jest repo".

    Args:
        kit_root: Katalog repo kita (``git -C``).
        *args: Argumenty gita, np. ``("rev-parse", "HEAD")``.

    Returns:
        str | None: Przyciety stdout, albo ``None`` gdy git nie wystartowal,
            przekroczyl limit czasu albo zwrocil niezerowy kod.
    """
    global _last_git_error
    try:
        result = subprocess.run(
            ["git", "-C", str(kit_root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            # Bez tego dziecko dziedziczy stdin serwera MCP — potok od klienta, ktory
            # nigdy nie dostaje EOF. Git czeka wtedy na wejscie, ktore nie nadchodzi,
            # i kazde wywolanie konczy sie timeoutem zamiast odpowiedzia. Widac to
            # tylko pod serwerem (stdio transport); z terminala ten sam kod dziala.
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _last_git_error = "nie znaleziono `git` w PATH procesu serwera MCP"
        return None
    except OSError as exc:
        _last_git_error = f"nie udalo sie uruchomic gita: {exc}"
        return None
    except subprocess.TimeoutExpired:
        _last_git_error = f"git nie odpowiedzial w {_GIT_TIMEOUT_SECONDS}s"
        return None
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        detail = stderr[0][:200] if stderr else f"kod wyjscia {result.returncode}"
        _last_git_error = f"git zwrocil blad: {detail}"
        return None
    _last_git_error = None
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
            "bootstrapowany wersją kita ze stampem (albo plik usunięty).\n\n"
            "Załóż go narzędziem MCP `bootstrap_workspace` — najpierw bez argumentów "
            "(dry run pokaże listę plików), potem `dry_run=False` żeby zainstalować. "
            "Alternatywa bez MCP: lokalny klon kita i `bootstrap-project.sh`."
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
            "# Kit status: nie udało się odczytać commitu kita\n\n"
            f"- Ścieżka kita: `{kit_root}`\n"
            f"- Powód: {_last_git_error or 'nieznany'}\n\n"
            "Gdy ścieżka wskazuje katalog w cache `uv` (`…/uv/cache/…/guides/_data`), "
            "serwer czyta **kopię** kita z koła, a nie Twój klon — dodaj "
            "`--kit-root /sciezka/do/klona` do argumentów `guides-mcp`."
        )

    if current_commit == stamp_commit:
        return (
            "# Kit status: aktualny\n\n"
            f"- Bootstrapowano: {bootstrapped_at}\n"
            f"- Commit: `{stamp_commit[:12]}`\n"
            "- Nic nowego w kicie od ostatniego bootstrapu."
        )

    count = _git(kit_root, "rev-list", "--count", f"{stamp_commit}..{current_commit}")

    def changed(globs: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        for pattern in globs:
            out = _git(
                kit_root, "diff", "--name-only", f"{stamp_commit}..{current_commit}", "--", pattern
            )
            if out:
                found.extend(line for line in out.splitlines() if line)
        return sorted(set(found))

    overwritten = changed(_OVERWRITTEN_GLOBS)
    manual = changed(_MANUAL_GLOBS)

    lines = [
        "# Kit status: ZMIENIŁ SIĘ od ostatniego bootstrapu",
        "",
        f"- Bootstrapowano: {bootstrapped_at} (`{stamp_commit[:12]}`)",
        f"- Teraz: `{current_commit[:12]}`"
        + (f" ({count} commitów później)" if count else ""),
        "",
    ]
    if overwritten:
        lines.append("## Re-bootstrap wciągnie sam (pliki nadpisywane):")
        lines.append("")
        lines.extend(f"- `{f}`" for f in overwritten)
        lines.append("")
        lines.append(
            "Zaktualizuj narzędziem MCP `bootstrap_workspace` (dry run najpierw) albo "
            "ponownym `bootstrap-project.sh` z tymi samymi flagami co poprzednio. "
            "**Nadpisze** `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, "
            "`.codex/skills/`, `.github/prompts/`, `mcp.json` — jeśli je ręcznie "
            "edytowałeś, zrób `git diff` najpierw."
        )
    if manual:
        if overwritten:
            lines.append("")
        lines.append("## Wymagają ręcznego przeniesienia (bootstrap ich NIE nadpisze):")
        lines.append("")
        lines.extend(f"- `{f}`" for f in manual)
        lines.append("")
        lines.append(
            "Te pliki bootstrap kopiuje wyłącznie gdy u konsumenta jeszcze ich nie ma, "
            "żeby nie zdeptać lokalnej treści projektu. Skoro szablon w kicie się "
            "zmienił, a Twoja kopia już istnieje — porównaj ją z `templates/` i przenieś "
            "to, czego potrzebujesz."
        )
    if not overwritten and not manual:
        lines.append(
            "Kit ma nowe commity, ale żaden nie dotyka plików które bootstrap kopiuje "
            "do tego repo — re-bootstrap niepotrzebny. Moduły instrukcji "
            "(`modules/*.md`) i tak są czytane live, bez kopii."
        )

    return "\n".join(lines)
