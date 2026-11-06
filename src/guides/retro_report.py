"""``kit-ai retro report`` — agregacja znalezisk z wielu repo i progi propozycji (#373, część (c) #338).

Czyta zapisy ``kit-ai retro scan`` w ``<cache>/<repo>/<sesja>.jsonl``. Raport niczego nie zapisuje
i niczego nie zakłada: pokazuje propozycje, które człowiek musi zaakceptować.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Próg propozycji z #338 (część (c)): znalezisko w co najmniej tylu sesjach albo tylu repo.
REPORT_SESSION_THRESHOLD = 3
REPORT_REPO_THRESHOLD = 2
# Górna granica `gh issue list`; pełna strona oznacza, że część issue mogła zostać ucięta.
ISSUE_LIMIT = 1000
# Dedup po markerze z ADR-0015: fingerprint w body otwartego issue jako ukryty komentarz HTML.
_MARKER = re.compile(r"<!--\s*retro-fingerprint:\s*([0-9a-f]{16})\s*-->")

GhRun = Callable[[list[str], Path], str]


@dataclass
class Group:
    """Znalezisko z wielu repo: wszystkie zapisy o tym samym fingerprincie (termin „Znalezisko”)."""

    fingerprint: str
    kind: str
    evidence: str
    guard: str | None = None
    tool: str | None = None
    sessions: set[tuple[str, str]] = field(default_factory=set)
    repos: set[str] = field(default_factory=set)
    replays: set[str] = field(default_factory=set)
    kit_shas: set[str] = field(default_factory=set)
    count: int = 0


def read_findings(cache_root: Path) -> list[tuple[str, dict]]:
    """Rekordy ``finding`` jako pary (repo, rekord). Uszkodzone linie i obce typy są pomijane."""
    found: list[tuple[str, dict]] = []
    for path in sorted(cache_root.glob("*/*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("type") == "finding":
                found.append((path.parent.name, record))
    return found


def group_findings(findings: list[tuple[str, dict]]) -> list[Group]:
    """Grupuje zapisy po fingerprincie; każda sesja liczy się raz na znalezisko."""
    groups: dict[str, Group] = {}
    for repo, record in findings:
        fingerprint = record.get("fingerprint")
        kind = record.get("kind")
        if not isinstance(fingerprint, str) or not isinstance(kind, str):
            continue
        group = groups.get(fingerprint)
        if group is None:
            guard, tool = record.get("guard"), record.get("tool")
            group = Group(
                fingerprint=fingerprint,
                kind=kind,
                evidence=str(record.get("evidence", "")),
                guard=guard if isinstance(guard, str) else None,
                tool=tool if isinstance(tool, str) else None,
            )
            groups[fingerprint] = group
        group.sessions.add((repo, str(record.get("session", ""))))
        group.repos.add(repo)
        group.replays.add(str(record.get("replay", "n/a")))
        group.kit_shas.add(str(record.get("kit_sha", "unknown")))
        count = record.get("count")
        group.count += count if isinstance(count, int) else 1
    return sorted(groups.values(), key=lambda group: (group.kind, group.fingerprint))


def is_candidate(group: Group) -> bool:
    """Próg z #338: co najmniej 3 sesje albo co najmniej 2 repo."""
    return len(group.sessions) >= REPORT_SESSION_THRESHOLD or len(group.repos) >= REPORT_REPO_THRESHOLD


def _run_gh(argv: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=str(cwd))
    except OSError as exc:
        raise ValueError(f"dedup z otwartymi issue wymaga gh, a nie udało się go uruchomić: {exc}") from exc
    if proc.returncode != 0:
        raise ValueError(f"gh issue list nie powiódł się: {proc.stderr.strip() or proc.returncode}")
    return proc.stdout


def parse_open_issues(payload: str) -> set[str]:
    """Fingerprinty z markerów w body issue; issue bez tekstu w body nic nie wnoszą."""
    try:
        issues = json.loads(payload)
    except ValueError as exc:
        raise ValueError("gh zwrócił nieczytelną listę issue (oczekiwano JSON)") from exc
    if not isinstance(issues, list):
        raise ValueError("gh zwrócił listę issue w nieoczekiwanym kształcie")
    if len(issues) >= ISSUE_LIMIT:
        # Ucięta lista mogłaby pominąć marker i pokazać duplikat — odmawiamy jak przy braku gh.
        raise ValueError(f"otwartych issue jest co najmniej {ISSUE_LIMIT}; dedup byłby niepełny")
    found: set[str] = set()
    for issue in issues:
        body = issue.get("body") if isinstance(issue, dict) else None
        if isinstance(body, str):
            found.update(_MARKER.findall(body))
    return found


def open_issue_fingerprints(workspace: Path, *, gh_run: GhRun | None = None) -> set[str]:
    """Fingerprinty z markerem w body otwartych issue repo w ``workspace`` (ADR-0015)."""
    argv = ["gh", "issue", "list", "--state", "open", "--limit", str(ISSUE_LIMIT), "--json", "body"]
    return parse_open_issues((gh_run or _run_gh)(argv, workspace))


def _proposal_lines(group: Group) -> list[str]:
    lines = [f"Propozycja {group.kind} · fingerprint {group.fingerprint}"]
    lines.append(
        f"  sesje: {len(group.sessions)} · repo: {', '.join(sorted(group.repos))} · "
        f"wystąpienia: {group.count} · replay: {', '.join(sorted(group.replays))} · "
        f"kit: {', '.join(sorted(group.kit_shas))}"
    )
    if group.guard or group.tool:
        lines.append(f"  guard: {group.guard or '-'} · narzędzie: {group.tool or '-'}")
    lines.append(f"  dowód: {group.evidence}")
    lines.append(f"  marker do karty: <!-- retro-fingerprint: {group.fingerprint} -->")
    return lines


def report_command(workspace: Path, *, cache_root: Path, gh_run: GhRun | None = None) -> str:
    """Tekst ``kit-ai retro report``: propozycje ponad progami, bez znalezisk z otwartym issue."""
    findings = read_findings(cache_root)
    if not findings:
        return f"retro report: brak znalezisk w {cache_root}"
    groups = group_findings(findings)
    candidates = [group for group in groups if is_candidate(group)]
    # gh pytamy tylko przy kandydatach; bez dedupu nie pokazujemy propozycji (fail-closed).
    open_fingerprints = open_issue_fingerprints(workspace, gh_run=gh_run) if candidates else set()
    proposals = [group for group in candidates if group.fingerprint not in open_fingerprints]
    skipped = len(candidates) - len(proposals)
    repos = {repo for repo, _ in findings}
    lines = [
        f"retro report: repo {len(repos)} · znaleziska {len(groups)} · powyżej progów {len(candidates)} · "
        f"pominięte (otwarte issue): {skipped} · propozycje {len(proposals)}"
    ]
    if not proposals:
        lines.append("Brak propozycji do zaakceptowania (progi: sesje ≥3 albo repo ≥2).")
    for group in proposals:
        lines += _proposal_lines(group)
    if proposals:
        lines.append(
            "Karty zakłada człowiek po akceptacji: /create-task (zmiana kitu) albo "
            "/kit-project-edit (zmiana w projekcie). Raport niczego nie zakłada."
        )
    return "\n".join(lines)
