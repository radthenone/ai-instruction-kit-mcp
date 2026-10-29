"""E2E kontrakt projektu: Profil → bootstrap → kanały klientów → MCP → hooki (#306).

Suita nie czyta modułów Pythona „na sucho”: dla każdego Profilu z macierzy uruchamia
prawdziwy ``scripts/bootstrap-project.sh`` na tymczasowym workspace, a potem startuje
prawdziwy serwer po stdio z argv wygenerowanego pliku MCP klienta. Dzięki temu jedna
wartość z Profilu musi dojechać każdym kanałem: konfiguracją klienta, narzędziami MCP,
plikami instrukcji i hookami kontekstu.

Brief projektu w ``AGENTS.md`` jest częścią #307. Dopóki resolver go nie renderuje,
testy briefu i wartości w hookach kończą się jawnym skipem z numerem issue — po jego
wdrożeniu włączą się same, bez zmiany tej suity.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from guides.bootstrap import find_bash, run_bootstrap
from guides.clients import KNOWN_CLIENTS

KIT_ROOT = Path(__file__).resolve().parents[1]
BRIEF_SENTINEL = "E2E-BRIEF-SENTINEL-306"
SERVER_NAME = "project-guides"
BRIEF_ISSUE = "#307 — brief projektu nie jest jeszcze wpisywany do AGENTS.md"

# Kanał konfiguracji MCP per klient: plik + ścieżka do wpisu serwera.
_JSON_MCP_CONFIGS: dict[str, tuple[str, tuple[str, ...]]] = {
    "claude": (".mcp.json", ("mcpServers",)),
    "cursor": (".cursor/mcp.json", ("mcpServers",)),
    "vscode": (".vscode/mcp.json", ("servers",)),
    "antigravity": (".agents/mcp_config.json", ("mcpServers",)),
    "kiro": (".kiro/settings/mcp.json", ("mcpServers",)),
    "kilo": (".kilocode/mcp.json", ("mcpServers",)),
}

# Hooki kontekstu instalowane per klient (guardy PreToolUse nie są tu przedmiotem testu).
_CONTEXT_HOOKS: dict[str, tuple[str, ...]] = {
    "claude": (".claude/hooks/language-reminder.mjs", ".claude/hooks/kit-doctor-reminder.mjs"),
    "codex": (".codex/hooks/kit-doctor-reminder.mjs",),
    "vscode": (".github/hooks/kit-doctor-reminder.mjs",),
}

_BACKEND_MARKERS = {"fastapi": "FastAPI", "django": "Django + DRF", "flask": "Flask"}
_WEB_MARKERS = {"react": "React — przegląd Stacku (web)", "angular": "Angular — przegląd Stacku (web)"}
_MOBILE_MARKERS = {"expo": "Expo Router"}


@dataclass(frozen=True)
class ProfileCase:
    """Jeden punkt macierzy Profili (język × Tiery × codegen)."""

    name: str
    language: str
    backend: str
    web: str
    mobile: str
    codegen: str
    overlay_base: str

    @property
    def clients(self) -> str:
        """Profil pokrywa wszystkich obsługiwanych klientów."""
        return "all"

    @property
    def effective_codegen(self) -> str:
        """Codegen jest ``none`` bez pary backend + klient (web/mobile) — ADR-0007."""
        if self.backend != "none" and (self.web != "none" or self.mobile != "none"):
            return self.codegen
        return "none"

    @property
    def sentinel(self) -> str:
        """Unikalny znacznik overlayu tego przypadku."""
        return f"{BRIEF_SENTINEL}-{self.name}"

    def profile_yaml(self) -> str:
        """Treść ``.ai/project.profile.yaml`` dla przypadku."""
        return (
            f"name: {self.name}\n"
            f"language: {self.language}\n"
            f"clients: {self.clients}\n"
            f"backend: {self.backend}\n"
            f"web: {self.web}\n"
            f"mobile: {self.mobile}\n"
            f"codegen: {self.codegen}\n"
        )

    def overlay_text(self) -> str:
        """Overlay projektu — ``base:`` plus znacznik wykrywający kanał plikowy."""
        return (
            f"# Overlay e2e — {self.name}\n\n"
            f"base: {self.overlay_base}\n\n"
            f"{self.sentinel}\n\n"
            "## Komendy\n\n- test: `make test`\n"
        )


MATRIX: tuple[ProfileCase, ...] = (
    ProfileCase("pl-core", "pl", "none", "none", "none", "none", "dev"),
    # Jawny `codegen: none` przy pełnej parze backend + web — nie tylko efekt braku pary.
    ProfileCase("pl-none-pair", "pl", "flask", "react", "none", "none", "dev"),
    ProfileCase("en-orval", "en", "fastapi", "react", "none", "orval", "main"),
    ProfileCase("pl-graphql", "pl", "django", "none", "expo", "graphql", "dev"),
    # Web bez backendu: codegen z Profilu jest ignorowany (efektywnie `none`).
    ProfileCase("en-web-only", "en", "none", "angular", "none", "orval", "main"),
)


@dataclass
class Workspace:
    """Zbootstrapowany workspace i odpowiedzi serwera MCP dla jednego Profilu."""

    case: ProfileCase
    root: Path
    tools: dict[str, str]


_WORKSPACES: dict[str, Workspace] = {}
_BRIEF: dict[str, bool] = {}
_TMP: tempfile.TemporaryDirectory[str] | None = None
_CONFIG_HOME: tempfile.TemporaryDirectory[str] | None = None
_ENV_PATCHER: Any = None


def _bootstrap(case: ProfileCase, root: Path) -> Path:
    """Zapisz Profil i overlay, potem wykonaj realny bootstrap (bez dry-runu)."""
    workspace = root / case.name
    (workspace / ".ai").mkdir(parents=True)
    (workspace / ".ai" / "project.profile.yaml").write_text(
        case.profile_yaml(), encoding="utf-8", newline="\n"
    )
    (workspace / ".ai" / "project.md").write_text(
        case.overlay_text(), encoding="utf-8", newline="\n"
    )
    run_bootstrap(
        kit_root=KIT_ROOT,
        target=workspace,
        clients=case.clients,
        language=case.language,
    )
    return workspace


_ENV_TOKEN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand(value: str, workspace: Path) -> str:
    """Rozwiń placeholdery zmiennych środowiskowych używane przez klientów."""
    mapping = {
        "CLAUDE_PROJECT_DIR": str(workspace),
        "workspaceFolder": str(workspace),
    }

    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return mapping.get(name) or os.environ.get(name) or default or ""

    return _ENV_TOKEN.sub(replace, value)


def _client_argv(workspace: Path, client: str) -> list[str]:
    """Odczytaj ``command`` + ``args`` serwera dokładnie tak, jak zrobi to klient."""
    if client == "codex":
        config = tomllib.loads((workspace / ".codex" / "config.toml").read_text(encoding="utf-8"))
        entry = config["mcp_servers"][SERVER_NAME]
        return [_expand(str(entry["command"]), workspace), *(_expand(str(a), workspace) for a in entry["args"])]
    if client == "opencode":
        config = json.loads((workspace / "opencode.json").read_text(encoding="utf-8"))
        command = config["mcp"][SERVER_NAME]["command"]
        if isinstance(command, str):
            return [_expand(command, workspace)]
        return [_expand(str(part), workspace) for part in command]

    rel, keys = _JSON_MCP_CONFIGS[client]
    data: object = json.loads((workspace / rel).read_text(encoding="utf-8"))
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            raise AssertionError(f"{rel}: brak sekcji {'.'.join(keys)}")
        data = data[key]
    if not isinstance(data, dict):
        raise AssertionError(f"{rel}: sekcja serwera nie jest obiektem")
    entry = data[SERVER_NAME]
    return [
        _expand(str(entry["command"]), workspace),
        *(_expand(str(arg), workspace) for arg in entry["args"]),
    ]


def _arg_value(argv: list[str], flag: str) -> str:
    """Wartość flagi z argv serwera."""
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError) as exc:  # pragma: no cover - diagnostyka asercji
        raise AssertionError(f"brak flagi {flag} w {argv}") from exc


def _tool_text(result: CallToolResult) -> str:
    """Pierwszy tekstowy blok odpowiedzi narzędzia MCP."""
    for item in result.content:
        if isinstance(item, TextContent):
            return item.text
    return ""


_TOOL_CALLS: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("language", "get_language", {}),
    ("overlay", "get_overlay", {}),
    ("codegen", "get_codegen", {}),
    ("clients", "get_clients", {}),
    ("index", "get_index", {}),
    ("architecture", "get_bundle", {"name": "architecture"}),
    ("backend", "get_bundle", {"name": "backend"}),
    ("frontend", "get_bundle", {"name": "frontend"}),
)


def _server_env(workspace: Path) -> dict[str, str]:
    """Środowisko procesu serwera — bez sieciowego sync zależności na VPS/CI."""
    return {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(workspace),
        "workspaceFolder": str(workspace),
        "UV_NO_SYNC": "1",
    }


async def _collect_tools(argv: list[str], workspace: Path) -> dict[str, str]:
    """Połącz się po stdio i pobierz odpowiedzi wszystkich narzędzi kontraktu."""
    params = StdioServerParameters(
        command=argv[0],
        args=argv[1:],
        env=_server_env(workspace),
        cwd=str(workspace),
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        try:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available = {tool.name for tool in (await session.list_tools()).tools}
                    missing = {tool for _, tool, _ in _TOOL_CALLS} - available
                    if missing:
                        raise AssertionError(f"serwer nie wystawił narzędzi: {sorted(missing)}")

                    texts: dict[str, str] = {}
                    for key, tool, arguments in _TOOL_CALLS:
                        texts[key] = _tool_text(await session.call_tool(tool, arguments))
                    return texts
        except BaseException:
            errlog.seek(0)
            sys.stderr.write(errlog.read())
            raise


def _read_tools(workspace: Path, client: str = "claude") -> dict[str, str]:
    """Uruchom serwer z konfiguracji klienta i zwróć odpowiedzi narzędzi."""
    argv = _client_argv(workspace, client)
    return asyncio.run(asyncio.wait_for(_collect_tools(argv, workspace), 180))


async def _ping_language(argv: list[str], workspace: Path) -> str:
    """Minimalny handshake: init + ``get_language`` — dowód, że argv klienta działa."""
    params = StdioServerParameters(
        command=argv[0],
        args=argv[1:],
        env=_server_env(workspace),
        cwd=str(workspace),
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        try:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return _tool_text(await session.call_tool("get_language", {}))
        except BaseException:
            errlog.seek(0)
            sys.stderr.write(errlog.read())
            raise


def _is_ci() -> bool:
    """Czy działamy na CI (ten sam kontrakt co ``tests/_shell.py``)."""
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


def _bash_available() -> bool:
    """Czy jest bash do uruchomienia bootstrapu (Windows: Git Bash)."""
    return shutil.which(find_bash()) is not None


def setUpModule() -> None:
    """Zbootstrapuj całą macierz Profili i pobierz kontrakt MCP raz na moduł."""
    global _TMP, _CONFIG_HOME, _ENV_PATCHER

    if not _bash_available():
        if _is_ci():
            raise RuntimeError("brak bash w CI — e2e bootstrapu musi się wykonać")
        raise unittest.SkipTest("brak bash / Git for Windows w PATH")

    _TMP = tempfile.TemporaryDirectory()
    # Globalny config opencode z maszyny nie może przeciekać do generowanych plików.
    _CONFIG_HOME = tempfile.TemporaryDirectory()
    _ENV_PATCHER = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": _CONFIG_HOME.name})
    _ENV_PATCHER.start()

    try:
        for case in MATRIX:
            workspace = _bootstrap(case, Path(_TMP.name))
            _WORKSPACES[case.name] = Workspace(case, workspace, _read_tools(workspace))
            _BRIEF[case.name] = _has_brief(_WORKSPACES[case.name])
    except Exception:
        _stop_fixture()
        raise


def tearDownModule() -> None:
    """Zwolnij workspace'y i przywróć środowisko procesu."""
    _stop_fixture()


def _stop_fixture() -> None:
    """Idempotentne sprzątanie fixture'a modułu."""
    global _TMP, _CONFIG_HOME, _ENV_PATCHER
    if _ENV_PATCHER is not None:
        _ENV_PATCHER.stop()
        _ENV_PATCHER = None
    if _CONFIG_HOME is not None:
        _CONFIG_HOME.cleanup()
        _CONFIG_HOME = None
    if _TMP is not None:
        _TMP.cleanup()
        _TMP = None
    _WORKSPACES.clear()
    _BRIEF.clear()


def _run_hook(script: Path, workspace: Path, payload: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Uruchom hook kontekstu tak, jak robi to klient: JSON na stdin, cwd projektu."""
    return subprocess.run(
        ["node", str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=workspace,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(workspace)},
        timeout=30,
        check=False,
    )


def _brief_lines(workspace: Path) -> list[str]:
    """Linie AGENTS.md spoza szablonu kita — czyli wygenerowany brief (jeśli jest)."""
    template = (KIT_ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    known = set(template.splitlines())
    return [
        line
        for line in (workspace / "AGENTS.md").read_text(encoding="utf-8").splitlines()
        if line.strip() and line not in known and "project:agents" not in line
    ]


def _has_brief(item: Workspace) -> bool:
    """Czy AGENTS.md tego workspace'u niesie brief z wartościami Profilu (zależy od #307)."""
    brief = "\n".join(_brief_lines(item.root))
    return bool(brief) and (
        item.case.sentinel in brief
        or (item.case.backend != "none" and item.case.backend in brief)
        or (item.case.effective_codegen != "none" and item.case.effective_codegen in brief)
    )


def _brief_available(item: Workspace | None = None) -> bool:
    """Brief w danym workspace (``item``) albo w którymkolwiek — liczone raz w ``setUpModule``."""
    if item is not None:
        return _BRIEF.get(item.case.name, False)
    return any(_BRIEF.values())


class TestGeneratedClientConfigs(unittest.TestCase):
    """Każdy klient dostaje ten sam serwer, Profil i workspace w swoim formacie configu."""

    def test_every_client_config_points_at_the_same_server(self) -> None:
        """Jeden serwer, jedna flaga języka/klientów, workspace = repo aplikacji."""
        for item in _WORKSPACES.values():
            expected = [
                "guides-mcp",
                "--language",
                item.case.language,
                "--clients",
                item.case.clients,
                "--kit-root",
                str(KIT_ROOT),
                "--workspace",
                str(item.root),
            ]
            for client in KNOWN_CLIENTS:
                with self.subTest(case=item.case.name, client=client):
                    argv = _client_argv(item.root, client)
                    self.assertEqual(argv[0], "uv", argv)
                    self.assertEqual(argv[1:3], ["run", "--project"], argv)
                    self.assertEqual(argv[3], str(KIT_ROOT), argv)
                    self.assertEqual(argv[4:], expected, argv)

    def test_server_starts_from_each_client_command_line(self) -> None:
        """Handshake + ``get_language`` z argv każdego klienta (nie tylko Claude)."""
        if not shutil.which("uv"):
            if _is_ci():
                self.fail("brak uv w CI — klienci muszą wystartować serwer")
            self.skipTest("brak uv w PATH")
        item = _WORKSPACES["pl-graphql"]
        for client in KNOWN_CLIENTS:
            with self.subTest(client=client):
                text = asyncio.run(asyncio.wait_for(_ping_language(_client_argv(item.root, client), item.root), 180))
                self.assertIn("# Language: `pl`", text)


class TestMcpToolsReflectProfile(unittest.TestCase):
    """Narzędzia MCP zwracają wartości z Profilu, a nie domyślne kita."""

    def test_language_and_module(self) -> None:
        """Język i moduł języka idą z Profilu."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                text = item.tools["language"]
                self.assertIn(f"# Language: `{item.case.language}`", text)
                self.assertIn(f"`core:language-{item.case.language}`", text)
                self.assertIn("Titles always English", text)

    def test_effective_codegen(self) -> None:
        """Codegen efektywny: z Profilu tylko przy parze backend + web/mobile (ADR-0007)."""
        suffixes = {"orval": "", "graphql": ":graphql", "none": ":none"}
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                codegen = item.case.effective_codegen
                self.assertIn(f"# Codegen: `{codegen}`", item.tools["codegen"])
                self.assertIn(
                    f"Moduł: `arch:api-contract{suffixes[codegen]}`",
                    item.tools["codegen"],
                )

    def test_clients_are_expanded_for_all(self) -> None:
        """``clients: all`` w Profilu rozwija się do pełnej listy znanych klientów."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                text = item.tools["clients"]
                self.assertIn(f"- Flag `--clients`: `{item.case.clients}`", text)
                for client in KNOWN_CLIENTS:
                    self.assertIn(f"`{client}`", text)

    def test_index_reports_tiers_overlay_and_workspace(self) -> None:
        """Indeks to lustro Profilu: Tiery, overlay, workspace i kit root."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                text = item.tools["index"]
                self.assertIn(
                    f"- Tiery: backend=`{item.case.backend}` web=`{item.case.web}` "
                    f"mobile=`{item.case.mobile}`",
                    text,
                )
                self.assertIn(f"- Workspace: `{item.root}`", text)
                self.assertIn(f"- Kit root: `{KIT_ROOT}`", text)

    def test_overlay_comes_from_workspace(self) -> None:
        """Overlay MCP to dokładnie `.ai/project.md` tego workspace'u."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                text = item.tools["overlay"]
                self.assertIn(item.case.sentinel, text)
                self.assertIn(f"base: {item.case.overlay_base}", text)

    def test_bundle_carries_tier_modules_and_overlay(self) -> None:
        """Bundle backend/frontend zawiera moduły wybranych Tierów, każdy — overlay."""
        for item in _WORKSPACES.values():
            case = item.case
            with self.subTest(case=case.name):
                self.assertIn(case.sentinel, item.tools["backend"])
                self.assertIn(case.sentinel, item.tools["architecture"])

                if case.backend == "none":
                    self.assertNotIn("— przegląd Stacku", item.tools["backend"])
                else:
                    self.assertIn(_BACKEND_MARKERS[case.backend], item.tools["backend"])

                frontend = item.tools["frontend"]
                for tier, markers in (("web", _WEB_MARKERS), ("mobile", _MOBILE_MARKERS)):
                    value = getattr(case, tier)
                    if value == "none":
                        continue
                    self.assertIn(markers[value], frontend, f"{tier}={value}")


class TestChannelConsistency(unittest.TestCase):
    """Ta sama wartość z Profilu w każdym kanale — rozjazd wywala test."""

    def test_language_is_consistent(self) -> None:
        """Profil = config klienta = MCP = hook języka; brief po #307."""
        for item in _WORKSPACES.values():
            case = item.case
            with self.subTest(case=case.name):
                profile = yaml.safe_load((item.root / ".ai" / "project.profile.yaml").read_text(encoding="utf-8"))
                self.assertEqual(profile["language"], case.language)
                self.assertEqual(_arg_value(_client_argv(item.root, "claude"), "--language"), case.language)
                self.assertIn(f"# Language: `{case.language}`", item.tools["language"])

                hook = item.root / ".claude" / "hooks" / "language-reminder.mjs"
                if case.language == "en":
                    self.assertFalse(hook.exists(), "hook języka nie może zostać przy en")
                else:
                    self.assertTrue(hook.is_file())
                    result = _run_hook(hook, item.root, {})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("jęz", result.stdout.lower())

                if _brief_available(item):
                    brief = "\n".join(_brief_lines(item.root))
                    self.assertRegex(brief, rf"(?<![a-z]){case.language}(?![a-z])")

    def test_codegen_is_consistent(self) -> None:
        """Profil → efektywny codegen w MCP; brief po #307."""
        for item in _WORKSPACES.values():
            case = item.case
            with self.subTest(case=case.name):
                profile = yaml.safe_load((item.root / ".ai" / "project.profile.yaml").read_text(encoding="utf-8"))
                self.assertEqual(profile["codegen"], case.codegen)
                self.assertIn(f"# Codegen: `{case.effective_codegen}`", item.tools["codegen"])
                if _brief_available(item):
                    self.assertIn(case.effective_codegen, "\n".join(_brief_lines(item.root)))

    def test_clients_are_consistent(self) -> None:
        """Profil → ``--clients`` w każdym configu → rozwinięta lista w MCP."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                for client in KNOWN_CLIENTS:
                    self.assertEqual(
                        _arg_value(_client_argv(item.root, client), "--clients"),
                        item.case.clients,
                    )
                for client in KNOWN_CLIENTS:
                    self.assertIn(f"`{client}`", item.tools["clients"])

    def test_overlay_is_consistent(self) -> None:
        """Overlay z `base:` trafia do MCP i do bundli, nie tylko leży na dysku."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                on_disk = (item.root / ".ai" / "project.md").read_text(encoding="utf-8")
                self.assertIn(f"base: {item.case.overlay_base}", on_disk)
                for key in ("overlay", "architecture", "backend"):
                    self.assertIn(item.case.sentinel, item.tools[key], key)

    def test_tiers_drive_installed_agents(self) -> None:
        """Tiery z Profilu decydują o agentach w kanale klienta (Claude)."""
        for item in _WORKSPACES.values():
            case = item.case
            with self.subTest(case=case.name):
                agents = item.root / ".claude" / "agents"
                self.assertEqual((agents / "review-backend.md").exists(), case.backend != "none")
                self.assertEqual(
                    (agents / "review-frontend.md").exists(),
                    case.web != "none" or case.mobile != "none",
                )


class TestInstructionChannels(unittest.TestCase):
    """Każdy klient ma punkt wejścia do tych samych wytycznych z ``AGENTS.md``."""

    _ENTRY_POINTS: dict[str, str] = {
        "claude": "CLAUDE.md",
        "cursor": ".cursor/rules/use-guides.mdc",
        "vscode": ".github/copilot-instructions.md",
        "kiro": ".kiro/steering/instruction-kit.md",
    }

    def test_every_client_has_a_path_to_agents_md(self) -> None:
        """``AGENTS.md`` jest wspólnym źródłem; klienci z własnym plikiem mają entry point."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                agents = item.root / "AGENTS.md"
                self.assertTrue(agents.is_file())
                self.assertIn("## Priorytet źródeł", agents.read_text(encoding="utf-8"))

                for client, rel in self._ENTRY_POINTS.items():
                    path = item.root / rel
                    self.assertTrue(path.is_file(), f"{client}: {rel}")
                    self.assertIn("AGENTS.md", path.read_text(encoding="utf-8"), f"{client}: {rel}")


class TestBriefDelivery(unittest.TestCase):
    """Brief projektu w AGENTS.md — aktywuje się po wdrożeniu #307."""

    def _require_brief(self, item: Workspace | None = None) -> None:
        """Pomiń z numerem issue, dopóki brief nie jest renderowany (całość albo dany workspace)."""
        if not _brief_available(item):
            self.skipTest(BRIEF_ISSUE)

    def test_agents_md_carries_profile_values(self) -> None:
        """Brief zawiera język, Tiery, codegen, klientów, overlay i regułę priorytetu."""
        self._require_brief()
        for item in _WORKSPACES.values():
            case = item.case
            with self.subTest(case=case.name):
                self._require_brief(item)
                brief = "\n".join(_brief_lines(item.root))
                self.assertRegex(brief, rf"(?<![a-z]){case.language}(?![a-z])")
                for tier in ("backend", "web", "mobile"):
                    value = getattr(case, tier)
                    if value != "none":
                        self.assertIn(value, brief, tier)
                self.assertIn(case.effective_codegen, brief)
                self.assertTrue(
                    "all" in brief or all(client in brief for client in KNOWN_CLIENTS),
                    "brief nie wymienia klientów",
                )
                self.assertTrue(case.sentinel in brief or "project.md" in brief, "brief bez overlayu")
                self.assertRegex(brief, r"(?i)priorytet")
                self.assertRegex(brief, r"(?i)(kit|wytyczne)")

    def test_claude_imports_agents_md(self) -> None:
        """Claude czyta brief przez import ``@AGENTS.md``, także w subagentach."""
        self._require_brief()
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                self.assertIn("@AGENTS.md", (item.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_language_hook_carries_profile_values(self) -> None:
        """Hook języka mówi konkretny język i bazę z Profilu, nie sam wskaźnik."""
        self._require_brief()
        for item in _WORKSPACES.values():
            if item.case.language == "en":
                continue
            with self.subTest(case=item.case.name):
                self._require_brief(item)
                result = _run_hook(
                    item.root / ".claude" / "hooks" / "language-reminder.mjs", item.root, {}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                output = result.stdout
                self.assertRegex(output, r"(?<![a-z])pl(?![a-z])|polsk")
                self.assertRegex(output, rf"(?<![\w/-]){re.escape(item.case.overlay_base)}(?![\w/-])")


class TestContextHooks(unittest.TestCase):
    """Zainstalowane hooki kontekstu wykonują się u klienta i mówią to, co trzeba."""

    def setUp(self) -> None:
        if not shutil.which("node"):
            if _is_ci():
                self.fail("brak node w CI — hooki kontekstu muszą się wykonać")
            self.skipTest("brak node w PATH")

    def test_expected_context_hooks_are_installed(self) -> None:
        """Claude ma hook języka (pl), Claude/Codex/VSCode hook doctora."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                for client, hooks in _CONTEXT_HOOKS.items():
                    for rel in hooks:
                        exists = (item.root / rel).is_file()
                        if rel.endswith("language-reminder.mjs"):
                            expected = item.case.language != "en"
                        else:
                            expected = True
                        self.assertEqual(exists, expected, rel)

                # Klienci bez hooków kontekstu nie dostają obcych plików.
                # Katalogi klientów są różne (.agents/, .kilocode/, .kiro/, .opencode/…) — szukaj w całym drzewie.
                known = {rel for hooks in _CONTEXT_HOOKS.values() for rel in hooks}
                stray = sorted(
                    rel
                    for path in item.root.rglob("*reminder*.mjs")
                    if (rel := path.relative_to(item.root).as_posix()) not in known
                )
                self.assertEqual(stray, [])

    def test_every_installed_context_hook_runs(self) -> None:
        """Każdy zainstalowany hook kończy się exit 0 dla wejścia klienta."""
        for item in _WORKSPACES.values():
            for client, hooks in _CONTEXT_HOOKS.items():
                for rel in hooks:
                    script = item.root / rel
                    if not script.is_file():
                        continue
                    with self.subTest(case=item.case.name, client=client, hook=rel):
                        result = _run_hook(script, item.root, {"cwd": str(item.root)})
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_language_hook_is_wired_in_settings_only_for_pl(self) -> None:
        """``settings.json`` Claude woła hook języka tylko przy language ≠ en."""
        for item in _WORKSPACES.values():
            with self.subTest(case=item.case.name):
                settings = json.loads(
                    (item.root / ".claude" / "settings.json").read_text(encoding="utf-8")
                )
                commands = json.dumps(settings.get("hooks", {}).get("UserPromptSubmit", []))
                self.assertEqual(
                    "language-reminder.mjs" in commands,
                    item.case.language != "en",
                )

    def test_doctor_reminder_speaks_when_doctor_batch_exists(self) -> None:
        """Hook doctora realnie czyta workspace i zwraca kontekst z trybem naprawy."""
        item = _WORKSPACES["en-orval"]
        (item.root / ".ai" / ".kit-doctor.json").write_text("{}\n", encoding="utf-8")
        self.addCleanup((item.root / ".ai" / ".kit-doctor.json").unlink)
        for client, hooks in _CONTEXT_HOOKS.items():
            script = item.root / hooks[-1]
            if not script.is_file():
                continue
            with self.subTest(client=client):
                result = _run_hook(script, item.root, {"cwd": str(item.root)})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("kit-project-edit", result.stdout)


@unittest.skipUnless(
    os.environ.get("KIT_E2E_LIVE_AGENT"),
    "smoke na żywym agencie: ustaw KIT_E2E_LIVE_AGENT=1 (ręcznie, nie w CI)",
)
class TestLiveAgentSmoke(unittest.TestCase):
    """Ręczny smoke: agent odpowiada z briefu, bez wywołań MCP (manual, nie CI)."""

    _COMMANDS: dict[str, list[str]] = {
        "claude": ["claude", "-p", "{prompt}"],
        "codex": ["codex", "exec", "{prompt}"],
        "opencode": ["opencode", "run", "{prompt}"],
    }

    def test_agent_answers_from_brief_without_mcp_calls(self) -> None:
        """Pytania o język, bazę i codegen — odpowiedź jest tylko w wytycznych."""
        if not _brief_available():
            self.skipTest(BRIEF_ISSUE)

        item = _WORKSPACES["pl-graphql"]
        requested = os.environ.get("KIT_E2E_LIVE_CLIENT", "").strip()
        clients = [requested] if requested else list(self._COMMANDS)
        client = next((c for c in clients if c in self._COMMANDS and shutil.which(c)), None)
        if client is None:
            self.skipTest("brak CLI żywego agenta (claude/codex/opencode) w PATH")

        prompt = (
            "Bez wywoływania jakichkolwiek narzędzi MCP odpowiedz jednym zdaniem: "
            "jaki jest język projektu (pl/en), baza brancha i codegen?"
        )
        template = os.environ.get("KIT_E2E_LIVE_AGENT_CMD")
        if template:
            argv = shlex.split(template.replace("{prompt}", prompt))
        else:
            argv = [part.replace("{prompt}", prompt) for part in self._COMMANDS[client]]

        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=item.root,
            timeout=300,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        answer = result.stdout.lower()
        self.assertRegex(answer, r"(?<![a-z])pl(?![a-z])|polsk")
        self.assertIn("dev", answer)
        self.assertIn("graphql", answer)


if __name__ == "__main__":
    unittest.main()
