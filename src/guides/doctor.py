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
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

from guides.clients import expand_clients, parse_clients

RULE_FILES: tuple[str, ...] = (
    "BUGBOT.md",
    ".ai/project.md",
    "AGENTS.md",
    "CODING_STANDARDS.md",
)
OVERLAY_FILE = ".ai/project.md"
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

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
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
    """

    severity: str
    file: str
    line: int | None
    message: str

    def render(self) -> str:
        """Linia raportu zaczynająca się od ``doctor:``."""
        where = f"{self.file}:{self.line}" if self.line else self.file
        label = "OSTRZEŻENIE" if self.severity == "warning" else "INFO"
        return f"doctor: {label} {where} — {self.message}"


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


def _exists(workspace: Path, value: str) -> bool:
    """Czy ścieżka istnieje; goła nazwa pliku może leżeć w podkatalogu."""
    if (workspace / value).exists():
        return True
    if "/" not in value:
        return next(workspace.glob(f"**/{value}"), None) is not None
    return False


def _command_names(workspace: Path, kit_root: Path | None, clients: str) -> set[str]:
    """Nazwy komend znanych w repo: instalacje klientów + szablony kita."""
    names: set[str] = set()
    for client in expand_clients(parse_clients(clients)):
        for pattern in COMMAND_SURFACES.get(client, ()):
            for path in workspace.glob(pattern):
                if not path.is_file():
                    continue
                if path.name == "SKILL.md":
                    names.add(path.parent.name)
                elif path.name.endswith(".prompt.md"):
                    names.add(path.name[: -len(".prompt.md")])
                else:
                    names.add(path.name[: -len(".md")] if path.name.endswith(".md") else path.stem)
    if kit_root is not None:
        # Szablon istnieje = komenda jest w kicie, nawet gdy Tier/klient nie jest
        # wybrany w tym repo. Doctor pilnuje rozjazdu dokumentacji z kitem, nie
        # tego, czy akurat włączono backend.
        for pattern in (
            "templates/shared/agents/*.md",
            "templates/shared/skills/*/SKILL.md",
            "templates/cursor/skills/*/SKILL.md",
            "templates/opencode/command/*.md",
        ):
            for path in kit_root.glob(pattern):
                if path.name == "SKILL.md":
                    names.add(path.parent.name)
                elif path.name.endswith(".md"):
                    names.add(path.name[: -len(".md")])
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
    clients: set[str],
    kit_root: Path | None,
) -> list[Finding]:
    """Ścieżki w backtickach, których nie ma w drzewie."""
    findings: list[Finding] = []
    for match in _INLINE_CODE.finditer(text):
        value = _normalise_path(match.group(1))
        if value is None:
            continue
        line = _line_of(text, match.start())
        if (rel, line, value) in reported:
            continue
        if _skip_path(value, clients=clients, kit_root=kit_root):
            continue
        if _exists(workspace, value):
            continue
        reported.add((rel, line, value))
        findings.append(Finding("warning", rel, line, f"ścieżka `{value}` nie istnieje"))
    return findings


def _skip_path(value: str, *, clients: set[str], kit_root: Path | None) -> bool:
    """
    Czy pominąć ścieżkę, bo nie należy do tego repo?

    AGENTS.md opisuje wszystkie warstwy naraz: ścieżki klientów spoza ``clients:``
    i pliki samego kita (``scripts/…``, ``manifest.yaml``) nie muszą tu istnieć.
    """
    client = CLIENT_DIRS.get(value.split("/", 1)[0])
    if client is not None and client not in clients:
        return True
    return kit_root is not None and (kit_root / value).exists()


def _command_findings(
    rel: str, text: str, available: set[str], clients_label: str
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
        if (line, name) in seen:
            continue
        seen.add((line, name))
        findings.append(
            Finding(
                "warning",
                rel,
                line,
                f"komenda `/{name}` nie ma agenta, komendy ani skilla "
                f"u klientów: {clients_label}",
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
) -> tuple[list[Finding], list[str]]:
    """Walidacja kluczy ``## Ścieżki`` + lista ścieżek do opisu pakietów."""
    findings: list[Finding] = []
    paths: list[str] = []
    for line, key, value in _overlay_paths(text):
        paths.append(value)
        reported.add((OVERLAY_FILE, line, value))
        if _exists(workspace, value):
            continue
        findings.append(
            Finding(
                "warning",
                OVERLAY_FILE,
                line,
                f"klucz `{key}:` wskazuje nieistniejącą ścieżkę `{value}`",
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
        if isinstance(workspaces, list):
            patterns.extend(str(item) for item in workspaces)
        elif isinstance(workspaces, dict):
            patterns.extend(str(item) for item in workspaces.get("packages") or [])

    pnpm = workspace / "pnpm-workspace.yaml"
    if pnpm.is_file():
        try:
            data = yaml.safe_load(_read(pnpm)) or {}
        except yaml.YAMLError:
            data = {}
        if isinstance(data, dict):
            patterns.extend(str(item) for item in data.get("packages") or [])

    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(_read(pyproject))
        except tomllib.TOMLDecodeError:
            data = {}
        members = data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members") or []
        patterns.extend(str(item) for item in members)

    return patterns


def _package_dirs(workspace: Path, patterns: list[str]) -> list[str]:
    """Katalogi pakietów rozwinięte z wzorców workspace'ów (bez negacji)."""
    found: list[str] = []
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern or pattern.startswith("!"):
            continue
        try:
            matches = workspace.glob(pattern)
        except (OSError, ValueError):
            continue
        for path in sorted(matches):
            if path.is_dir() and path != workspace:
                rel = path.relative_to(workspace).as_posix()
                if rel not in found:
                    found.append(rel)
    return found


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
        kit_root: Root kita (szablony agentów do sprawdzenia komend); ``None`` —
            tylko pliki repo aplikacji.
        clients: Wartość ``clients:`` z Profilu (``all`` albo lista po przecinku).

    Returns:
        DoctorReport: Ostrzeżenia i informacje w kolejności plików; pusty raport,
            gdy wszystko się zgadza. Funkcja nie rzuca wyjątków od I/O.
    """
    workspace = workspace.resolve()
    findings: list[Finding] = []
    reported: set[tuple[str, int, str]] = set()

    configured = set(expand_clients(parse_clients(clients)))
    clients_label = ", ".join(sorted(configured))

    overlay_text = ""
    overlay_paths: list[str] = []
    overlay = workspace / OVERLAY_FILE
    if overlay.is_file():
        overlay_text = _read(overlay)
        overlay_findings, overlay_paths = _overlay_findings(workspace, overlay_text, reported)
        findings.extend(overlay_findings)

    available = _command_names(workspace, kit_root, clients)
    for rel in RULE_FILES:
        path = workspace / rel
        if not path.is_file():
            continue
        text = _read(path)
        findings.extend(
            _path_findings(
                rel,
                text,
                workspace,
                reported,
                clients=configured,
                kit_root=kit_root,
            )
        )
        findings.extend(_command_findings(rel, text, available, clients_label))

    if kit_root is not None:
        templates = kit_root / AGENT_TEMPLATES
        if templates.is_dir():
            for path in sorted(templates.glob("*.md")):
                rel = path.relative_to(kit_root).as_posix()
                findings.extend(
                    _command_findings(rel, _read(path), available, clients_label)
                )

    findings.extend(_package_infos(workspace, overlay_text, overlay_paths))

    unique: list[Finding] = []
    seen: set[Finding] = set()
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            unique.append(finding)
    return DoctorReport(tuple(unique))
