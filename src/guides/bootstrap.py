"""Wykonanie ``scripts/bootstrap-project.sh`` z poziomu serwera MCP.

Skrypt bash zostaje **jedynym źródłem prawdy** o tym, co bootstrap gdzie kładzie.
Ten moduł trzyma też czyste funkcje scalania konfiguracji i doboru agentów
(wywoływane przez ``scripts/bootstrap-project.sh``), dzięki czemu można je
testować bezpośrednio w Pythonie bez uruchamiania podprocesu basha.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guides import __version__
from guides.kit_status import installed_kit_commit

SCRIPT_REL_PATH = "scripts/bootstrap-project.sh"

KIT_SERVER = "kit-ai-mcp"
LEGACY_KIT_SERVERS: tuple[str, ...] = ("project-guides",)

GITIGNORE_BEGIN = "# >>> instruction-kit >>>"
GITIGNORE_END = "# <<< instruction-kit <<<"

_TOML_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")
_TOML_KEY = re.compile(r'"(?:[^"\\]|\\.)*"|' + r"'[^']*'|[^.\s]+")
_CLIENT_BLOCK = re.compile(r"<!-- clients: ([\w ,-]+) -->\n(.*?)<!-- /clients -->\n?", re.DOTALL)
_JSON_STRING = r'("(?:\\.|[^"\\])*")'

# Powierzchnia repo aplikacji, którą bootstrap czyta lub zapisuje. Sandbox dry-runu
# dostaje kopię dokładnie tych ścieżek — dzięki temu „nie nadpisuj jeśli istnieje"
# (AGENTS.md, BUGBOT.md, .ai/project.md), scalanie `.claude/settings.json` i sprzątanie
# klientów spoza `--clients` zachowują się w planie tak jak zachowają się na żywo.
KIT_SURFACE: tuple[str, ...] = (
    ".agents",
    ".ai",
    ".claude",
    ".coderabbit.yaml",
    ".codex",
    ".cursor",
    ".github/copilot-instructions.md",
    ".github/hooks",
    ".github/prompts",
    ".kilocode",
    ".kiro",
    ".mcp.json",
    ".opencode",
    ".vscode",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "BUGBOT.md",
    "CLAUDE.md",
    "CODING_STANDARDS.md",
    # Tylko czytane: od nich zależy treść `CODING_STANDARDS.md` (#279).
    "CONTEXT.md",
    "CONTEXT-MAP.md",
    "docs/adr",
    "docs/agents/design-handoff.md",
    "docs/agents/domain.md",
    "docs/agents/issue-tracker.md",
    "docs/agents/triage-labels.md",
    "opencode.json",
    "orca.yaml",
    "skills-lock.json",
)

_TIMEOUT_SECONDS = 600

# Stamp dostaje świeży znacznik czasu przy każdym przebiegu; plik jest w .gitignore,
# więc sama zmiana czasu nie jest zmianą, którą plan ma raportować (#279).
_STAMP_REL = ".ai/.kit-bootstrap.json"
_STAMP_TIME = re.compile(rb'"bootstrapped_at": "[^"]*"')


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
    language: str = "pl",
    from_src: str | None = None,
    with_overlay: bool = False,
    skip_agents: bool = False,
    keep_unselected_clients: bool = False,
    remove: bool = False,
) -> list[str]:
    """
    Zbuduj listę argumentów wywołania ``bootstrap-project.sh``.

    Stacki i codegen nie są flagami — skrypt ich nie potrzebuje, serwer czyta je
    z profilu (ADR-0007).

    Args:
        kit_root: Root repozytorium instruction-kit (źródło szablonów).
        target: Repo aplikacji, do którego lądują pliki.
        clients: Wartość ``--clients`` (już zwalidowana przez ``guides.clients``).
        language: Język prozy instrukcji (``pl``/``en``).
        from_src: Wartość ``--from``; domyślnie lokalna ścieżka kita.
        with_overlay: Dołóż ``--with-overlay``.
        skip_agents: Dołóż ``--skip-agents``.
        keep_unselected_clients: Nie sprzątaj plików klientów spoza ``--clients``.
        remove: ``--remove`` — usuń pliki kita zamiast instalować.

    Returns:
        list[str]: Argv dla bash (bez samego interpretera).
    """
    script = _script_path(kit_root)
    args = [
        str(script).replace("\\", "/"),
        str(target).replace("\\", "/"),
        "--language",
        language,
        "--clients",
        clients,
        "--from",
        (from_src or str(kit_root)).replace("\\", "/"),
    ]
    if with_overlay:
        args.append("--with-overlay")
    if skip_agents:
        args.append("--skip-agents")
    if keep_unselected_clients:
        args.append("--keep-unselected-clients")
    if remove:
        args.append("--remove")
    return args


def run_bootstrap(**kwargs) -> str:
    """
    Uruchom bootstrap na wskazanym katalogu (**zapisuje na dysk**).

    Args:
        **kwargs: Jak w :func:`build_args` (``kit_root``, ``target``, flagi), plus
            opcjonalny ``workspace``: prawdziwe repo, gdy ``target`` to sandbox dry-runu — skrypt
            wpisuje jego ścieżkę do konfiguracji i czyta z niego Taskfile / package.json.

    Returns:
        str: Stdout skryptu (lista założonych plików).

    Raises:
        BootstrapError: Brak skryptu, brak basha, timeout albo niezerowy exit code.
    """
    workspace = kwargs.pop("workspace", None)
    argv = build_args(**kwargs)
    bash = find_bash()
    # Skrypt dostaje ten interpreter (widzi pakiet `guides` także bez klonu z `src/`)
    # i commit z metadanych instalacji — w kole nie ma `.git`, z którego by go wziął.
    env = {
        **os.environ,
        "KIT_PYTHON": sys.executable.replace("\\", "/"),
        "KIT_COMMIT": installed_kit_commit() or "",
        "KIT_VERSION": __version__,
        # Skrypt i jego Pythony piszą UTF-8; bez tego Windows dekoduje stdout jako cp1250.
        "PYTHONUTF8": "1",
    }
    if workspace is not None:
        env["KIT_WORKSPACE"] = str(workspace).replace("\\", "/")
    else:
        # Zmienna odziedziczona z otoczenia nie może przekierować prawdziwego reloadu.
        env.pop("KIT_WORKSPACE", None)
    try:
        result = subprocess.run(
            [bash, "--noprofile", "--norc", *argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            check=False,
            # Skrypt (i kazdy proces, ktory sam odpali) nie dostaje stdin serwera MCP.
            # Ten potok nigdy nie konczy sie EOF-em, wiec cokolwiek probowaloby z niego
            # czytac — prompt gita, `read` w shellu — wisialoby az do timeoutu zamiast
            # zwrocic blad. Bootstrap jest nieinteraktywny, wiec pusty stdin to jedyne
            # poprawne wejscie. Patrz ten sam mechanizm w `guides.kit_status._git`.
            stdin=subprocess.DEVNULL,
            env=env,
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
            # Runy /kit-ai:headless (#183): logi i worktree wykonawcy — nie kitowa powierzchnia.
            shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("headless-runs"))
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

        output = run_bootstrap(target=sandbox, workspace=workspace_root, **kwargs)

        after = _relative_files(sandbox)
        plan = BootstrapPlan(script_output=output)
        for rel in sorted(after - before):
            plan.created.append(rel)
        for rel in sorted(before - after):
            plan.deleted.append(rel)
        # Ścieżkę Workspace'u w konfiguracji (Codex, opencode) skrypt wpisuje już
        # prawdziwą (KIT_WORKSPACE), więc porównanie jest bajt w bajt.
        for rel in sorted(before & after):
            produced = (sandbox / rel).read_bytes()
            current = (workspace_root / rel).read_bytes()
            if rel == _STAMP_REL:
                produced = _STAMP_TIME.sub(b"", produced)
                current = _STAMP_TIME.sub(b"", current)
            same = produced == current
            (plan.unchanged if same else plan.modified).append(rel)
        return plan


def render_mcp_template(
    template_text: str,
    *,
    from_src: str,
    language: str,
    clients_arg: str,
    workspace_repl: str = "",
) -> str:
    """Podstaw zmienne środowiska i źródła kita w szablonie konfiguracji MCP."""
    text = template_text.replace(
        "git+https://github.com/radthenone/ai-instruction-kit-mcp.git",
        from_src,
    )
    text = re.sub(
        r'("--language",\s*")[^"]*(")',
        rf"\g<1>{language}\2",
        text,
    )
    text = re.sub(
        r'("--clients",\s*")[^"]*(")',
        rf"\g<1>{clients_arg}\2",
        text,
    )
    text = re.sub(
        r'("--workspace",\s*")[^"]*(")',
        lambda m: m.group(0)
        if not workspace_repl
        else f"{m.group(1)}{workspace_repl}{m.group(2)}",
        text,
    )
    if workspace_repl:
        text = text.replace("/ABSOLUTNA/SCIEZKA/DO/PROJEKTU", workspace_repl)

    if Path(from_src).is_dir():
        text = text.replace('"uvx"', '"uv"', 1)
        text = re.sub(
            r'"--from",(\s*)"' + re.escape(from_src) + r'"',
            lambda m: f'"run", "--project",{m.group(1)}"{from_src}"',
            text,
            count=1,
        )
        if "--kit-root" not in text:
            text = re.sub(
                r'(^([ \t]*)"--clients",[^\n]*\n)',
                lambda m: f'{m.group(1)}{m.group(2)}"--kit-root", "{from_src}",\n',
                text,
                count=1,
                flags=re.MULTILINE,
            )
    return text


def merge_json_config(old_text: str, new_text: str) -> str:
    """Scal nowy wpis serwera MCP kita z istniejącym plikiem JSON użytkownika."""
    old = json.loads(old_text)
    new = json.loads(new_text)
    key = next(k for k in ("mcpServers", "servers", "mcp") if k in new)
    if not isinstance(old, dict) or not isinstance(old.get(key, {}), dict):
        raise ValueError(f"`{key}` nie jest obiektem")
    merged = json.loads(json.dumps(old))
    for k, v in new.items():
        if k != key:
            merged.setdefault(k, v)
    servers = merged.setdefault(key, {})
    for legacy in LEGACY_KIT_SERVERS:
        servers.pop(legacy, None)
    servers[KIT_SERVER] = new[key][KIT_SERVER]
    if merged == old:
        return old_text
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


def toml_open_quote(line: str, quote: str | None) -> str | None:
    """Ogranicznik ciągu wielowierszowego TOML otwartego po tej linii albo None."""
    i = 0
    while i < len(line):
        if quote:
            j = line.find(quote, i)
            if j < 0:
                return quote
            slashes = len(line[i:j]) - len(line[i:j].rstrip("\\"))
            if quote == '"""' and slashes % 2 == 1:
                i = j + 1
                continue
            run = len(line[j:]) - len(line[j:].lstrip(quote[0]))
            i, quote = j + min(run, 5), None
            continue
        c = line[i]
        if c == "#":
            return None
        if line.startswith('"""', i) or line.startswith("'''", i):
            quote, i = line[i : i + 3], i + 3
            continue
        if c in "\"'":
            j = i + 1
            while j < len(line) and line[j] != c:
                j += 2 if c == '"' and line[j] == "\\" else 1
            i = j + 1
            continue
        i += 1
    return quote


def toml_kit_span(lines: list[str], server: str = KIT_SERVER) -> tuple[int, int] | None:
    """Zakres linii tabeli ``[mcp_servers.<server>]`` (z podtabelami) albo None."""
    start = None
    end = len(lines)
    quote = None
    for i, line in enumerate(lines):
        m = _TOML_HEADER.match(line) if quote is None else None
        quote = toml_open_quote(line, quote)
        if not m:
            continue
        keys = [k[1:-1] if k[:1] in "\"'" else k for k in _TOML_KEY.findall(m.group(1))]
        is_kit = keys[:2] == ["mcp_servers", server]
        if start is None and is_kit:
            start = i
        elif start is not None and not is_kit:
            end = i
            break
    if start is None:
        return None
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return start, end


def merge_toml_config(old_text: str, new_text: str) -> str:
    """Scal sekcję ``[mcp_servers.kit-ai-mcp]`` z istniejącym ``config.toml`` (fail-closed bez tomllib)."""
    tomllib: Any
    try:
        import tomllib as _tomllib

        tomllib = _tomllib
    except ImportError:
        tomllib = None
    if tomllib:
        tomllib.loads(old_text)
    new_lines = new_text.splitlines(keepends=True)
    span_new = toml_kit_span(new_lines)
    if span_new is None:
        raise ValueError("szablon TOML nie zawiera sekcji kita")
    kit_block = new_lines[span_new[0] : span_new[1]]
    old_lines = old_text.splitlines(keepends=True)
    if tomllib is None and any(
        toml_kit_span(old_lines, name) is not None
        for name in (KIT_SERVER, *LEGACY_KIT_SERVERS)
    ):
        raise ValueError("do bezpiecznego scalania potrzebny jest Python 3.11+")
    for legacy in LEGACY_KIT_SERVERS:
        while legacy_span := toml_kit_span(old_lines, legacy):
            old_lines = old_lines[: legacy_span[0]] + old_lines[legacy_span[1] :]
    span = toml_kit_span(old_lines)
    if span is None:
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        sep = ["\n"] if old_lines and old_lines[-1].strip() else []
        merged = old_lines + sep + kit_block
    else:
        merged = old_lines[: span[0]] + kit_block + old_lines[span[1] :]
    result = "".join(merged)
    if tomllib:
        def foreign(data: dict[str, Any]) -> dict[str, Any]:
            servers = dict(data.get("mcp_servers", {}))
            for name in (KIT_SERVER, *LEGACY_KIT_SERVERS):
                servers.pop(name, None)
            return {**data, "mcp_servers": servers}

        if foreign(tomllib.loads(old_text)) != foreign(tomllib.loads(result)):
            raise ValueError("scalanie zmieniłoby wpisy spoza kita")
    return result


def sync_mcp_file(
    src: Path,
    dest: Path,
    *,
    from_src: str,
    language: str,
    clients_arg: str,
    workspace_repl: str = "",
) -> str | None:
    """Wyrenderuj i zapisz konfig MCP w ``dest``, scalając z istniejącym albo tworząc ``.bak``."""
    text = render_mcp_template(
        src.read_text(encoding="utf-8"),
        from_src=from_src,
        language=language,
        clients_arg=clients_arg,
        workspace_repl=workspace_repl,
    )
    warning: str | None = None
    if dest.is_file():
        old_text = dest.read_text(encoding="utf-8")
        try:
            text = (
                merge_toml_config(old_text, text)
                if dest.suffix == ".toml"
                else merge_json_config(old_text, text)
            )
        except Exception as exc:
            backup = dest.with_name(dest.name + ".bak")
            backup.write_text(old_text, encoding="utf-8", newline="\n")
            reason = f"{exc.__class__.__name__}: {exc}" if str(exc) else exc.__class__.__name__
            warning = (
                f"  ! {dest.name}: nie da się scalić ({reason}) — oryginał w "
                f"{backup.name}, przenieś swoje wpisy ręcznie"
            )
        else:
            if text == old_text:
                return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    return warning


def skill_allow(
    dest_prefix: str,
    *source_dirs: Path | str,
    names: tuple[str, ...] = (),
) -> str:
    """Zbuduj reguły ``!`` dla skilli kita w ``.gitignore`` po nazwie katalogu lub agenta."""
    collected: list[str] = list(names)
    for source in source_dirs:
        root = Path(source)
        if not root.is_dir():
            continue
        collected.extend(sorted(p.name for p in root.iterdir() if p.is_dir()))
    lines: list[str] = []
    for name in sorted(set(collected)):
        lines.append(f"!{dest_prefix}/{name}/")
        lines.append(f"!{dest_prefix}/{name}/**")
    return "\n".join(lines) if lines else f"# (kit nie dostarcza skilli dla {dest_prefix})"


def render_gitignore_section(
    *,
    template_text: str,
    shared_skills_dir: Path | str,
    shared_agents_dir: Path | str,
    cursor_skills_dir: Path | str,
    machine_files: tuple[str, ...] | list[str],
    begin: str = GITIGNORE_BEGIN,
    end: str = GITIGNORE_END,
) -> str:
    """Wyrenderuj pełną sekcję ``instruction-kit`` dla ``.gitignore``."""
    body = template_text.strip("\n")
    agent_names = tuple(sorted(p.stem for p in Path(shared_agents_dir).glob("*.md")))
    body = body.replace(
        "@KIT_SKILLS_AGENTS@",
        skill_allow(".agents/skills", shared_skills_dir, names=agent_names),
    )
    body = body.replace("@KIT_SKILLS_CLAUDE@", skill_allow(".claude/skills", shared_skills_dir))
    body = body.replace(
        "@KIT_SKILLS_CURSOR@",
        skill_allow(".cursor/skills", shared_skills_dir, cursor_skills_dir),
    )
    rendered_machine = "\n".join(
        f"/{rel}\n/{rel}.bak"
        if rel.endswith((".json", ".toml")) and "kit-bootstrap" not in rel
        else "/" + rel
        for rel in (line.lstrip("/") for line in machine_files)
    )
    body = body.replace("@KIT_MACHINE_FILES@", rendered_machine)
    return f"{begin}\n{body}\n{end}\n"


def merge_gitignore_text(
    existing: str,
    section: str,
    *,
    begin: str = GITIGNORE_BEGIN,
    end: str = GITIGNORE_END,
) -> tuple[str, str]:
    """Wstaw albo podmień sekcję kita w treści ``.gitignore``; zwraca ``(nowa_treść, akcja)``."""
    if begin in existing and end in existing:
        head, _, rest = existing.partition(begin)
        _, _, tail = rest.partition(end)
        return f"{head}{section}{tail.lstrip(chr(10))}", "zaktualizowano"
    prefix = existing if not existing or existing.endswith("\n") else existing + "\n"
    separator = "\n" if prefix.strip() else ""
    return f"{prefix}{separator}{section}", "dodano"


def sync_gitignore_file(
    *,
    dest: Path,
    template_path: Path,
    shared_skills_dir: Path | str,
    shared_agents_dir: Path | str,
    cursor_skills_dir: Path | str,
    machine_files: tuple[str, ...] | list[str],
    begin: str = GITIGNORE_BEGIN,
    end: str = GITIGNORE_END,
) -> str | None:
    """Zapisz sekcję kita do ``dest`` tylko przy zmianie; zwraca akcję albo None."""
    section = render_gitignore_section(
        template_text=template_path.read_text(encoding="utf-8"),
        shared_skills_dir=shared_skills_dir,
        shared_agents_dir=shared_agents_dir,
        cursor_skills_dir=cursor_skills_dir,
        machine_files=machine_files,
        begin=begin,
        end=end,
    )
    existing = dest.read_text(encoding="utf-8") if dest.is_file() else ""
    updated, action = merge_gitignore_text(existing, section, begin=begin, end=end)
    if updated == existing:
        return None
    dest.write_text(updated, encoding="utf-8", newline="\n")
    return action


def detect_profile_tiers(profile_text: str) -> list[str]:
    """Wykryj aktywne znaczniki tierów (``backend``, ``client``) z treści Profilu."""
    empty = {"", "none", "null", "~", "false", "0", "no"}
    filled: set[str] = set()
    for tier in ("backend", "web", "mobile"):
        match = re.search(rf"^{tier}:[ \t]*['\"]?([^'\"\s#]*)", profile_text, re.MULTILINE)
        if match and match.group(1).lower() not in empty:
            filled.add(tier)
    legacy = re.search(r"^stacks:[ \t]*\n((?:[ \t]+\S.*\n?)*)", profile_text, re.MULTILINE)
    for name, value in re.findall(
        r"^[ \t]+([\w-]+):[ \t]*(.*)$",
        legacy.group(1) if legacy else "",
        re.MULTILINE,
    ):
        if value.strip().strip("'\"").lower() in empty:
            continue
        if name == "django-drf":
            filled.add("backend")
        elif name == "expo-router":
            filled.update({"web", "mobile"})
    tags: list[str] = []
    if "backend" in filled:
        tags.append("backend")
    if filled & {"web", "mobile"}:
        tags.append("client")
    return tags


def stage_shared_agents(
    *,
    src_dir: Path,
    dest_dir: Path,
    tiers: set[str],
    clients: set[str],
    headless_enabled: bool,
) -> list[str]:
    """Przefiltruj agentów według tierów/klientów do ``dest_dir`` i zwróć pominięte nazwy."""
    def gate(match: re.Match[str]) -> str:
        names = {name.strip() for name in match.group(1).split(",")}
        return match.group(2) if names & clients else ""

    skipped: list[str] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob("*.md")):
        if src.stem == "headless" and not headless_enabled:
            skipped.append(src.stem)
            continue
        lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        tier = next(
            (line.partition(":")[2].strip() for line in lines[1:end] if line.startswith("tier:")),
            None,
        )
        if tier and tier not in tiers:
            skipped.append(src.stem)
            continue
        kept = [
            line
            for i, line in enumerate(lines)
            if not (0 < i < end and line.startswith(("tier:", "model-tier:", "classification:")))
        ]
        text = _CLIENT_BLOCK.sub(gate, "".join(kept))
        if "<!-- clients" in text or "<!-- /clients" in text:
            raise ValueError(f"{src.name}: niedomknięty albo zagnieżdżony blok <!-- clients: … -->")
        (dest_dir / src.name).write_text(text, encoding="utf-8", newline="\n")
    return skipped


def load_jsonc(text: str) -> Any:
    """Sparsuj JSONC (komentarze ``//`` i ``/* */`` oraz końcowe przecinki poza stringami)."""
    stripped = re.sub(_JSON_STRING + r"|//[^\n]*|/\*.*?\*/", lambda m: m.group(1) or "", text, flags=re.S)
    stripped = re.sub(_JSON_STRING + r"|,(\s*[}\]])", lambda m: m.group(1) or m.group(2), stripped)
    return json.loads(stripped)


def inherit_opencode_model(
    dest: Path,
    *,
    config_dir: Path | None = None,
) -> tuple[str, Path] | None:
    """Odziedzicz ``model`` z globalnego configu OpenCode, jeśli projektowy go nie ma."""
    try:
        text = dest.read_text(encoding="utf-8")
        project = json.loads(text)
    except (OSError, ValueError):
        return None
    if not isinstance(project, dict) or "model" in project:
        return None
    if config_dir is None:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
    model: str | None = None
    source: Path | None = None
    for name in ("config.json", "opencode.json", "opencode.jsonc"):
        try:
            loaded = load_jsonc((config_dir / name).read_text(encoding="utf-8-sig"))
            value = loaded.get("model") if isinstance(loaded, dict) else None
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str) and value:
            model, source = value, config_dir / name
    if model is None or source is None:
        return None
    line = f'  "model": {json.dumps(model, ensure_ascii=False)},\n'
    updated = re.sub(r"\A\{[ \t]*\n", lambda m: m.group(0) + line, text, count=1)
    try:
        ok = json.loads(updated).get("model") == model
    except ValueError:
        ok = False
    if not ok:
        updated = json.dumps({"model": model, **project}, indent=2, ensure_ascii=False) + "\n"
    dest.write_text(updated, encoding="utf-8", newline="\n")
    return model, source
