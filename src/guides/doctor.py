"""Doctor — czy reguły projektu wskazują istniejące ścieżki i komendy (#242).

Reload kita odświeża pliki, ale nie sprawdza, czy proza reguł nie odwołuje się do
katalogów, plików i komend, których w repo już nie ma. Taki rozjazd nie boli przy
reloadzie — boli tygodnie później, gdy reguła review po cichu przestaje cokolwiek
łapać. Ten moduł czyta:

- ``BUGBOT.md``, ``.ai/project.md``, ``AGENTS.md``, ``CODING_STANDARDS.md`` —
  ścieżki w backtickach i komendy ``/nazwa``;
- ``templates/shared/agents/*.md`` kita — komendy, które agenci polecają;
- sekcję ``## Ścieżki`` overlayu — klucze Tierów i pozostałe wpisy;
- workspace'y Bun/npm, pnpm i uv — pakiety, których overlay nie opisuje.

Wynik nigdy nie blokuje reloadu: to lista ``doctor:`` i kod wyjścia 0.
Moduł jest stdlib + PyYAML, bez zależności od basha i bez zapisu na dysk.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from guides.bugbot_md import (
    PATH_PLACEHOLDER,
    read_template_history,
    render_paths,
)
from guides.bugbot_md import overlay_paths as overlay_path_keys
from guides.clients import expand_clients, parse_clients

RULE_FILES: tuple[str, ...] = (
    "BUGBOT.md",
    ".ai/project.md",
    "AGENTS.md",
    "CODING_STANDARDS.md",
)
OVERLAY_FILE = ".ai/project.md"

# Szablony kita, z których powstają pliki reguł. W repo aplikacji linie
# skopiowane z szablonu bez zmian pomijamy: to treść kita (np. komendy Tierów
# spoza Profilu), której użytkownik nie naprawi — doctor pilnuje jego reguł.
KIT_TEMPLATES: dict[str, str] = {
    "AGENTS.md": "templates/AGENTS.md",
    "BUGBOT.md": "templates/cursor/BUGBOT.md",
}
AGENT_TEMPLATES = "templates/shared/agents"

# Komendy z innych warstw (Matt, Superpowers, Cursor), których kit nie instaluje.
# Ich brak to brak warstwy zewnętrznej — nie rozjazd reguł projektu — więc doctor
# ich nie zgłasza. Komendy kita (`/review-*`, `/git-*`, …) muszą istnieć.
EXTERNAL_COMMANDS = frozenset(
    {
        "grill-me",
        "grill-with-docs",
        "tdd",
        "triage",
        "code-review",
        "compact",
        "goal",
        "loop",
        "schedule",
        "handoff",
        "design-sync",
        "batch",
    }
)

# Komendy, które kit dokumentuje jako alias innej komendy.
COMMAND_ALIASES: dict[str, str] = {"git-pr": "git-end"}

# Placeholdery w prozie (``/nazwa``), nie komendy.
PLACEHOLDER_COMMANDS = frozenset({"nazwa", "name", "command", "komenda"})

# Pliki zależności wymieniane w regułach jako alternatywy („gdy zmienia się
# ``package.json``, ``bun.lock``, …”). Brak jednego z nich nie jest rozjazdem —
# projekt używa innego menedżera, a reguła odpala na tym, który istnieje.
OPTIONAL_MANIFESTS = frozenset(
    {
        "package.json",
        "package-lock.json",
        "bun.lock",
        "bun.lockb",
        "pnpm-lock.yaml",
        "yarn.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "pyproject.toml",
        "uv.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "Gemfile",
        "Gemfile.lock",
        "composer.json",
        "composer.lock",
    }
)

# Segmenty ścieżek absolutnych, które wyglądają jak komenda (``/tmp``).
FILESYSTEM_ROOTS = frozenset(
    {
        "tmp",
        "dev",
        "etc",
        "usr",
        "var",
        "home",
        "mnt",
        "opt",
        "bin",
        "sbin",
        "root",
        "proc",
        "sys",
        "run",
        "media",
        "srv",
        "lib",
    }
)

# Pliki samego kita, które AGENTS.md repo aplikacji może wymieniać — w aplikacji
# ich nie ma i nie musi być. ``scripts/`` dzielone z aplikacją, więc tylko pliki
# istniejące w kicie.
KIT_ONLY_ROOTS = frozenset({"templates", "modules", "manifest.yaml"})

# Katalogi pomijane przy szukaniu gołej nazwy pliku: zależności i artefakty
# narzędzi (wolne, a plik z ``node_modules`` maskowałby brak w projekcie).
SEARCH_SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tox"}
)

# Katalogi konfiguracji klientów. Ścieżkę klienta spoza ``clients:`` pomijamy —
# AGENTS.md opisuje wszystkie warstwy, ale w repo istnieją tylko wybrane.
CLIENT_DIRS: dict[str, str] = {
    ".cursor": "cursor",
    ".claude": "claude",
    ".codex": "codex",
    ".vscode": "vscode",
    ".kiro": "kiro",
    ".kilocode": "kilo",
    ".opencode": "opencode",
    ".agents": "antigravity",
}

# Gdzie bootstrap kładzie agentów, komendy i skille u klienta. Nazwa komendy to
# nazwa pliku (bez ``.md`` / ``.prompt``) albo katalogu skilla.
COMMAND_SURFACES: dict[str, tuple[str, ...]] = {
    "cursor": (".cursor/agents/*.md", ".cursor/skills/*/SKILL.md"),
    "claude": (".claude/agents/*.md", ".claude/commands/*.md", ".claude/skills/*/SKILL.md"),
    "codex": (".codex/skills/*/SKILL.md",),
    "vscode": (".github/prompts/*.prompt.md",),
    "kiro": (".kiro/agents/*.md",),
    "kilo": (".kilocode/workflows/*.md",),
    "antigravity": (".agents/skills/*/SKILL.md",),
    "opencode": (".opencode/command/*.md",),
}

# Znane rozszerzenia plików (F3, #266): goła nazwa z kropką bez nich to zwykle
# atrybut albo wyrażenie (`request.user`), nie plik — liczy się tylko, gdy istnieje.
FILE_EXTENSIONS = frozenset(
    {
        "py", "pyi", "js", "jsx", "ts", "tsx", "mjs", "cjs", "mts", "cts", "vue",
        "svelte", "json", "jsonc", "yaml", "yml", "toml", "ini", "cfg", "conf", "env",
        "lock", "lockb", "md", "mdx", "mdc", "txt", "rst", "html", "css", "scss",
        "sass", "less", "sh", "bash", "ps1", "bat", "sql", "go", "rs", "java", "kt",
        "kts", "swift", "rb", "php", "cs", "c", "h", "cpp", "hpp", "dart", "xml",
        "gradle", "properties", "graphql", "gql", "prisma", "proto", "svg", "png",
        "jpg", "ipynb", "csv", "mod", "sum", "plist", "pem",
    }
)

# Moduły wbudowane Node — pierwszy segment specyfikatora importu (F2, #266).
NODE_BUILTINS = frozenset(
    {
        "assert", "buffer", "child_process", "crypto", "dns", "events", "fs", "http",
        "https", "net", "os", "path", "process", "readline", "stream", "timers",
        "url", "util", "worker_threads", "zlib",
    }
)

# Podkatalogi źródeł sprawdzane pod każdym rootem z `## Ścieżki` (F1, #266).
SOURCE_SUBDIRS = ("src", "app")

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# F4: overlay dokumentuje, czego w repo NIE ma. Liczy się tylko jednoznaczna fraza
# tuż przed backtickiem (ewentualnie z dopowiedzeniem zakończonym dwukropkiem:
# „Nie istnieje po stronie web:** `x/`”) albo tuż za nim — bez gołego no/not.
_NEGATION_PHRASE = (
    r"(?:brak|nie istniej\w*|nie ma|nie zakładaj|does not exist|doesn't exist|"
    r"don't assume)"
)
_NEGATION_BEFORE = re.compile(
    rf"\b{_NEGATION_PHRASE}(?:[^`.;:→\n]{{0,40}}:)?[\s*:]*$", re.IGNORECASE
)
_NEGATION_AFTER = re.compile(rf"^[\s*]*{_NEGATION_PHRASE}\b", re.IGNORECASE)
# Wcześniejsze pozycje tej samej listy (`a/`, `b/`, `c/`) — zaprzeczenie obejmuje całą listę.
_CODE_LIST_TAIL = re.compile(r"(?:`[^`\n]*`\s*,\s*)+$")
# F5: linia o trasach URL / prefiksach API — segmenty to nie ścieżki repo. Całe
# słowa (``router``, ``Endpointy`` to nie kontekst trasy); segment ``api/…`` pomijamy
# osobno, bez wycinania całej linii.
_URL_CONTEXT = re.compile(
    r"(?i:\bprefiks\w*|\bendpoints?\b|\broutes?\b|\burl\b)"
    r"|\b(?:GET|POST|PUT|PATCH|DELETE)\b"
)
# Komenda: `/nazwa` albo `/nazwa-z-myslnikami`. Odrzuca fragmenty ścieżek
# (`src/foo`, `/dev/null`), wildcardy (`/review-*`) i URL-e (`https://`).
_COMMAND = re.compile(
    r"(?<![\w/.\-*?<>])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![-\w/.*:]|\s*-->)"
)
_OVERLAY_SECTION = re.compile(r"^##\s+Ścieżki\s*$")
_BULLET = re.compile(r"^\s*[-*]\s+([A-Za-z0-9_.-]+)\s*:\s*(.+?)\s*$")
_FILE_NAME = re.compile(r"[^/\\]+\.[A-Za-z][A-Za-z0-9]{0,5}")
_DOMAIN = re.compile(
    r"[a-z0-9-]+(\.[a-z0-9-]+)*\.(com|org|net|io|dev|ai|pl|co|app)(/.*)?$"
)
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class Finding:
    """Jedno zgłoszenie doctora.

    Attributes:
        severity: ``warning`` (reguła wskazuje na coś, czego nie ma) albo ``info``.
        file: Ścieżka pliku względem repo aplikacji (albo kita dla szablonów agentów).
        line: Numer linii 1-based; ``None`` dla zgłoszeń o całym pliku.
        message: Co jest nie tak i co wskazuje.
        kind: Klasa zgłoszenia (``stale-path``, ``negated-path-exists``,
            ``missing-command``, ``undescribed-package``, ``invalid-clients``, …).
        suggestion: Proponowana poprawka (np. jedyny kandydat w drzewie) albo ``None``.
        value: Wartość z pliku, której dotyczy zgłoszenie (ścieżka) albo ``None``.
    """

    severity: str
    file: str
    line: int | None
    message: str
    kind: str
    suggestion: str | None = None
    value: str | None = None

    def render(self) -> str:
        """Linia raportu zaczynająca się od ``doctor:``."""
        where = f"{self.file}:{self.line}" if self.line else self.file
        label = "OSTRZEŻENIE" if self.severity == "warning" else "INFO"
        hint = f" (propozycja: `{self.suggestion}`)" if self.suggestion else ""
        return f"doctor: {label} {where} — {self.message}{hint}"


@dataclass(frozen=True)
class _Layout:
    """Struktura repo liczona raz na przebieg doctora (#266).

    Attributes:
        roots: Katalogi, względem których rozwiązujemy ścieżki (``## Ścieżki``,
            ich ``src/``/``app/`` i pakiety workspace'u).
        dependencies: Pierwsze segmenty specyfikatorów modułów (zależności JS + moduły Node).
        tree: Ścieżki względne repo bez katalogów narzędzi; katalogi z ``/`` na końcu.
    """

    roots: tuple[str, ...] = ()
    dependencies: frozenset[str] = frozenset()
    tree: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoctorReport:
    """Wynik przebiegu doctora — nigdy nie rzuca i nigdy nie blokuje reloadu."""

    findings: tuple[Finding, ...] = ()

    @property
    def warnings(self) -> tuple[Finding, ...]:
        """Zgłoszenia, które łamią regułę (nieistniejąca ścieżka albo komenda)."""
        return tuple(finding for finding in self.findings if finding.severity == "warning")

    @property
    def infos(self) -> tuple[Finding, ...]:
        """Informacje bez blokowania — np. nieopisany pakiet workspace'u."""
        return tuple(finding for finding in self.findings if finding.severity == "info")

    def render(self) -> str:
        """Raport jako linie ``doctor:`` (czysty przebieg też ma jedną linię)."""
        if not self.findings:
            return "doctor: brak zgłoszeń — ścieżki i komendy w regułach projektu istnieją."
        header = (
            f"doctor: {_plural(len(self.warnings), 'ostrzeżenie', 'ostrzeżenia', 'ostrzeżeń')}, "
            f"{_plural(len(self.infos), 'informacja', 'informacje', 'informacji')}"
        )
        return "\n".join([header, *(finding.render() for finding in self.findings)])

    def to_json(self) -> str:
        """Wynik maszynowy dla trybu C i MCP (#266) — bez parsowania linii ``doctor:``."""
        return json.dumps(
            {
                "warnings": len(self.warnings),
                "infos": len(self.infos),
                "findings": [asdict(finding) for finding in self.findings],
            },
            ensure_ascii=False,
            indent=2,
        )


def _plural(count: int, one: str, few: str, many: str) -> str:
    """Odmiana rzeczownika po liczbie (1 ostrzeżenie, 2 ostrzeżenia, 5 ostrzeżeń)."""
    if count == 1:
        return f"{count} {one}"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return f"{count} {few}"
    return f"{count} {many}"


def _read(path: Path) -> str:
    """Treść pliku jako UTF-8 z LF (brak pliku → pusty string)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def _line_of(text: str, offset: int) -> int:
    """Numer linii 1-based dla pozycji w tekście."""
    return text.count("\n", 0, offset) + 1


def _normalise_path(raw: str) -> str | None:
    """
    Zamień kandydata z backticków na ścieżkę względną repo.

    Args:
        raw: Treść inline-code (bez backticków).

    Returns:
        str | None: Ścieżka z ``/`` albo ``None``, gdy to nie jest ścieżka repo
            (glob, placeholder, URL, komenda, nazwa pola, fragment kodu).
    """
    value = raw.strip()
    if not value or any(ch.isspace() for ch in value):
        return None
    if value.startswith(("/", "~", "-")) or _DRIVE_PATH.match(value):
        return None
    if any(ch in value for ch in "*?[]{}<>$|;=,`"):
        return None
    if "://" in value or "@" in value:
        return None
    value = re.sub(r":\d+$", "", value)
    value = value.replace("\\", "/")
    if value.startswith(".") and "/" not in value:
        return None
    if not ("/" in value or _FILE_NAME.fullmatch(value)):
        return None
    if _DOMAIN.fullmatch(value):
        return None
    return value


def _tree(workspace: Path) -> tuple[str, ...]:
    """Ścieżki względne repo (katalogi z ``/``), bez zależności i artefaktów narzędzi."""
    entries: list[str] = []
    # os.walk ignoruje błędy odczytu katalogów (onerror=None) — brak uprawnień
    # do podkatalogu nie wywraca doctora.
    for root, dirs, files in os.walk(workspace):
        dirs[:] = sorted(name for name in dirs if name not in SEARCH_SKIP_DIRS)
        base = Path(root).relative_to(workspace).as_posix()
        prefix = "" if base == "." else f"{base}/"
        entries.extend(f"{prefix}{name}/" for name in dirs)
        entries.extend(f"{prefix}{name}" for name in sorted(files))
    return tuple(entries)


def _exists(workspace: Path, value: str, layout: _Layout) -> bool:
    """
    Czy ścieżka istnieje — od roota repo, a gdy nie, względem rootów Tierów (F1).

    Goła nazwa pliku albo katalogu (``server.py``, ``ui/``) może leżeć w dowolnym
    podkatalogu (F6) — overlay używa ich jako skrótu.
    """
    if (workspace / value).exists():
        return True
    name = value.rstrip("/")
    if "/" not in name:
        return any(entry.rstrip("/").rsplit("/", 1)[-1] == name for entry in layout.tree)
    return any((workspace / root / value).exists() for root in layout.roots)


def _suggest(value: str, layout: _Layout) -> str | None:
    """
    Jedyny kandydat w drzewie po najdłuższym pasującym ogonie ścieżki.

    ``frontend/web/components/ui/`` → ``frontend/web/src/components/ui/``, gdy
    ``components/ui/`` występuje w repo dokładnie raz. Kilku kandydatów → ``None``.
    """
    segments = value.rstrip("/").split("/")
    want_dir = value.endswith("/")
    for size in range(len(segments), 0, -1):
        tail = "/".join(segments[-size:])
        candidates = [
            entry
            for entry in layout.tree
            if (not want_dir or entry.endswith("/"))
            and (entry.rstrip("/") == tail or entry.rstrip("/").endswith(f"/{tail}"))
        ]
        if candidates:
            return candidates[0] if len(candidates) == 1 else None
    return None


def _is_module_specifier(value: str, layout: _Layout) -> bool:
    """F2: ``next/navigation``, ``fs/promises`` — import zależności, nie ścieżka repo."""
    head, _, rest = value.partition("/")
    last = value.rstrip("/").rsplit("/", 1)[-1]
    return bool(rest) and head in layout.dependencies and not _FILE_NAME.fullmatch(last)


def _has_known_extension(value: str) -> bool:
    """F3: czy goła nazwa ma rozszerzenie pliku (a nie np. atrybut ``.user``)."""
    return value.rsplit(".", 1)[-1].lower() in FILE_EXTENSIONS


def _command_name(path: Path) -> str:
    """Nazwa komendy z pliku agenta/komendy/skilla."""
    if path.name == "SKILL.md":
        return path.parent.name
    for suffix in (".prompt.md", ".md"):
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem


def _command_names(workspace: Path, clients: set[str], *, is_kit: bool) -> set[str]:
    """Nazwy komend u skonfigurowanych klientów (+ szablony, gdy to repo kita)."""
    patterns = [p for client in clients for p in COMMAND_SURFACES.get(client, ())]
    if is_kit:
        # W repo kita szablon = komenda kita, nawet gdy Tier/klient nie jest wybrany.
        patterns += [
            "templates/shared/agents/*.md",
            "templates/shared/skills/*/SKILL.md",
            "templates/cursor/skills/*/SKILL.md",
            "templates/opencode/command/*.md",
        ]
    names = {
        _command_name(path)
        for pattern in patterns
        for path in workspace.glob(pattern)
        if path.is_file()
    }
    for alias, target in COMMAND_ALIASES.items():
        if target in names:
            names.add(alias)
    return names


def _path_findings(
    rel: str,
    text: str,
    workspace: Path,
    reported: set[tuple[str, int, str]],
    *,
    skip_lines: set[int],
    clients: set[str],
    kit_root: Path | None,
    is_kit: bool,
    layout: _Layout,
) -> list[Finding]:
    """Ścieżki w backtickach, których nie ma w drzewie (bez klas F1–F6 z #266)."""
    findings: list[Finding] = []
    for match in _INLINE_CODE.finditer(text):
        value = _normalise_path(match.group(1))
        if value is None:
            continue
        line = _line_of(text, match.start())
        if line in skip_lines or (rel, line, value) in reported:
            continue
        if _skip_path(value, clients=clients, kit_root=kit_root, is_kit=is_kit):
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.start())
        line_text = text[line_start : None if line_end < 0 else line_end]
        # Prozę linii bez inline-code: `/api/` wewnątrz samej ścieżki to nie trasa.
        if _URL_CONTEXT.search(_INLINE_CODE.sub("", line_text)) or value.startswith("api/"):
            continue
        exists = _exists(workspace, value, layout)
        before = _CODE_LIST_TAIL.sub("", text[line_start : match.start()])
        after = text[match.end() : None if line_end < 0 else line_end]
        if _NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after):
            # „Overlay twierdzi, że nie istnieje” — tylko overlay opisuje brak celowo.
            if exists and rel == OVERLAY_FILE:
                reported.add((rel, line, value))
                findings.append(
                    Finding(
                        "warning",
                        rel,
                        line,
                        f"overlay twierdzi, że `{value}` nie istnieje, a istnieje",
                        "negated-path-exists",
                        value=value,
                    )
                )
            continue
        if exists or _is_module_specifier(value, layout):
            continue
        if "/" not in value and not _has_known_extension(value):
            continue
        reported.add((rel, line, value))
        findings.append(
            Finding(
                "warning",
                rel,
                line,
                f"ścieżka `{value}` nie istnieje",
                "stale-path",
                _suggest(value, layout),
                value,
            )
        )
    return findings


def _skip_path(
    value: str, *, clients: set[str], kit_root: Path | None, is_kit: bool
) -> bool:
    """
    Czy pominąć ścieżkę, bo nie należy do tego repo?

    AGENTS.md opisuje wszystkie warstwy naraz: ścieżki klientów spoza ``clients:``
    i pliki samego kita (``scripts/…``, ``manifest.yaml``) nie muszą tu istnieć.
    Gołe nazwy plików zależności (``bun.lock``, ``requirements.txt``) są
    alternatywami, nie ścieżkami projektu.
    """
    if "/" not in value and value in OPTIONAL_MANIFESTS:
        return True
    client = CLIENT_DIRS.get(value.split("/", 1)[0])
    if client is not None and client not in clients:
        return True
    if is_kit or kit_root is None:
        return False
    # Repo aplikacji: pomijamy tylko pliki wyłącznie kitowe, nigdy wspólnych
    # nazw (`src/`, `README.md`) — ich brak w aplikacji to realny rozjazd.
    head = value.split("/", 1)[0]
    if head in KIT_ONLY_ROOTS:
        return True
    return head == "scripts" and value != "scripts/" and (kit_root / value).is_file()


def _kit_template_lines(
    rel: str, text: str, kit_root: Path | None, *, is_kit: bool, paths: dict[str, str]
) -> set[int]:
    """Numery linii pliku reguł skopiowanych bez zmian z szablonu kita (repo aplikacji).

    Szablon porównujemy po podstawieniu ``{{path:…}}`` ścieżkami overlayu — tak, jak
    wyrenderował go reload (#266).
    """
    template = KIT_TEMPLATES.get(rel)
    if is_kit or kit_root is None or template is None:
        return set()
    kit_lines = {
        line.strip() for line in render_paths(_read(kit_root / template), paths).splitlines()
    }
    kit_lines.discard("")
    return {
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() in kit_lines
    }


def _stale_kit_lines(
    rel: str, text: str, kit_root: Path | None, *, is_kit: bool
) -> set[int]:
    """
    Linie równe historycznej (nie aktualnej) wersji szablonu kita (#266, R2/R3).

    Plik zamrożony na starej wersji szablonu to przestarzała treść kita, a nie
    reguły użytkownika — historię czytamy z gita kita tylko, gdy plik ma linie
    spoza aktualnego szablonu.
    """
    template = KIT_TEMPLATES.get(rel)
    if is_kit or kit_root is None or template is None:
        return set()
    current = {line.strip() for line in _read(kit_root / template).splitlines()}
    own = {
        number: line.strip()
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and line.strip() not in current
    }
    if not own:
        return set()
    history = {
        line.strip()
        for version in read_template_history(kit_root, template)
        for line in version.splitlines()
    } - current
    return {number for number, line in own.items() if line in history}


def _path_key_findings(
    workspace: Path, kit_root: Path | None, paths: dict[str, str], layout: _Layout
) -> list[Finding]:
    """
    Klucze ``## Ścieżki``, bez których reguła szablonu ``BUGBOT.md`` celuje w pustkę.

    Brak klucza → reload renderuje wartość domyślną; zgłaszamy to tylko, gdy
    domyślnej ścieżki nie ma w repo (reguła po cichu nigdy nie odpala, #266).
    """
    bugbot = workspace / "BUGBOT.md"
    if kit_root is None or not bugbot.is_file():
        return []
    rendered = {line.strip() for line in _read(bugbot).splitlines()}
    findings: list[Finding] = []
    for line in _read(kit_root / KIT_TEMPLATES["BUGBOT.md"]).splitlines():
        for key, default in PATH_PLACEHOLDER.findall(line):
            if (
                key in paths
                or render_paths(line).strip() not in rendered
                or (workspace / default).exists()
            ):
                continue
            findings.append(
                Finding(
                    "warning",
                    OVERLAY_FILE,
                    None,
                    f"brak klucza `{key}:` w `## Ścieżki` — reguła `BUGBOT.md` używa "
                    f"domyślnej `{default}`, której nie ma w repo",
                    "missing-path-key",
                    _suggest(default, layout),
                    key,
                )
            )
    return findings


def _command_findings(
    rel: str,
    text: str,
    available: set[str],
    clients_label: str,
    skip_lines: frozenset[int] | set[int] = frozenset(),
) -> list[Finding]:
    """Komendy ``/nazwa``, których nie ma u żadnego skonfigurowanego klienta."""
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    for match in _COMMAND.finditer(text):
        name = match.group(1)
        if (
            name in EXTERNAL_COMMANDS
            or name in PLACEHOLDER_COMMANDS
            or name in FILESYSTEM_ROOTS
            or name in available
        ):
            continue
        line = _line_of(text, match.start())
        if line in skip_lines or (line, name) in seen:
            continue
        seen.add((line, name))
        findings.append(
            Finding(
                "warning",
                rel,
                line,
                f"komenda `/{name}` nie ma agenta, komendy ani skilla "
                f"u klientów: {clients_label}",
                "missing-command",
            )
        )
    return findings


def _overlay_paths(text: str) -> list[tuple[int, str, str]]:
    """
    Wpisy sekcji ``## Ścieżki`` overlayu jako ``(linia, klucz, ścieżka)``.

    Wartość bierzemy z pierwszego inline-code w linii (``- backend: `backend/` ``),
    a bez backticków — do myślnika/pauzy. Glob i placeholdery pomijamy.
    """
    entries: list[tuple[int, str, str]] = []
    in_section = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            in_section = bool(_OVERLAY_SECTION.match(line))
            continue
        if not in_section:
            continue
        bullet = _BULLET.match(line)
        if bullet is None:
            continue
        key, rest = bullet.group(1), bullet.group(2)
        code = _INLINE_CODE.search(rest)
        raw = code.group(1) if code else re.split(r"\s+[—–-]\s+", rest)[0]
        value = _normalise_path(raw)
        if value is not None:
            entries.append((number, key, value))
    return entries


def _overlay_findings(
    workspace: Path,
    text: str,
    reported: set[tuple[str, int, str]],
    tree: tuple[str, ...],
) -> tuple[list[Finding], list[str]]:
    """Walidacja kluczy ``## Ścieżki`` (katalog albo plik, F7) + lista ścieżek."""
    findings: list[Finding] = []
    paths: list[str] = []
    for line, key, value in _overlay_paths(text):
        paths.append(value)
        reported.add((OVERLAY_FILE, line, value))
        if (workspace / value).exists():
            continue
        findings.append(
            Finding(
                "warning",
                OVERLAY_FILE,
                line,
                f"klucz `{key}:` wskazuje nieistniejącą ścieżkę `{value}`",
                "stale-path",
                _suggest(value, _Layout(tree=tree)),
                value,
            )
        )
    return findings, paths


def _workspace_patterns(workspace: Path) -> list[str]:
    """Wzorce pakietów z ``package.json``, ``pnpm-workspace.yaml`` i uv."""
    patterns: list[str] = []

    package_json = workspace / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(_read(package_json))
        except json.JSONDecodeError:
            data = {}
        workspaces = data.get("workspaces") if isinstance(data, dict) else None
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages")
        patterns.extend(_str_list(workspaces))

    pnpm = workspace / "pnpm-workspace.yaml"
    if pnpm.is_file():
        try:
            data = yaml.safe_load(_read(pnpm)) or {}
        except yaml.YAMLError:
            data = {}
        if isinstance(data, dict):
            patterns.extend(_str_list(data.get("packages")))

    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(_read(pyproject))
        except tomllib.TOMLDecodeError:
            data = {}
        for key in ("tool", "uv", "workspace"):
            data = data.get(key) if isinstance(data, dict) else None
        patterns.extend(_str_list(data.get("members") if isinstance(data, dict) else None))

    return patterns


def _str_list(value: object) -> list[str]:
    """Lista stringów z pola konfiguracji; inny typ (string, dict, None) → pusta."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _package_dirs(workspace: Path, patterns: list[str]) -> list[str]:
    """Katalogi pakietów rozwinięte z wzorców workspace'ów (bez negacji)."""
    found: list[str] = []
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern or pattern.startswith(("!", "/", "\\")) or _DRIVE_PATH.match(pattern):
            continue
        try:
            matches = sorted(workspace.glob(pattern))
        except (OSError, ValueError, NotImplementedError):
            continue
        for path in matches:
            if path.is_dir() and path != workspace:
                rel = path.relative_to(workspace).as_posix()
                if rel not in found:
                    found.append(rel)
    return found


def _dependency_names(workspace: Path, dirs: list[str]) -> set[str]:
    """Nazwy zależności JS z ``package.json`` rootu i katalogów pakietów."""
    names: set[str] = set()
    for rel in ["", *dirs]:
        package_json = workspace / rel / "package.json"
        if package_json.is_file():
            try:
                data = json.loads(_read(package_json))
            except json.JSONDecodeError:
                data = {}
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                section = data.get(key) if isinstance(data, dict) else None
                if isinstance(section, dict):
                    names.update(name for name in section if isinstance(name, str))
    return names


def _layout(workspace: Path, overlay_paths: list[str], tree: tuple[str, ...]) -> _Layout:
    """Rooty Tierów, zależności i drzewo repo dla jednego przebiegu (#266)."""
    packages = _package_dirs(workspace, _workspace_patterns(workspace))
    roots: list[str] = []
    for value in [*overlay_paths, *packages]:
        base = value.rstrip("/")
        for rel in (base, *(f"{base}/{sub}" for sub in SOURCE_SUBDIRS)):
            if rel not in roots and (workspace / rel).is_dir():
                roots.append(rel)
    dependencies = _dependency_names(workspace, roots)
    # Bez stdlib i zależności Pythona: `util/`, `json/` to częściej katalogi projektu.
    dependencies |= NODE_BUILTINS
    return _Layout(tuple(roots), frozenset(dependencies), tree)


def _described(rel: str, overlay_text: str, overlay_paths: list[str]) -> bool:
    """Czy overlay opisuje katalog pakietu (ścieżką, przodkiem albo globem)."""
    normalized = overlay_text.replace("\\", "/")
    if re.search(rf"(?<![\w-]){re.escape(rel)}/?(?![\w-])", normalized):
        return True
    for value in overlay_paths:
        value = value.rstrip("/")
        if rel == value or rel.startswith(f"{value}/"):
            return True
    for token in _INLINE_CODE.findall(normalized):
        token = token.rstrip("/")
        if any(ch in token for ch in "*?[") and fnmatch.fnmatch(rel, token):
            return True
    return False


def _package_infos(
    workspace: Path,
    overlay_text: str,
    overlay_paths: list[str],
) -> list[Finding]:
    """Pakiety workspace'u, których overlay nie wymienia — informacja, nie ostrzeżenie."""
    findings: list[Finding] = []
    for rel in _package_dirs(workspace, _workspace_patterns(workspace)):
        if _described(rel, overlay_text, overlay_paths):
            continue
        findings.append(
            Finding(
                "info",
                OVERLAY_FILE,
                None,
                f"katalog `{rel}/` z workspace'u nie jest opisany w `.ai/project.md`",
                "undescribed-package",
            )
        )
    return findings


def run_doctor(
    workspace: Path,
    kit_root: Path | None = None,
    *,
    clients: str = "all",
) -> DoctorReport:
    """
    Sprawdź, czy reguły projektu nie wskazują nieistniejących ścieżek i komend.

    Args:
        workspace: Root repo aplikacji.
        kit_root: Root kita. Równy ``workspace`` = repo kita (sprawdza też komendy
            w szablonach agentów); inny — repo aplikacji (pomija tylko pliki
            wyłącznie kitowe); ``None`` — bez wiedzy o kicie.
        clients: Wartość ``clients:`` z Profilu (``all`` albo lista po przecinku).

    Returns:
        DoctorReport: Ostrzeżenia i informacje w kolejności plików; pusty raport,
            gdy wszystko się zgadza. Funkcja nie rzuca wyjątków od I/O.
    """
    workspace = workspace.resolve()
    findings: list[Finding] = []
    reported: set[tuple[str, int, str]] = set()
    is_kit = kit_root is not None and kit_root.resolve() == workspace

    try:
        configured = set(expand_clients(parse_clients(clients)))
    except ValueError:
        configured = set(expand_clients(parse_clients("all")))
        findings.append(
            Finding(
                "info",
                ".ai/project.profile.yaml",
                None,
                f"nieprawidłowe `clients: {clients}` — sprawdzam jak `all`",
                "invalid-clients",
            )
        )
    clients_label = ", ".join(sorted(configured))

    overlay_text = ""
    overlay_paths: list[str] = []
    tree = _tree(workspace)
    overlay = workspace / OVERLAY_FILE
    if overlay.is_file():
        overlay_text = _read(overlay)
        overlay_findings, overlay_paths = _overlay_findings(
            workspace, overlay_text, reported, tree
        )
        findings.extend(overlay_findings)
    layout = _layout(workspace, overlay_paths, tree)
    path_keys = overlay_path_keys(overlay_text)
    findings.extend(_path_key_findings(workspace, kit_root, path_keys, layout))

    available = _command_names(workspace, configured, is_kit=is_kit)
    for rel in RULE_FILES:
        path = workspace / rel
        if not path.is_file():
            continue
        text = _read(path)
        skip_lines = _kit_template_lines(rel, text, kit_root, is_kit=is_kit, paths=path_keys)
        stale = _stale_kit_lines(rel, text, kit_root, is_kit=is_kit)
        if stale:
            skip_lines |= stale
            findings.append(
                Finding(
                    "warning",
                    rel,
                    None,
                    f"{_plural(len(stale), 'linia', 'linie', 'linii')} ze starej wersji "
                    "szablonu kita — odśwież plik (`/kit-project-edit "
                    '"napraw zgłoszenia doctora"`)',
                    "stale-kit-content",
                )
            )
        findings.extend(
            _path_findings(
                rel,
                text,
                workspace,
                reported,
                skip_lines=skip_lines,
                clients=configured,
                kit_root=kit_root,
                is_kit=is_kit,
                layout=layout,
            )
        )
        findings.extend(_command_findings(rel, text, available, clients_label, skip_lines))

    if is_kit:
        templates = workspace / AGENT_TEMPLATES
        if templates.is_dir():
            for path in sorted(templates.glob("*.md")):
                rel = path.relative_to(workspace).as_posix()
                findings.extend(
                    _command_findings(rel, _read(path), available, clients_label)
                )

    findings.extend(_package_infos(workspace, overlay_text, overlay_paths))

    return DoctorReport(tuple(dict.fromkeys(findings)))
