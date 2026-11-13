"""``kit-ai issue stats`` — analiza i priorytetyzacja otwartych issues.

Generuje raport z dokładnie 4 sekcjami:
  1. Status bieżący: Co faktycznie zostało do zrobienia?
  2. Rekomendowana kolejność prac (Roadmapa)
  3. Podejście, skille i metodyka per zadanie
  4. Przegląd gotowości issues pod night-run
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GhRun = Callable[[list[str], Path], str]

SECTION_HEADERS = [
    "## 1. Status bieżący: Co faktycznie zostało do zrobienia?",
    "## 2. Rekomendowana kolejność prac (Roadmapa)",
    "## 3. Podejście, skille i metodyka per zadanie",
    "## 4. Przegląd gotowości issues pod night-run",
]

_LABEL_READY = "ready-for-agent"
_LABEL_HUMAN = "ready-for-human"
_LABEL_NEEDS_INFO = "needs-info"
_LABEL_TRIAGE = "needs-triage"
_LABEL_WONTFIX = "wontfix"
_LABEL_NEEDS_LOCAL = "needs-local"

_SKIP_LABELS = {_LABEL_HUMAN, _LABEL_NEEDS_INFO, _LABEL_TRIAGE, _LABEL_WONTFIX}

_EFFORT_RE = re.compile(r"\bkryteria\s+akceptacji\b|\bkryterium\s+uko[ńn]czenia\b", re.IGNORECASE)


@dataclass
class IssueInfo:
    """Dane jednego issue z listy."""

    number: int
    title: str
    labels: list[str] = field(default_factory=list)
    body: str = ""
    state: str = "open"
    merged_pr: bool = False  # Czy powiązane PR zmergowane na dev?

    @property
    def skip_label(self) -> str | None:
        for lbl in self.labels:
            if lbl in _SKIP_LABELS:
                return lbl
        return None

    @property
    def is_ready(self) -> bool:
        return _LABEL_READY in self.labels

    @property
    def needs_local(self) -> bool:
        return _LABEL_NEEDS_LOCAL in self.labels

    @property
    def acceptance_criteria_count(self) -> int:
        """Szacunkowa liczba kryteriów akceptacji z body issue."""
        if not self.body:
            return 0
        lines = [ln.strip() for ln in self.body.splitlines()]
        in_criteria = False
        count = 0
        for line in lines:
            if _EFFORT_RE.search(line):
                in_criteria = True
                continue
            if in_criteria:
                if line.startswith("## ") and not _EFFORT_RE.search(line):
                    in_criteria = False
                elif re.match(r"^[-*]\s+\S", line) or re.match(r"^\d+\.\s+\S", line):
                    count += 1
        return max(count, 0)

    @property
    def effort_label(self) -> str:
        cnt = self.acceptance_criteria_count
        if cnt <= 2:
            return "S (≤2 kryteria)"
        if cnt <= 4:
            return "M (3–4 kryteria)"
        return "L (>4 kryteria)"


def _gh_run(argv: list[str], cwd: Path) -> str:
    """Uruchom ``gh`` w katalogu ``cwd`` i zwróć stdout (lub pusty string)."""
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def fetch_issues(workspace: Path, gh_run: GhRun = _gh_run) -> list[IssueInfo]:
    """Pobierz otwarte issues przez ``gh issue list``."""
    raw = gh_run(
        [
            "gh", "issue", "list",
            "--state", "open",
            "--limit", "100",
            "--json", "number,title,labels,body,state",
        ],
        workspace,
    )
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []

    issues: list[IssueInfo] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        title = item.get("title", "")
        if not isinstance(number, int) or not isinstance(title, str):
            continue
        raw_labels = item.get("labels") or []
        labels: list[str] = []
        for lbl in raw_labels:
            if isinstance(lbl, dict):
                name = lbl.get("name", "")
                if isinstance(name, str) and name:
                    labels.append(name)
            elif isinstance(lbl, str) and lbl:
                labels.append(lbl)
        body = item.get("body") or ""
        state = item.get("state", "open")
        issues.append(IssueInfo(
            number=number,
            title=str(title),
            labels=labels,
            body=str(body),
            state=str(state),
        ))
    return issues


def detect_merged_issues(issues: list[IssueInfo], workspace: Path, gh_run: GhRun = _gh_run) -> None:
    """Oznacz issues, których powiązane PR zostały zmergowane na dev."""
    for issue in issues:
        raw = gh_run(
            [
                "gh", "pr", "list",
                "--state", "merged",
                "--search", f"#{issue.number}",
                "--json", "number,title,baseRefName",
                "--limit", "5",
            ],
            workspace,
        )
        if not raw.strip():
            continue
        try:
            prs: Any = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(prs, list):
            continue
        for pr in prs:
            if not isinstance(pr, dict):
                continue
            base = pr.get("baseRefName", "")
            if isinstance(base, str) and base in ("dev", "main", "master"):
                issue.merged_pr = True
                break


def _night_run_command(issue: IssueInfo) -> str:
    """Gotowa komenda ``/night-run`` dla issue."""
    return f"/night-run #{issue.number}"


def _gh_edit_command(issue: IssueInfo, action: str) -> str:
    """Gotowa komenda ``gh issue edit`` dla issue."""
    if action == "ready":
        return (
            f"gh issue edit {issue.number} "
            f"--remove-label needs-triage --add-label ready-for-agent"
        )
    if action == "skip":
        return (
            f"gh issue edit {issue.number} "
            f"--add-label wontfix"
        )
    return f"gh issue edit {issue.number}"


def render_report(issues: list[IssueInfo]) -> str:
    """Złóż raport z dokładnie 4 sekcjami."""
    # Partycja issues
    done: list[IssueInfo] = [i for i in issues if i.merged_pr]
    skipped: list[IssueInfo] = [i for i in issues if not i.merged_pr and i.skip_label]
    ready: list[IssueInfo] = [
        i for i in issues
        if not i.merged_pr and not i.skip_label and i.is_ready
    ]
    not_ready: list[IssueInfo] = [
        i for i in issues
        if not i.merged_pr and not i.skip_label and not i.is_ready
    ]

    lines: list[str] = []

    # Sekcja 1
    lines.append(SECTION_HEADERS[0])
    lines.append("")
    total = len(issues)
    lines.append(
        f"Łącznie issues: **{total}** "
        f"(zmergowane: {len(done)}, gotowe do agenta: {len(ready)}, "
        f"pominięte: {len(skipped)}, oczekujące: {len(not_ready)})"
    )
    lines.append("")

    if done:
        lines.append("### Kod już na dev (PR zmergowane)")
        lines.append("")
        lines.append("| # | Tytuł |")
        lines.append("|---|-------|")
        for i in done:
            lines.append(f"| #{i.number} | {i.title} |")
        lines.append("")

    if skipped:
        lines.append("### Pominięte (blokujące etykiety)")
        lines.append("")
        lines.append("| # | Tytuł | Etykieta |")
        lines.append("|---|-------|----------|")
        for i in skipped:
            lines.append(f"| #{i.number} | {i.title} | `{i.skip_label}` |")
        lines.append("")

    if not_ready:
        lines.append("### Oczekujące (bez `ready-for-agent`)")
        lines.append("")
        lines.append("| # | Tytuł | Etykiety |")
        lines.append("|---|-------|---------|")
        for i in not_ready:
            lbl_str = ", ".join(f"`{l}`" for l in i.labels) if i.labels else "—"
            lines.append(f"| #{i.number} | {i.title} | {lbl_str} |")
        lines.append("")

    if ready:
        lines.append("### Gotowe do realizacji (`ready-for-agent`)")
        lines.append("")
        lines.append("| # | Tytuł | Nakład | needs-local |")
        lines.append("|---|-------|--------|------------|")
        for i in ready:
            nl = "tak" if i.needs_local else "nie"
            lines.append(f"| #{i.number} | {i.title} | {i.effort_label} | {nl} |")
        lines.append("")

    # Sekcja 2
    lines.append(SECTION_HEADERS[1])
    lines.append("")
    if not ready:
        lines.append("Brak issues gotowych do agenta. Sprawdź sekcję 1.")
        lines.append("")
    else:
        lines.append(
            "Sugerowana kolejność: najpierw issues `S`, potem `M`, na końcu `L`. "
            "Issues z `needs-local` wymagają lokalnego środowiska."
        )
        lines.append("")
        priority = sorted(ready, key=lambda i: i.acceptance_criteria_count)
        lines.append("| Priorytet | # | Tytuł | Nakład | Komenda |")
        lines.append("|-----------|---|-------|--------|---------|")
        for rank, i in enumerate(priority, 1):
            cmd = _night_run_command(i)
            lines.append(f"| {rank} | #{i.number} | {i.title} | {i.effort_label} | `{cmd}` |")
        lines.append("")

    # Sekcja 3
    lines.append(SECTION_HEADERS[2])
    lines.append("")
    if not ready:
        lines.append("Brak issues do analizy.")
        lines.append("")
    else:
        for i in ready:
            lines.append(f"### #{i.number} — {i.title}")
            lines.append("")
            criteria = i.acceptance_criteria_count
            lines.append(f"- **Nakład:** {i.effort_label} ({criteria} kryteriów akceptacji)")
            if i.needs_local:
                lines.append("- **Wymaga lokalnego środowiska:** tak (etykieta `needs-local`)")
            lines.append(f"- **Skille:** `/git-start #{i.number}`, `/tdd`, `/git-commit`, `/git-end`")
            if criteria > 3:
                lines.append(
                    "- **Metodyka:** duży ticket (>3 kryteria) — plan 5–10 kroków przed implementacją"
                )
            else:
                lines.append(
                    "- **Metodyka:** standardowy TDD, test czerwony → kod → zielony → commit"
                )
            lines.append(f"- **Komenda night-run:** `{_night_run_command(i)}`")
            lines.append(f"- **Gotowe labels:** `{_gh_edit_command(i, 'ready')}`")
            lines.append("")

    # Sekcja 4
    lines.append(SECTION_HEADERS[3])
    lines.append("")
    if not ready:
        lines.append("Brak issues `ready-for-agent` do przeglądu.")
        lines.append("")
    else:
        lines.append(
            "| # | Tytuł | ready-for-agent | Kryterium ukończenia | needs-local | PR zmergowane | night-run |"
        )
        lines.append(
            "|---|-------|-----------------|---------------------|------------|---------------|-----------|"
        )
        for i in ready:
            has_criteria = "tak" if i.acceptance_criteria_count > 0 else "brak"
            nl = "tak" if i.needs_local else "—"
            merged = "tak" if i.merged_pr else "—"
            cmd = f"`{_night_run_command(i)}`"
            lines.append(
                f"| #{i.number} | {i.title} | ✓ | {has_criteria} | {nl} | {merged} | {cmd} |"
            )
        lines.append("")

    return "\n".join(lines)


def issue_stats_command(workspace: Path, gh_run: GhRun = _gh_run) -> str:
    """Główna logika komendy ``kit-ai issue stats``."""
    issues = fetch_issues(workspace, gh_run)
    if not issues:
        header = "\n".join(SECTION_HEADERS)
        return (
            "Brak otwartych issues.\n\n"
            + "\n\n(brak danych)\n\n".join(SECTION_HEADERS)
            + "\n\n(brak danych)\n"
        )
    detect_merged_issues(issues, workspace, gh_run)
    return render_report(issues)


def _parse_issue_dict(item: dict) -> IssueInfo:
    number = item.get("number", 0)
    title = str(item.get("title", ""))
    raw_labels = item.get("labels") or []
    labels: list[str] = []
    for lbl in raw_labels:
        if isinstance(lbl, dict):
            name = lbl.get("name", "")
            if isinstance(name, str) and name:
                labels.append(name)
        elif isinstance(lbl, str) and lbl:
            labels.append(lbl)
    body = str(item.get("body") or "")
    state = str(item.get("state", "open"))
    merged_pr = bool(item.get("merged_pr", False))
    return IssueInfo(
        number=number,
        title=title,
        labels=labels,
        body=body,
        state=state,
        merged_pr=merged_pr,
    )


def generate_issue_stats_report(issues: list[dict] | list[IssueInfo]) -> str:
    """Generuj 4-sekcyjny raport z listy słowników lub obiektów IssueInfo."""
    parsed: list[IssueInfo] = []
    for item in issues:
        if isinstance(item, IssueInfo):
            parsed.append(item)
        elif isinstance(item, dict):
            parsed.append(_parse_issue_dict(item))
    return render_report(parsed)


def run_issue_stats(repo_root: str | Path = ".") -> str:
    """Wywołaj gh issue list i wygeneruj 4-sekcyjny raport."""
    return issue_stats_command(Path(repo_root))
