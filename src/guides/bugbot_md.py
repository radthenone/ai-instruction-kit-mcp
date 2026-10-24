"""Render i migracja ``BUGBOT.md`` z zachowaniem bloku ``project:rules`` (#240).

Szablon kita odświeża się przy każdym ``kit-ai reload``, ale reguły projektu żyją
w chronionym bloku ``<!-- project:rules -->`` … ``<!-- /project:rules -->`` i przechodzą
przez reload bez zmian. Plik dostosowany przed wprowadzeniem bloku jest migrowany:
znajdujemy w historii ``templates/cursor/BUGBOT.md`` wersję najbliższą plikowi
(najmniejszy diff), a linie dopisane względem niej przenosimy do bloku. Gdy migracja
nie jest pewna (brak historii — np. instalacja z koła — albo za duży diff), plik
zostaje bez zmian, a reload wypisuje instrukcję ręcznego przeniesienia.

Moduł jest stdlib-only: bootstrap woła go przez ``scripts/bugbot_md.py``.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

BLOCK_OPEN = "<!-- project:rules -->"
BLOCK_CLOSE = "<!-- /project:rules -->"
TEMPLATE_REL_PATH = "templates/cursor/BUGBOT.md"

# Ile dopisanych linii uznajemy jeszcze za „własne reguły projektu”, a nie za
# przepisany szablon. Powyżej — migracja niepewna, plik zostaje bez zmian.
MAX_MIGRATED_LINES = 40
HISTORY_LIMIT = 50
_GIT_TIMEOUT_SECONDS = 20

# Zestawy Tierów, dla których renderujemy szablon przy porównaniach. Szablon kita
# ma dziś dokładnie `backend` i `client`; nadmiarowy zestaw nic nie psuje.
TIER_SETS: tuple[frozenset[str], ...] = (
    frozenset(),
    frozenset({"backend"}),
    frozenset({"client"}),
    frozenset({"backend", "client"}),
)

_BLOCK_RE = re.compile(re.escape(BLOCK_OPEN) + r"(.*?)" + re.escape(BLOCK_CLOSE), re.DOTALL)
_TIER_RE = re.compile(r"<!-- tier:(\w+) -->\n(.*?)<!-- /tier:\1 -->\n?", re.DOTALL)
# Blok podmieniamy po redukcji pustych linii, żeby nie zjadać pustych linii
# wewnątrz reguł użytkownika (migracja ma zachować treść dosłownie).
_SENTINEL = "\x00project:rules\x00"


@dataclass(frozen=True)
class Migration:
    """Wynik migracji dostosowanego pliku.

    Attributes:
        text: Nowa treść pliku albo ``None``, gdy migracja jest niepewna.
        moved: Linie przeniesione do bloku ``project:rules``.
        reason: Powód niepewności (tylko gdy ``text is None``).
    """

    text: str | None
    moved: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True)
class SyncResult:
    """Co ``sync_file`` zrobił z plikiem.

    Attributes:
        action: ``created`` | ``refreshed`` | ``unchanged`` | ``migrated`` | ``uncertain``.
        message: Komunikat do wypisania w wyniku reloadu (pusty = cisza).
        moved: Linie przeniesione do bloku przy migracji.
    """

    action: str
    message: str = ""
    moved: list[str] = field(default_factory=list)


def extract_rules(text: str) -> str | None:
    """
    Wyciągnij surową treść bloku ``project:rules``.

    Args:
        text: Treść pliku ``BUGBOT.md``.

    Returns:
        str | None: Wszystko między znacznikami (bajt w bajt) albo ``None``, gdy
            plik nie ma bloku.
    """
    match = _BLOCK_RE.search(text)
    return match.group(1) if match else None


def render(template: str, tiers: str | Iterable[str], rules: str | None = None) -> str:
    """
    Wyrenderuj szablon: wybrane sekcje Tierów + blok reguł projektu.

    Args:
        template: Treść szablonu ``templates/cursor/BUGBOT.md``.
        tiers: Tiery projektu, np. ``"backend"`` albo ``{"backend", "client"}``.
        rules: Treść bloku ``project:rules``; ``None`` zostawia instrukcję z szablonu.

    Returns:
        str: Gotowa treść pliku (LF).
    """
    chosen = set(tiers.split()) if isinstance(tiers, str) else set(tiers)
    default_rules = extract_rules(template)
    block_rules = default_rules if rules is None else rules

    text = template
    if default_rules is not None:
        text = _BLOCK_RE.sub(lambda _: BLOCK_OPEN + _SENTINEL + BLOCK_CLOSE, text)

    def keep(match: re.Match[str]) -> str:
        return match.group(2).strip("\n") + "\n" if match.group(1) in chosen else ""

    text = _TIER_RE.sub(keep, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if default_rules is not None:
        text = text.replace(_SENTINEL, block_rules or "")
    return text


def is_pristine(text: str, template: str) -> bool:
    """
    Czy plik to nietknięty render szablonu (dowolny zestaw Tierów)?

    Blok ``project:rules`` bez własnych reguł — pusty albo z samą instrukcją
    z szablonu — liczy się jak nietknięty, więc ``--remove`` może taki plik usunąć.

    Args:
        text: Treść pliku w repo aplikacji.
        template: Aktualny szablon kita.

    Returns:
        bool: ``True`` gdy plik można bezpiecznie nadpisać/usunąć.
    """
    default_rules = extract_rules(template)
    current_rules = extract_rules(text)
    normalized = text
    if (
        default_rules is not None
        and current_rules is not None
        and current_rules.strip() in ("", default_rules.strip())
    ):
        normalized = _BLOCK_RE.sub(
            lambda _: BLOCK_OPEN + default_rules + BLOCK_CLOSE, text, count=1
        )
    return any(normalized == render(template, tiers) for tiers in TIER_SETS)


def _diff(candidate: str, dest: str) -> tuple[int, int, list[str]]:
    """Policz diff linii: ``(zmienione, usunięte, dopisane)``."""
    candidate_lines = candidate.splitlines()
    dest_lines = dest.splitlines()
    matcher = difflib.SequenceMatcher(None, candidate_lines, dest_lines, autojunk=False)
    added: list[str] = []
    deleted = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added.extend(dest_lines[j1:j2])
        if tag in ("delete", "replace"):
            deleted += i2 - i1
    return deleted + len(added), deleted, added


def migrate(
    dest: str,
    template: str,
    tiers: str | Iterable[str],
    history: Sequence[str],
) -> Migration:
    """
    Zmigruj plik bez bloku: dopisane linie → ``project:rules``, reszta z szablonu.

    Args:
        dest: Dostosowany plik bez bloku ``project:rules``.
        template: Aktualny szablon kita.
        tiers: Tiery projektu.
        history: Treści historycznych wersji szablonu, od najnowszej.

    Returns:
        Migration: Nowa treść albo powód, dla którego migracja jest niepewna.
    """
    best: tuple[tuple[int, int], int, list[str]] | None = None
    for index, version in enumerate(history):
        for tier_set in TIER_SETS:
            score, deleted, added = _diff(render(version, tier_set), dest)
            key = (score, index)
            if best is None or key < best[0]:
                best = (key, deleted, added)

    if best is None:
        return Migration(None, reason="brak historii szablonu w kicie")

    _, deleted, added = best
    if deleted:
        return Migration(None, reason="plik zmienia lub usuwa linie szablonu")
    if len(added) > MAX_MIGRATED_LINES:
        return Migration(
            None,
            reason=f"diff za duży ({len(added)} dopisanych linii, limit {MAX_MIGRATED_LINES})",
        )

    # Puste linie na brzegach to zwykle odstęp przed dopisanymi regułami, nie reguła.
    while added and not added[0].strip():
        added.pop(0)
    while added and not added[-1].strip():
        added.pop()
    if not added:
        return Migration(render(template, tiers), moved=[])

    rules = "\n" + "\n".join(added) + "\n"
    return Migration(render(template, tiers, rules), moved=added)


def needs_migration(text: str, template: str) -> bool:
    """
    Czy plik wymaga migracji (jest dostosowany i nie ma jeszcze bloku)?

    Args:
        text: Treść pliku w repo aplikacji.
        template: Aktualny szablon kita.

    Returns:
        bool: ``True`` gdy trzeba dopasować plik do historii szablonu.
    """
    return extract_rules(text) is None and not is_pristine(text, template)


def _migration_message(moved: Sequence[str]) -> str:
    lines = [f"  ~ BUGBOT.md: reguły projektu przeniesione do bloku project:rules ({len(moved)}):"]
    lines.extend(f"    {line}" for line in moved)
    return "\n".join(lines)


def _uncertain_message(reason: str) -> str:
    return "\n".join(
        [
            f"  ! BUGBOT.md: nie przeniosłem reguł projektu do bloku project:rules ({reason}).",
            "    Plik bez zmian — przenieś własne reguły ręcznie między",
            f"    {BLOCK_OPEN} i {BLOCK_CLOSE}, potem uruchom reload ponownie.",
        ]
    )


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def sync_file(
    dest: Path,
    source: Path,
    tiers: str | Iterable[str] = "",
    history: Sequence[str] = (),
) -> SyncResult:
    """
    Doprowadź plik ``BUGBOT.md`` do stanu zgodnego z szablonem i blokiem projektu.

    Args:
        dest: Plik w repo aplikacji (może nie istnieć).
        source: Szablon kita.
        tiers: Tiery z Profilu.
        history: Historyczne wersje szablonu (od najnowszej) do migracji.

    Returns:
        SyncResult: Akcja, komunikat dla reloadu i lista przeniesionych linii.
    """
    template = source.read_text(encoding="utf-8")
    if not dest.is_file():
        _write(dest, render(template, tiers))
        return SyncResult("created")

    text = dest.read_text(encoding="utf-8")
    rules = extract_rules(text)
    if rules is not None:
        fresh = render(template, tiers, rules)
        if fresh != text:
            _write(dest, fresh)
            return SyncResult("refreshed")
        return SyncResult("unchanged")

    if is_pristine(text, template):
        fresh = render(template, tiers)
        if fresh != text:
            _write(dest, fresh)
            return SyncResult("refreshed")
        return SyncResult("unchanged")

    migration = migrate(text, template, tiers, history)
    if migration.text is None:
        return SyncResult("uncertain", message=_uncertain_message(migration.reason or "nieznany powód"))
    _write(dest, migration.text)
    return SyncResult("migrated", message=_migration_message(migration.moved), moved=migration.moved)


def _git(kit_root: Path, *args: str) -> str | None:
    """Uruchom gita w ``kit_root``; ``None`` przy braku gita/repo/błędu."""
    try:
        result = subprocess.run(
            ["git", "-C", str(kit_root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            # Serwer MCP nie przekazuje stdin — inaczej git czeka na wejście, które nie przyjdzie.
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def read_template_history(kit_root: Path, rel_path: str = TEMPLATE_REL_PATH) -> list[str]:
    """
    Wczytaj historyczne wersje szablonu BUGBOT.md z gita kita.

    Instalacja z koła (``guides/_data``) nie ma ``.git`` — wtedy zwracamy pustą
    listę, a migracja kończy się ostrzeżeniem zamiast zgadywania.

    Args:
        kit_root: Root kita (z ``templates/`` i ewentualnym ``.git``).
        rel_path: Ścieżka szablonu względem root kita.

    Returns:
        list[str]: Treści od najnowszej, bez duplikatów.
    """
    commits = _git(kit_root, "log", f"--max-count={HISTORY_LIMIT}", "--format=%H", "--", rel_path)
    if not commits:
        return []
    versions: list[str] = []
    for sha in commits.splitlines():
        sha = sha.strip()
        if not sha:
            continue
        content = _git(kit_root, "show", f"{sha}:{rel_path}")
        if content is not None and content not in versions:
            versions.append(content)
    return versions


def main() -> int:
    """
    Wejście z bootstrapu: ``SRC``, ``DEST``, ``TIERS``, ``KIT_ROOT``, ``CHECK_ONLY``.

    Returns:
        int: Kod wyjścia (``CHECK_ONLY=1``: 0 = plik nietknięty, 1 = dostosowany).
    """
    source = Path(os.environ["SRC"])
    dest = Path(os.environ["DEST"])
    tiers = os.environ.get("TIERS", "")

    if os.environ.get("CHECK_ONLY"):
        if not dest.is_file():
            return 1
        return 0 if is_pristine(dest.read_text(encoding="utf-8"), source.read_text(encoding="utf-8")) else 1

    kit_root = Path(os.environ.get("KIT_ROOT") or source.parents[2])
    # Historię czytamy tylko przy migracji — nietknięty plik albo plik z blokiem
    # nie potrzebuje kilkudziesięciu wywołań gita przy każdym reloadzie.
    history: Sequence[str] = ()
    if dest.is_file() and needs_migration(
        dest.read_text(encoding="utf-8"), source.read_text(encoding="utf-8")
    ):
        history = read_template_history(kit_root)
    result = sync_file(dest, source, tiers, history)
    if result.message:
        print(result.message)
    return 0
