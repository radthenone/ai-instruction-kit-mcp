"""Retro: deterministyczny skaner sesji agentów (#371, część (a) #338).

Czyta transkrypty Claude Code (JSONL razem z subagentami) i wyciąga sygnały: deny
guardów, błędy narzędzi, blokady harnessu, błędy API, powtórzone wywołania, zgodność
z ``get_overlay`` przed edycją kodu oraz koszt sesji. Do ``~/.cache`` trafia tylko
znormalizowany tekst i zamaskowane evidence, nigdy całe wiadomości. Nic tu nie woła
modelu (0 tokenów).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
KEY_LIMIT = 200
EVIDENCE_LIMIT = 240
REPEAT_THRESHOLD = 3
OVERLAY_TOOL = "mcp__project-guides__get_overlay"
EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
KIT_CODE_PATH = re.compile(r"(?:^|/)(?:src|tests|templates|modules)/")

_HOOK_DENY = re.compile(r"^PreToolUse:(?P<tool>[\w-]+) hook error: (?P<guard>[\w.-]+): (?P<msg>.*)$")
_TRAILING_TAG = re.compile(r"\s*\[[\w.-]+\]\s*$")
_HARNESS_BLOCKS = (
    ("safety-check", re.compile(r"built-in safety check", re.IGNORECASE)),
)
_SECRETS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
_KEY_VALUE = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)(\s*[=:]\s*)\S+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_HOME = re.compile(r"/(?:home|Users)/[^/\s]+")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{12,}\b")
_DIGITS = re.compile(r"\d+")
_EXIT_CODE = re.compile(r"^Exit code -?\d+$")


def mask(text: str) -> str:
    """Maskuje sekrety, e-maile i nazwę użytkownika w ścieżce domowej."""
    masked = _HOME.sub("~", text)
    for pattern in _SECRETS:
        masked = pattern.sub("<secret>", masked)
    masked = _BEARER.sub("Bearer <secret>", masked)
    masked = _KEY_VALUE.sub(r"\1\2<secret>", masked)
    return _EMAIL.sub("<email>", masked)


def normalize(text: str) -> str:
    """Klucz grupowania: bez katalogu domowego, identyfikatorów, liczb i nadmiaru spacji."""
    collapsed = _HOME.sub("~", text)
    collapsed = _UUID.sub("<id>", collapsed)
    collapsed = _LONG_HEX.sub("<id>", collapsed)
    collapsed = _DIGITS.sub("N", collapsed)
    return " ".join(collapsed.split())[:KEY_LIMIT]


def evidence(text: str) -> str:
    """Zamaskowany, jednowierszowy fragment do zapisu (nigdy cała wiadomość)."""
    single = " ".join(mask(text).split())
    if len(single) <= EVIDENCE_LIMIT:
        return single
    return single[: EVIDENCE_LIMIT - 3] + "..."


def fingerprint(kind: str, key: str) -> str:
    """Stały klucz deduplikacji znaleziska — ten sam problem daje ten sam ciąg w każdej sesji."""
    return hashlib.sha256(f"{kind}\x1f{key}".encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Signal:
    """Pojedyncze wykrycie w sesji (termin „Sygnał” z CONTEXT.md)."""

    kind: str
    key: str
    evidence: str
    guard: str | None = None
    tool_name: str | None = None
    tool_input: Any = None
    count: int = 1


@dataclass
class SessionMetrics:
    """Koszt sesji liczony z ``message.usage`` (każde wywołanie API raz)."""

    api_calls: int = 0
    cache_read_sum: int = 0
    max_context: int = 0


@dataclass
class ParsedSession:
    session_id: str
    files: int
    signals: list[Signal] = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)


@dataclass
class _Scan:
    """Stan przebiegu przez wszystkie pliki sesji (główny plik i subagenty)."""

    tool_uses: dict[str, tuple[str, dict]] = field(default_factory=dict)
    seen_message_ids: set[str] = field(default_factory=set)
    signals: list[Signal] = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)


@dataclass
class _FileState:
    """Stan jednego pliku (subagenta): reguły i liczniki obowiązują w kontekście agenta."""

    overlay_seen: bool = False
    unseen_edits: int = 0
    first_unseen: str = ""
    seen_tool_ids: set[str] = field(default_factory=set)
    repeats: dict[str, int] = field(default_factory=dict)


def parse_session(paths: list[Path], session_id: str) -> ParsedSession:
    """Wyciąga sygnały i metryki z plików sesji (główny JSONL i jego subagenty)."""
    scan = _Scan()
    for path in paths:
        _scan_file(path, scan, session_id=session_id)
    return ParsedSession(session_id=session_id, files=len(paths), signals=scan.signals, metrics=scan.metrics)


def _read_records(path: Path) -> Iterator[dict]:
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                yield data


def _scan_file(path: Path, scan: _Scan, *, session_id: str = "") -> None:
    agent_id = path.stem if path.stem != session_id else "main"
    state = _FileState()
    for record in _read_records(path):
        if record.get("isApiErrorMessage") is True:
            scan.signals.append(_api_signal(_flatten(_content(record))))
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        _count_usage(message, scan)
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                _on_tool_use(block, scan, state)
            elif block.get("type") == "tool_result":
                _on_tool_result(block, scan)
    if state.unseen_edits:
        key = f"missing-get_overlay-before-edit:{agent_id}"
        ev = f"{agent_id}: {state.first_unseen}"
        scan.signals.append(
            Signal(
                "mcp_compliance",
                key,
                evidence(ev),
                count=state.unseen_edits,
            )
        )
    for key, count in sorted(state.repeats.items()):
        if count >= REPEAT_THRESHOLD:
            name = key.split(" ", 1)[0]
            scan.signals.append(
                Signal("repeated_tool_use", normalize(mask(key)), evidence(key), tool_name=name, count=count)
            )


def _content(record: dict) -> Any:
    message = record.get("message")
    return message.get("content") if isinstance(message, dict) else None


def _count_usage(message: dict, scan: _Scan) -> None:
    usage = message.get("usage")
    msg_id = message.get("id")
    if not isinstance(usage, dict) or not msg_id or msg_id in scan.seen_message_ids:
        return
    scan.seen_message_ids.add(msg_id)
    cache_read = _int(usage.get("cache_read_input_tokens"))
    context = _int(usage.get("input_tokens")) + cache_read + _int(usage.get("cache_creation_input_tokens"))
    scan.metrics.api_calls += 1
    scan.metrics.cache_read_sum += cache_read
    scan.metrics.max_context = max(scan.metrics.max_context, context)


def _on_tool_use(block: dict, scan: _Scan, state: _FileState) -> None:
    tool_id = str(block.get("id") or "")
    if tool_id:
        if tool_id in state.seen_tool_ids:
            return
        state.seen_tool_ids.add(tool_id)
    name = str(block.get("name") or "")
    raw_input = block.get("input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    if tool_id:
        scan.tool_uses[tool_id] = (name, tool_input)
    if name == OVERLAY_TOOL:
        state.overlay_seen = True
    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    if name in EDIT_TOOLS and path and KIT_CODE_PATH.search(path) and not state.overlay_seen:
        state.unseen_edits += 1
        state.first_unseen = state.first_unseen or path
    repeat_key = f"{name} {json.dumps(tool_input, sort_keys=True, ensure_ascii=False)}"
    state.repeats[repeat_key] = state.repeats.get(repeat_key, 0) + 1


_QUESTIONING_TOOLS = frozenset({
    "confirm_repository_trust",
    "askfollowupquestion",
    "askuserquestion",
    "ask_followup_question",
    "ask_user",
    "ask_question",
})


def _is_questioning_tool(name: str) -> bool:
    if not name:
        return False
    lower = name.lower()
    base = lower.rsplit("__", 1)[-1]
    return base in _QUESTIONING_TOOLS or "confirm_repository_trust" in lower


def _is_json(text: str) -> bool:
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        try:
            json.loads(stripped)
            return True
        except ValueError:
            return False
    return False


def _on_tool_result(block: dict, scan: _Scan) -> None:
    text = _flatten(block.get("content"))
    lines = text.strip().splitlines()
    first = lines[0] if lines else ""
    is_error = block.get("is_error") is True
    tool_use_id = str(block.get("tool_use_id") or "")
    tool_name, tool_input = scan.tool_uses.get(tool_use_id, ("", None))
    hook = _HOOK_DENY.match(first)
    if hook and is_error:
        guard = hook.group("guard")
        message = _TRAILING_TAG.sub("", hook.group("msg"))
        scan.signals.append(
            Signal(
                "guard_deny",
                f"{guard}: {normalize(mask(message))}",
                evidence(message),
                guard=guard,
                tool_name=tool_name or hook.group("tool"),
                tool_input=tool_input,
            )
        )
        return
    if is_error and not _is_json(text):
        for label, pattern in _HARNESS_BLOCKS:
            if first and pattern.search(first):
                scan.signals.append(Signal("harness_block", label, evidence(first)))
                return
    if _is_questioning_tool(tool_name):
        ev = f"{tool_name}: {first}" if first else tool_name
        scan.signals.append(
            Signal(
                "questioning_tool",
                normalize(mask(ev)),
                evidence(ev),
                tool_name=tool_name,
                tool_input=tool_input,
            )
        )
        return
    if is_error and first:
        # Bash zaczyna błąd od „Exit code N” — bez tego wszystkie błędy Bash zlałyby się w jedno Znalezisko.
        detail = next((line for line in lines[1:] if line.strip()), "") if _EXIT_CODE.match(first) else ""
        line = f"{first}: {detail}" if detail else first
        scan.signals.append(Signal("tool_error", normalize(mask(line)), evidence(line)))


def _api_signal(text: str) -> Signal:
    lowered = text.lower()
    if "rate_limit" in lowered or "rate limit" in lowered:
        label = "rate_limit"
    elif "authentication" in lowered:
        label = "authentication_failed"
    else:
        label = "other"
    return Signal("api_error", f"api:{label}", evidence(text))


def _flatten(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


GUARD_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
REPLAY_TIMEOUT = 10.0
# Łączny limit replayu na jeden skan: hook SessionEnd ma 120 s, reszta deny dostaje ``unknown``.
REPLAY_BUDGET = 60.0


@dataclass(frozen=True)
class Finding:
    """Znalezisko: sygnały o tym samym fingerprincie (termin „Znalezisko” z CONTEXT.md)."""

    kind: str
    fingerprint: str
    count: int
    evidence: str
    guard: str | None = None
    tool_name: str | None = None
    replay: str = "n/a"


def replay_guard(
    guard: str | None,
    tool_name: str | None,
    tool_input: Any,
    *,
    kit_root: Path,
    cwd: Path,
    timeout: float = REPLAY_TIMEOUT,
) -> str:
    """Odtwarza decyzję aktualnego guarda z ``templates/shared/guards`` dla zapisanego wywołania.

    Zwraca ``allow`` albo ``deny``; ``unknown``, gdy nie da się rozstrzygnąć (brak guarda,
    brak wejścia, błąd procesu, nieczytelna odpowiedź). Pusta odpowiedź przy kodzie 0
    znaczy brak opinii, czyli ``allow``.
    """
    node = shutil.which("node")
    if guard is None or not GUARD_NAME.fullmatch(guard) or node is None or tool_input is None:
        return "unknown"
    script = kit_root / "templates" / "shared" / "guards" / f"{guard}.mjs"
    if not script.is_file():
        return "unknown"
    payload = json.dumps(
        {"hook_event_name": "PreToolUse", "tool_name": tool_name or "", "tool_input": tool_input, "cwd": str(cwd)},
        ensure_ascii=False,
    )
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(cwd)}
    try:
        proc = subprocess.run(
            [node, str(script)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(cwd),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    output = proc.stdout.strip()
    if not output:
        return "allow"
    try:
        data = json.loads(output.splitlines()[-1])
    except ValueError:
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    hook = data.get("hookSpecificOutput")
    decision = hook.get("permissionDecision") if isinstance(hook, dict) else data.get("permissionDecision")
    return decision if decision in ("allow", "deny") else "unknown"


def budgeted_replay(*, kit_root: Path, cwd: Path, budget: float = REPLAY_BUDGET) -> Callable[[Signal], str]:
    """Replay guardów z łącznym limitem czasu; po jego wyczerpaniu zwraca ``unknown``."""
    deadline = time.monotonic() + budget

    def replay(signal: Signal) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "unknown"
        return replay_guard(
            signal.guard,
            signal.tool_name,
            signal.tool_input,
            kit_root=kit_root,
            cwd=cwd,
            timeout=min(REPLAY_TIMEOUT, remaining),
        )

    return replay


def build_findings(signals: list[Signal], *, replay: Callable[[Signal], str]) -> list[Finding]:
    """Grupuje sygnały po fingerprincie; deny, który na aktualnym kicie się nie odtwarza, odpada.

    Każdy deny guarda odtwarzany jest raz na unikalne wywołanie (guard, narzędzie, wejście).
    Inne rodzaje sygnałów nie są odtwarzane.
    """
    verdicts: dict[tuple[str | None, str | None, str], str] = {}
    groups: dict[str, list[tuple[Signal, str]]] = {}
    for signal in signals:
        status = "n/a"
        if signal.kind == "guard_deny":
            call = (signal.guard, signal.tool_name, json.dumps(signal.tool_input, sort_keys=True, default=str))
            if call not in verdicts:
                verdicts[call] = replay(signal)
            status = verdicts[call]
            if status == "allow":
                continue
        groups.setdefault(fingerprint(signal.kind, signal.key), []).append((signal, status))
    findings: list[Finding] = []
    for fp, members in groups.items():
        first = members[0][0]
        if first.kind == "guard_deny":
            replay_status = "deny" if any(status == "deny" for _, status in members) else "unknown"
        else:
            replay_status = "n/a"
        findings.append(
            Finding(
                kind=first.kind,
                fingerprint=fp,
                count=sum(signal.count for signal, _ in members),
                evidence=first.evidence,
                guard=first.guard,
                tool_name=first.tool_name,
                replay=replay_status,
            )
        )
    return sorted(findings, key=lambda finding: (finding.kind, finding.fingerprint))


SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_PROJECT_CHARS = re.compile(r"[^A-Za-z0-9]")
_REPO_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_SINCE_DAYS = re.compile(r"(\d+)d")


def project_dir_name(workspace: Path) -> str:
    """Nazwa katalogu projektu w ``~/.claude/projects``: każdy znak spoza ``[A-Za-z0-9]`` to ``-``."""
    return _PROJECT_CHARS.sub("-", str(workspace.resolve()))


def repo_name(workspace: Path) -> str:
    """Nazwa repo w ścieżce cache (nazwa katalogu roboczego, bez znaków ze ścieżek)."""
    return _REPO_CHARS.sub("-", workspace.resolve().name) or "repo"


def default_projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def default_cache_root() -> Path:
    """``$XDG_CACHE_HOME/kit-ai/retro`` albo ``~/.cache/kit-ai/retro``."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "kit-ai" / "retro"


def parse_since(value: str, *, now: datetime) -> float:
    """``Nd`` (ostatnie N dni) albo ``YYYY-MM-DD`` (północ czasu lokalnego) jako znacznik czasu."""
    days = _SINCE_DAYS.fullmatch(value)
    if days:
        return (now - timedelta(days=int(days.group(1)))).timestamp()
    try:
        return datetime.strptime(value, "%Y-%m-%d").timestamp()
    except ValueError as exc:
        raise ValueError(f"nieznany format --since: {value} (oczekiwano YYYY-MM-DD albo Nd)") from exc


def kit_sha(workspace: Path) -> str:
    """Commit kita, z którego działa serwer MCP; inaczej ``unknown``.

    Najpierw pin ``@<ref>`` z ``--from git+…`` (instalacja przez uvx), potem HEAD klona z ``--kit-root``.
    """
    try:
        config = json.loads((workspace / ".mcp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unknown"
    servers = config.get("mcpServers") if isinstance(config, dict) else None
    if not isinstance(servers, dict):
        return "unknown"
    for server in servers.values():
        args = server.get("args") if isinstance(server, dict) else None
        if not isinstance(args, list):
            continue
        pairs = [(flag, value) for flag, value in zip(args, args[1:]) if isinstance(value, str)]
        for flag, value in pairs:
            if flag == "--from" and value.startswith("git+") and "@" in value.rsplit("/", 1)[-1]:
                return value.rsplit("@", 1)[1]
        for flag, value in pairs:
            if flag != "--kit-root":
                continue
            try:
                result = subprocess.run(
                    ["git", "-C", value, "rev-parse", "--short=12", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                continue
            sha = result.stdout.strip()
            if result.returncode == 0 and sha:
                return sha
    return "unknown"


def find_session_files(projects_root: Path, session_id: str) -> list[Path]:
    """Plik JSONL sesji i pliki jej subagentów; pusta lista, gdy sesji nie ma."""
    if not SESSION_ID.fullmatch(session_id):
        raise ValueError(f"nieprawidłowy identyfikator sesji: {session_id!r}")
    matches = sorted(projects_root.glob(f"*/{session_id}.jsonl"), key=_mtime, reverse=True)
    if not matches:
        return []
    return [matches[0], *_subagent_files(matches[0].parent, session_id)]


def _subagent_files(project_dir: Path, session_id: str) -> list[Path]:
    return sorted((project_dir / session_id / "subagents").glob("*.jsonl"))


def _mtime(path: Path) -> float:
    return path.stat().st_mtime


HEADLESS_EXIT = re.compile(r"^\[headless\] kod wyjścia: (-?\d+)\s*$", re.MULTILINE)
HEADLESS_CLEAN = re.compile(
    r"^## git status --short\n\(czysto\)\n## git log [^\n]*\n\(brak commitów\)", re.MULTILINE
)


def headless_runs(workspace: Path) -> list[Path]:
    """Przebiegi ``.ai/headless-runs/<run>/`` z plikiem ``headless.log`` (każdy to osobna sesja)."""
    root = workspace / ".ai" / "headless-runs"
    return [
        run
        for run in sorted(root.glob("*"))
        if run.is_dir() and SESSION_ID.fullmatch(run.name) and (run / "headless.log").is_file()
    ]


def parse_headless_run(run_dir: Path) -> ParsedSession:
    """Sygnały przebiegu headless: ostatni kod wyjścia z ``headless.log`` i czystość drzewa po wyjściu 0."""
    try:
        text = (run_dir / "headless.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    exits = HEADLESS_EXIT.findall(text)
    signals: list[Signal] = []
    if not exits:
        signals.append(Signal("headless_exit", "exit-missing", "brak linii kod wyjścia w headless.log"))
    elif exits[-1] != "0":
        signals.append(Signal("headless_exit", "exit-nonzero", evidence(f"kod wyjścia: {exits[-1]}")))
    elif HEADLESS_CLEAN.search(text):
        signals.append(Signal("headless_no_change", "exit0-clean-tree", "kod wyjścia: 0, czyste drzewo po przebiegu"))
    return ParsedSession(session_id=run_dir.name, files=1, signals=signals)


def _scan_files(
    files: list[Path],
    *,
    session_id: str,
    workspace: Path,
    cache_root: Path,
    replay: Callable[[Signal], str],
    sha: str,
    now: datetime | None,
) -> tuple[Path, list[Finding]]:
    """Sesja Claude: parsuje jej pliki razem z subagentami i zapisuje wpisy."""
    return _write_entries(
        parse_session(files, session_id=session_id),
        source="claude",
        workspace=workspace,
        cache_root=cache_root,
        replay=replay,
        sha=sha,
        now=now,
    )


def _write_entries(
    parsed: ParsedSession,
    *,
    source: str,
    workspace: Path,
    cache_root: Path,
    replay: Callable[[Signal], str],
    sha: str,
    now: datetime | None,
) -> tuple[Path, list[Finding]]:
    """Odtwarza deny, buduje Znaleziska i zapisuje wpisy do ``cache_root/<repo>/<sesja>.jsonl``.

    Plik powstaje przez zapis tymczasowy i podmianę, więc ponowny skan tej samej sesji
    zastępuje wynik zamiast go dublować.
    """
    session_id = parsed.session_id
    findings = build_findings(parsed.signals, replay=replay)
    repo = repo_name(workspace)
    base = {"schema": SCHEMA_VERSION, "source": source, "repo": repo, "kit_sha": sha, "session": session_id}
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    records: list[dict] = [
        {
            "type": "session",
            **base,
            "scanned_at": stamp,
            "files": parsed.files,
            "metrics": asdict(parsed.metrics),
            "findings": len(findings),
        }
    ]
    for finding in findings:
        records.append(
            {
                "type": "finding",
                **base,
                "kind": finding.kind,
                "fingerprint": finding.fingerprint,
                "guard": finding.guard,
                "tool": finding.tool_name,
                "count": finding.count,
                "replay": finding.replay,
                "evidence": finding.evidence,
            }
        )
    target_dir = cache_root / repo
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{session_id}.jsonl"
    staging = target.with_name(f"{target.name}.tmp")
    staging.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8", newline="\n")
    os.replace(staging, target)
    return target, findings


def scan_session(
    session_id: str,
    *,
    workspace: Path,
    projects_root: Path,
    cache_root: Path,
    kit_root: Path,
    runner: Callable[[Signal], str] | None = None,
    now: datetime | None = None,
) -> Path:
    """Skanuje jedną sesję razem z subagentami i zwraca ścieżkę wpisów w cache repo."""
    files = find_session_files(projects_root, session_id)
    if not files:
        raise ValueError(f"nie znaleziono sesji {session_id} w {projects_root}")
    target, _ = _scan_files(
        files,
        session_id=session_id,
        workspace=workspace,
        cache_root=cache_root,
        replay=runner or budgeted_replay(kit_root=kit_root, cwd=workspace),
        sha=kit_sha(workspace),
        now=now,
    )
    return target


def scan_command(
    workspace: Path,
    *,
    session: str | None,
    since: str | None,
    projects_root: Path,
    cache_root: Path,
    kit_root: Path,
    runner: Callable[[Signal], str] | None = None,
    now: datetime | None = None,
) -> str:
    """Tekst wyniku ``kit-ai retro scan``: jedna sesja (``session``) albo sesje repo, opcjonalnie od ``since``."""
    stamp = now or datetime.now(timezone.utc)
    options = {
        "workspace": workspace,
        "cache_root": cache_root,
        "replay": runner or budgeted_replay(kit_root=kit_root, cwd=workspace),
        "sha": kit_sha(workspace),
        "now": stamp,
    }
    if session is not None:
        files = find_session_files(projects_root, session)
        if not files:
            raise ValueError(f"nie znaleziono sesji {session} w {projects_root}")
        target, findings = _scan_files(files, session_id=session, **options)
        lines = [f"retro: sesja {session} → {target} (znaleziska: {len(findings)})"]
        lines += [
            f"  {f.kind} ×{f.count} replay={f.replay}" + (f" [{f.guard}]" if f.guard else "") + f": {f.evidence}"
            for f in findings
        ]
        return "\n".join(lines)
    cutoff = parse_since(since, now=stamp) if since else None
    base = projects_root / project_dir_name(workspace)
    mains = [
        main
        for main in sorted(base.glob("*.jsonl"))
        if SESSION_ID.fullmatch(main.stem) and (cutoff is None or _mtime(main) >= cutoff)
    ]
    runs = [
        run
        for run in headless_runs(workspace)
        if cutoff is None or _mtime(run / "headless.log") >= cutoff
    ]
    if not mains and not runs:
        return f"retro: brak sesji i przebiegów headless w {base}"
    found_total = 0
    for main in mains:
        _, findings = _scan_files([main, *_subagent_files(base, main.stem)], session_id=main.stem, **options)
        found_total += len(findings)
    for run in runs:
        _, findings = _write_entries(parse_headless_run(run), source="headless", **options)
        found_total += len(findings)
    return (
        f"retro: sesje: {len(mains)}, przebiegi headless: {len(runs)}, znaleziska: {found_total} "
        f"→ {cache_root / repo_name(workspace)}"
    )
