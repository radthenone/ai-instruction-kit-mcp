"""Render i migracja ``BUGBOT.md`` i ``AGENTS.md`` z zachowaniem bloku projektu (#240, #269).

Szablon kita odświeża się przy każdym ``kit-ai reload``, ale reguły projektu żyją
w chronionym bloku ``<!-- project:rules -->`` … ``<!-- /project:rules -->`` i przechodzą
przez reload bez zmian. Plik dostosowany przed wprowadzeniem bloku jest migrowany:
znajdujemy w historii ``templates/cursor/BUGBOT.md`` wersję najbliższą plikowi
(najmniejszy diff), a linie dopisane względem niej przenosimy do bloku. Gdy migracja
nie jest pewna (brak historii — np. instalacja z koła — albo za duży diff), plik
zostaje bez zmian, a reload wypisuje jedną linię z trybem naprawy (#266).

``AGENTS.md`` idzie tym samym modelem z blokiem ``project:agents`` (``block="agents"``,
#269); jego sekcja ``## Agent skills`` (kontrakt Matta) to treść kita spoza szablonu —
na czas porównania odkładamy ją na bok i dokładamy z powrotem na końcu.

Moduł jest stdlib-only: bootstrap woła go przez ``scripts/bugbot_md.py``.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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

# Sekcje kita spoza szablonu, które sync odkłada na bok (blok → nagłówek sekcji).
ASIDE_SECTIONS = {"agents": re.compile(r"(?m)^## Agent skills[ \t]*$")}

# Blok briefu projektu (#307): generowany z Profilu i overlayu przy każdym reloadzie.
# Nie jest blokiem projektu — użytkownik go nie edytuje, a `is_pristine` normalizuje
# jego treść tak samo jak treść szablonu.
BRIEF_OPEN = "<!-- kit:brief -->"
BRIEF_CLOSE = "<!-- /kit:brief -->"
_BRIEF_RE = re.compile(re.escape(BRIEF_OPEN) + r"(.*?)" + re.escape(BRIEF_CLOSE), re.DOTALL)


def _markers(block: str) -> tuple[str, str]:
    """Znaczniki bloku projektu, np. ``project:rules`` albo ``project:agents``."""
    return f"<!-- project:{block} -->", f"<!-- /project:{block} -->"


def _block_re(block: str) -> re.Pattern[str]:
    opener, closer = _markers(block)
    return re.compile(re.escape(opener) + r"(.*?)" + re.escape(closer), re.DOTALL)

_TIER_RE = re.compile(r"<!-- tier:(\w+) -->\n(.*?)<!-- /tier:\1 -->\n?", re.DOTALL)
# Ścieżka reguły z overlayu (#266): `{{path:klucz|domyślna}}` → wartość klucza
# z `## Ścieżki` w `.ai/project.md`, a bez klucza — domyślna. Domyślna `@inny/reszta`
# jest pochodna od klucza `inny` (#280).
PATH_PLACEHOLDER = re.compile(r"\{\{path:([\w-]+)\|([^}]*)\}\}")
_PATHS_HEADING = re.compile(r"^##\s+Ścieżki\s*$")
_PATH_BULLET = re.compile(r"^\s*[-*]\s+([A-Za-z0-9_.-]+)\s*:\s*(.+?)\s*$")
_PATH_CODE = re.compile(r"`([^`\n]+)`")
# Blok podmieniamy po redukcji pustych linii, żeby nie zjadać pustych linii
# wewnątrz reguł użytkownika (migracja ma zachować treść dosłownie).
_SENTINEL = "\x00project:rules\x00"
# Dowolna ścieżka z overlayu w miejscu `{{path:…}}` przy rozpoznawaniu renderu (#270).
_ANY_PATH = "\x00path\x00"
# Alias klucza `## Ścieżki` → klucz placeholdera (#270); jawny klucz wygrywa z aliasem.
PATH_KEY_ALIASES = {"codegen-output": "api-generated"}


@dataclass(frozen=True)
class Migration:
    """Wynik migracji dostosowanego pliku.

    Attributes:
        text: Nowa treść pliku albo ``None``, gdy migracja jest niepewna.
        moved: Linie przeniesione do bloku ``project:rules``.
        reason: Powód niepewności (tylko gdy ``text is None``).
        proposal: Propozycja treści bloku projektu przy niepewnej migracji (#277):
            linie dopisane i zmienione względem najbliższej wersji szablonu; pusta
            bez historii szablonu.
    """

    text: str | None
    moved: list[str] = field(default_factory=list)
    reason: str | None = None
    proposal: list[str] = field(default_factory=list)


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


def extract_rules(text: str, block: str = "rules") -> str | None:
    """
    Wyciągnij surową treść bloku ``project:<block>``.

    Args:
        text: Treść pliku ``BUGBOT.md`` / ``AGENTS.md``.
        block: Nazwa bloku (``rules`` dla ``BUGBOT.md``, ``agents`` dla ``AGENTS.md``).

    Returns:
        str | None: Wszystko między znacznikami (bajt w bajt) albo ``None``, gdy
            plik nie ma bloku.
    """
    match = _block_re(block).search(text)
    return match.group(1) if match else None


def extract_brief(text: str) -> str | None:
    """
    Wyciągnij treść generowanego bloku ``kit:brief`` z ``AGENTS.md`` (#307).

    Args:
        text: Treść ``AGENTS.md``.

    Returns:
        str | None: Treść między ``<!-- kit:brief -->`` a ``<!-- /kit:brief -->``
            albo ``None``, gdy plik nie ma bloku.
    """
    match = _BRIEF_RE.search(text)
    return match.group(1) if match else None


def _with_brief(text: str, brief: str | None) -> str:
    """Podmień treść bloku ``kit:brief`` (``None`` albo brak bloku = bez zmian)."""
    if brief is None or BRIEF_OPEN not in text or BRIEF_CLOSE not in text:
        return text
    replacement = f"{BRIEF_OPEN}\n{brief.strip()}\n{BRIEF_CLOSE}"
    return _BRIEF_RE.sub(lambda _: replacement, text, count=1)


def overlay_path_entries(text: str) -> list[tuple[int, str, str]]:
    """
    Wpisy sekcji ``## Ścieżki`` overlayu jako ``(linia, klucz, wartość)``.

    Jedyny parser tej sekcji — używają go render ``BUGBOT.md`` i doctor. Wartość
    to pierwszy inline-code w linii (``- backend: `backend/` ``), a bez backticków
    — tekst do myślnika/pauzy (``- backend: backend/ — opis``).

    Args:
        text: Treść ``.ai/project.md``.

    Returns:
        list[tuple[int, str, str]]: Numer linii (1-based), klucz małymi literami
            i surowa wartość.
    """
    entries: list[tuple[int, str, str]] = []
    in_section = False
    for number, line in enumerate(text.replace("\r\n", "\n").splitlines(), start=1):
        if line.startswith("## "):
            in_section = bool(_PATHS_HEADING.match(line))
            continue
        match = _PATH_BULLET.match(line) if in_section else None
        if match is None:
            continue
        rest = match.group(2)
        code = _PATH_CODE.search(rest)
        value = (code.group(1) if code else re.split(r"\s+[—–-]\s+", rest)[0]).strip()
        if value:
            entries.append((number, match.group(1).lower(), value))
    return entries


def overlay_paths(text: str) -> dict[str, str]:
    """
    Klucze sekcji ``## Ścieżki`` overlayu → wartość (pierwsze wystąpienie klucza).

    Args:
        text: Treść ``.ai/project.md``.

    Returns:
        dict[str, str]: Np. ``{"backend": "backend/src/"}`` (klucze małymi literami).
    """
    paths: dict[str, str] = {}
    for _, key, value in overlay_path_entries(text):
        paths.setdefault(key, value)
    for alias, key in PATH_KEY_ALIASES.items():
        if alias in paths:
            paths.setdefault(key, paths[alias])
    return paths


def resolve_path(
    key: str, default: str, paths: Mapping[str, str], defaults: Mapping[str, str]
) -> str:
    """
    Wartość ``{{path:klucz|domyślna}}``: klucz z overlayu, a bez niego domyślna.

    Domyślna ``@web/src/components/ui/`` jest pochodna (#280): ``@web`` to wartość
    klucza ``web`` (z overlayu albo jego domyślna z ``defaults``), reszta doklejana.
    """
    if value := paths.get(key):
        return value
    ref, slash, rest = default.partition("/")
    if not ref.startswith("@"):
        return default
    base = (paths.get(ref[1:]) or defaults.get(ref[1:], "")).rstrip("/")
    if not base:
        # Nieznany klucz — literalna domyślna zamiast ścieżki bezwzględnej `/reszta`.
        return default
    return base + slash + rest


def path_defaults(text: str) -> dict[str, str]:
    """Domyślne wartości kluczy ``{{path:…}}`` z treści szablonu."""
    return dict(PATH_PLACEHOLDER.findall(text))


def render_paths(
    text: str,
    paths: Mapping[str, str] | None = None,
    defaults: Mapping[str, str] | None = None,
) -> str:
    """
    Podstaw ``{{path:klucz|domyślna}}`` wartością z overlayu albo domyślną.

    ``defaults`` (domyślne całego szablonu) rozwiązuje pochodne ``@klucz/…`` przy
    renderze fragmentu; bez nich bierzemy domyślne z samego ``text``.
    """
    paths = paths or {}
    defaults = path_defaults(text) if defaults is None else defaults
    return PATH_PLACEHOLDER.sub(
        lambda m: resolve_path(m.group(1), m.group(2), paths, defaults), text
    )


def render(
    template: str,
    tiers: str | Iterable[str],
    rules: str | None = None,
    paths: Mapping[str, str] | None = None,
    block: str = "rules",
    brief: str | None = None,
) -> str:
    """
    Wyrenderuj szablon: wybrane sekcje Tierów + blok reguł projektu.

    Args:
        template: Treść szablonu ``templates/cursor/BUGBOT.md``.
        tiers: Tiery projektu, np. ``"backend"`` albo ``{"backend", "client"}``.
        rules: Treść bloku ``project:rules``; ``None`` zostawia instrukcję z szablonu.
        paths: Klucze ``## Ścieżki`` overlayu dla ``{{path:…}}`` (#266).
        block: Nazwa bloku projektu.
        brief: Treść generowanego bloku ``kit:brief`` (``AGENTS.md``, #307);
            ``None`` zostawia domyślną treść szablonu.

    Returns:
        str: Gotowa treść pliku (LF).
    """
    chosen = set(tiers.split()) if isinstance(tiers, str) else set(tiers)
    default_rules = extract_rules(template, block)
    block_rules = default_rules if rules is None else rules
    opener, closer = _markers(block)

    text = render_paths(template, paths)
    if default_rules is not None:
        text = _block_re(block).sub(lambda _: opener + _SENTINEL + closer, text)

    def keep(match: re.Match[str]) -> str:
        return match.group(2).strip("\n") + "\n" if match.group(1) in chosen else ""

    # Sekcja w sekcji (reguła Orvala: backend + klient, #270) — kolejne przejście
    # zdejmuje znaczniki wewnętrzne, które zewnętrzne dopasowanie zostawiło w treści.
    while (nested := _TIER_RE.sub(keep, text)) != text:
        text = nested
    text = re.sub(r"\n{3,}", "\n\n", text)
    if default_rules is not None:
        text = text.replace(_SENTINEL, block_rules or "")
    return _with_brief(text, brief)


def _render_pattern(template: str, tiers: frozenset[str], block: str) -> re.Pattern[str]:
    """Render szablonu jako regex: każde ``{{path:…}}`` to dowolna ścieżka bez spacji."""
    rendered = render(PATH_PLACEHOLDER.sub(_ANY_PATH, template), tiers, block=block)
    return re.compile(r"[^\s`]+".join(map(re.escape, rendered.split(_ANY_PATH))))


def is_pristine(text: str, template: str, block: str = "rules") -> bool:
    """
    Czy plik to nietknięty render szablonu (dowolny zestaw Tierów)?

    Blok ``project:rules`` bez własnych reguł — pusty albo z samą instrukcją
    z szablonu — liczy się jak nietknięty, więc ``--remove`` może taki plik usunąć.
    Ścieżki ``{{path:…}}`` mogą mieć dowolną wartość: render sprzed zmiany klucza
    w overlayu to nadal plik kita, nie edycja (#270).

    Args:
        text: Treść pliku w repo aplikacji.
        template: Aktualny szablon kita.
        block: Nazwa bloku projektu.

    Returns:
        bool: ``True`` gdy plik można bezpiecznie nadpisać/usunąć.
    """
    default_rules = extract_rules(template, block)
    current_rules = extract_rules(text, block)
    opener, closer = _markers(block)
    normalized = text
    if (
        default_rules is not None
        and current_rules is not None
        and current_rules.strip() in ("", default_rules.strip())
    ):
        normalized = _block_re(block).sub(
            lambda _: opener + default_rules + closer, text, count=1
        )
    default_brief = extract_brief(template)
    if default_brief is not None and extract_brief(normalized) is not None:
        normalized = _with_brief(normalized, default_brief)
    return any(
        _render_pattern(template, tiers, block).fullmatch(normalized) for tiers in TIER_SETS
    )


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
    paths: Mapping[str, str] | None = None,
    block: str = "rules",
    brief: str | None = None,
) -> Migration:
    """
    Zmigruj plik bez bloku: dopisane linie → ``project:rules``, reszta z szablonu.

    Args:
        dest: Dostosowany plik bez bloku ``project:rules``.
        template: Aktualny szablon kita.
        tiers: Tiery projektu.
        history: Treści historycznych wersji szablonu, od najnowszej.
        paths: Klucze ``## Ścieżki`` overlayu dla nowej treści.
        block: Nazwa bloku projektu.

    Returns:
        Migration: Nowa treść albo powód, dla którego migracja jest niepewna.
    """
    best: tuple[tuple[int, int], int, list[str]] | None = None
    for index, version in enumerate(history):
        for tier_set in TIER_SETS:
            score, deleted, added = _diff(render(version, tier_set, paths=paths), dest)
            key = (score, index)
            if best is None or key < best[0]:
                best = (key, deleted, added)

    if best is None:
        return Migration(None, reason="brak historii szablonu w kicie")

    _, deleted, raw_added = best
    # Puste linie na brzegach to zwykle odstęp przed dopisanymi regułami, nie reguła.
    added = list(raw_added)
    while added and not added[0].strip():
        added.pop(0)
    while added and not added[-1].strip():
        added.pop()
    # Niepewna migracja niesie propozycję bloku (#277): zmieniona linia szablonu idzie
    # jako linia projektu — oryginał wróci z szablonu przy reloadzie.
    if deleted:
        return Migration(
            None, reason="plik zmienia lub usuwa linie szablonu", proposal=added
        )
    if len(raw_added) > MAX_MIGRATED_LINES:
        return Migration(
            None,
            reason=f"diff za duży ({len(raw_added)} dopisanych linii, limit {MAX_MIGRATED_LINES})",
            proposal=added,
        )

    if not added:
        return Migration(render(template, tiers, paths=paths, block=block, brief=brief), moved=[])

    rules = "\n" + "\n".join(added) + "\n"
    return Migration(render(template, tiers, rules, paths, block, brief), moved=added)


def needs_migration(text: str, template: str, block: str = "rules") -> bool:
    """
    Czy plik wymaga migracji (jest dostosowany i nie ma jeszcze bloku)?

    Args:
        text: Treść pliku w repo aplikacji.
        template: Aktualny szablon kita.
        block: Nazwa bloku projektu.

    Returns:
        bool: ``True`` gdy trzeba dopasować plik do historii szablonu.
    """
    text, _ = _split_aside(text, block)
    return extract_rules(text, block) is None and not is_pristine(text, template, block)


def propose_migration(
    text: str,
    template: str,
    history: Sequence[str],
    paths: Mapping[str, str] | None = None,
    block: str = "rules",
) -> Migration:
    """
    Migracja pliku bez bloku liczona na potrzeby doctora (#277) — bez zapisu.

    Odkłada sekcję kita spoza szablonu (``## Agent skills``) tak jak ``sync_file``.

    Args:
        text: Treść pliku w repo aplikacji.
        template: Aktualny szablon kita.
        history: Historyczne wersje szablonu, od najnowszej.
        paths: Klucze ``## Ścieżki`` overlayu.
        block: Nazwa bloku projektu.

    Returns:
        Migration: Wynik ``migrate`` (przy niepewnej — ``reason`` i ``proposal``).
    """
    rest, _ = _split_aside(text.replace("\r\n", "\n"), block)
    return migrate(rest, template, (), history, paths, block)


def _line_count(count: int) -> str:
    """„1 linia”, „2 linie”, „5 linii” — komunikat ma czytać się po polsku."""
    if count == 1:
        return "1 linia"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return f"{count} linie"
    return f"{count} linii"


def _migration_message(moved: Sequence[str], label: str = "BUGBOT.md", block: str = "rules") -> str:
    lines = [
        f"  ~ {label}: reguły projektu przeniesione do bloku project:{block} "
        f"({_line_count(len(moved))}):"
    ]
    lines.extend(f"    {line}" for line in moved)
    return "\n".join(lines)


def _uncertain_message(reason: str, label: str = "BUGBOT.md", block: str = "rules") -> str:
    # Jedna linia z trybem naprawy (#266) — przeniesienie reguł robi tryb C, nie człowiek.
    return (
        f"  ! {label}: bez zmian, reguły projektu nie trafiły do bloku project:{block} "
        f'({reason}) → /kit-project-edit "napraw zgłoszenia doctora"'
    )


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _split_aside(text: str, block: str) -> tuple[str, str]:
    """Odłóż sekcję kita spoza szablonu (``## Agent skills``): ``(reszta, sekcja)``."""
    heading = ASIDE_SECTIONS.get(block)
    match = heading.search(text) if heading else None
    if match is None:
        return text, ""
    nxt = re.compile(r"(?m)^## ").search(text, match.end())
    end = nxt.start() if nxt else len(text)
    suffix = text[end:]
    rest = text[: match.start()].rstrip("\n") + "\n" + ("\n" + suffix if suffix else "")
    return rest, text[match.start() : end].strip("\n") + "\n"


def _with_aside(text: str, aside: str) -> str:
    """Dołóż odłożoną sekcję na koniec — tak, jak dopisuje ją ``matt_contract``."""
    return text.rstrip("\n") + "\n\n" + aside if aside else text


def sync_file(
    dest: Path,
    source: Path,
    tiers: str | Iterable[str] = "",
    history: Sequence[str] = (),
    label: str = "BUGBOT.md",
    paths: Mapping[str, str] | None = None,
    block: str = "rules",
    brief: str | None = None,
) -> SyncResult:
    """
    Doprowadź plik ``BUGBOT.md`` / ``AGENTS.md`` do stanu zgodnego z szablonem i blokiem.

    Args:
        dest: Plik w repo aplikacji (może nie istnieć).
        source: Szablon kita.
        tiers: Tiery z Profilu.
        history: Historyczne wersje szablonu (od najnowszej) do migracji.
        label: Ścieżka pliku w komunikatach reloadu (np. ``.cursor/BUGBOT.md``).
        paths: Klucze ``## Ścieżki`` overlayu dla ``{{path:…}}`` (#266).
        block: Nazwa bloku projektu (``rules`` / ``agents``).
        brief: Treść bloku ``kit:brief`` (#307); ``None`` zostawia domyślną szablonu.

    Returns:
        SyncResult: Akcja, komunikat dla reloadu i lista przeniesionych linii.
    """
    template = source.read_text(encoding="utf-8")
    if not dest.is_file():
        _write(dest, render(template, tiers, paths=paths, block=block, brief=brief))
        return SyncResult("created")

    # Surowe bajty: read_text tłumaczy CRLF po cichu, a plik ma skończyć z LF.
    raw = dest.read_bytes().decode("utf-8")
    text, aside = _split_aside(raw.replace("\r\n", "\n"), block)
    opener, closer = _markers(block)
    rules = extract_rules(text, block)
    if (opener in text or closer in text) and (
        rules is None or text.count(opener) != 1 or text.count(closer) != 1
    ):
        # Migracja wkleiłaby osierocony znacznik do nowego bloku (zagnieżdżenie).
        return SyncResult(
            "uncertain",
            message=_uncertain_message(f"niedomknięty blok project:{block}", label, block),
        )

    def refresh(fresh: str) -> SyncResult:
        fresh = _with_aside(fresh, aside)
        if fresh != raw:
            _write(dest, fresh)
            return SyncResult("refreshed")
        return SyncResult("unchanged")

    if rules is not None:
        return refresh(render(template, tiers, rules, paths, block, brief))
    if is_pristine(text, template, block):
        return refresh(render(template, tiers, paths=paths, block=block, brief=brief))

    migration = migrate(text, template, tiers, history, paths, block, brief)
    if migration.text is None:
        return SyncResult(
            "uncertain",
            message=_uncertain_message(migration.reason or "nieznany powód", label, block),
        )
    _write(dest, _with_aside(migration.text, aside))
    return SyncResult(
        "migrated",
        message=_migration_message(migration.moved, label, block),
        moved=migration.moved,
    )


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

    Instalacja z koła (``guides/_data``) nie ma ``.git`` — wtedy, podobnie jak gdy
    ``kit_root`` nie jest rootem repo, zwracamy pustą listę, a migracja kończy się ostrzeżeniem zamiast zgadywania.

    Args:
        kit_root: Root kita (z ``templates/`` i ewentualnym ``.git``).
        rel_path: Ścieżka szablonu względem root kita.

    Returns:
        list[str]: Treści od najnowszej, bez duplikatów.
    """
    # Koło może leżeć wewnątrz cudzego repo (np. venv w projekcie) — historia tamtego
    # repo nie jest historią szablonu kita.
    toplevel = _git(kit_root, "rev-parse", "--show-toplevel")
    if not toplevel or Path(toplevel.strip()).resolve() != kit_root.resolve():
        return []
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
    Wejście z bootstrapu: ``SRC``, ``DEST``, ``LABEL``, ``TIERS``, ``KIT_ROOT``, ``CHECK_ONLY``,
    ``OVERLAY`` (``.ai/project.md`` — ścieżki reguł, #266), ``BLOCK`` (``rules`` /
    ``agents``, #269).

    Returns:
        int: Kod wyjścia (``CHECK_ONLY=1``: 0 = plik nietknięty, 1 = dostosowany).
    """
    source = Path(os.environ["SRC"])
    dest = Path(os.environ["DEST"])
    tiers = os.environ.get("TIERS", "")
    block = os.environ.get("BLOCK") or "rules"
    overlay = Path(os.environ["OVERLAY"]) if os.environ.get("OVERLAY") else None
    paths = (
        overlay_paths(overlay.read_text(encoding="utf-8"))
        if overlay is not None and overlay.is_file()
        else {}
    )
    brief_path = Path(os.environ["BRIEF"]) if os.environ.get("BRIEF") else None
    brief = (
        brief_path.read_text(encoding="utf-8")
        if brief_path is not None and brief_path.is_file() and brief_path.stat().st_size
        else None
    )

    if os.environ.get("CHECK_ONLY"):
        if not dest.is_file():
            return 1
        text, _ = _split_aside(dest.read_text(encoding="utf-8"), block)
        pristine = is_pristine(text, source.read_text(encoding="utf-8"), block)
        return 0 if pristine else 1

    kit_root = Path(os.environ.get("KIT_ROOT") or source.parents[2])
    try:
        rel_path = source.resolve().relative_to(kit_root.resolve()).as_posix()
    except ValueError:
        rel_path = TEMPLATE_REL_PATH
    # Historię czytamy tylko przy migracji — nietknięty plik albo plik z blokiem
    # nie potrzebuje kilkudziesięciu wywołań gita przy każdym reloadzie.
    history: Sequence[str] = ()
    if dest.is_file() and needs_migration(
        dest.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"), block
    ):
        history = read_template_history(kit_root, rel_path)
    result = sync_file(
        dest,
        source,
        tiers,
        history,
        os.environ.get("LABEL") or dest.name,
        paths,
        block,
        brief,
    )
    if result.message:
        print(result.message)
    return 0
