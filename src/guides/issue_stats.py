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
_DEP_RE = re.compile(
    r"(?:zale[żz]y\s+od|wymaga|po|depends\s+on|blocked\s+by|prerequisite:?|parent:?|sub-issue\s+pod)\s+#?(\d+)",
    re.IGNORECASE,
)


def _clean_md(text: str) -> str:
    """Zabezpiecz tekst przed rozbiciem komórek tabeli Markdown."""
    return text.replace("|", "/").strip()


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
    def clean_title(self) -> str:
        return _clean_md(self.title)

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
    def issue_type(self) -> str:
        for lbl in self.labels:
            if lbl.startswith("type: "):
                return lbl.removeprefix("type: ")
            if lbl in ("bug", "enhancement"):
                return lbl
        return "inne"

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
                if re.match(r"^#{1,6}\s+", line) and not _EFFORT_RE.search(line):
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

    @property
    def estimated_minutes(self) -> str:
        cnt = self.acceptance_criteria_count
        if cnt <= 2:
            return "5–15 min"
        if cnt <= 4:
            return "15–30 min"
        return "30–60 min"

    @property
    def dependencies(self) -> list[int]:
        """Numery innych issues, od których to issue zależy."""
        if not self.body:
            return []
        deps: list[int] = []
        for line in self.body.splitlines():
            for match in _DEP_RE.finditer(line):
                try:
                    num = int(match.group(1))
                    if num != self.number and num not in deps:
                        deps.append(num)
                except ValueError:
                    continue
        return deps

    @property
    def open_questions(self) -> list[str]:
        """Wykryj sekcję 'Otwarte pytania' lub pytania blokujące."""
        if not self.body:
            return []
        questions: list[str] = []
        in_q_section = False
        for line in self.body.splitlines():
            s = line.strip()
            if re.search(r"\botwarte\s+pytani[ae]\b", s, re.IGNORECASE):
                in_q_section = True
                continue
            if in_q_section:
                if re.match(r"^#{1,6}\s+", s):
                    in_q_section = False
                elif s.startswith("- ") or s.startswith("* ") or s.endswith("?"):
                    q = s.lstrip("-* ").strip()
                    if q:
                        questions.append(_clean_md(q))
            elif "?" in s and not s.startswith("http") and not s.startswith("<!--"):
                questions.append(_clean_md(s.lstrip("-* ").strip()))
        return questions


def _gh_run(argv: list[str], cwd: Path) -> str:
    """Uruchom ``gh`` w katalogu ``cwd`` i zwróć stdout. Podnosi RuntimeError przy błędzie."""
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as err:
        raise RuntimeError(f"Nie można uruchomić gh: {err}") from err
    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or f"gh zakończony kodem {proc.returncode}"
        raise RuntimeError(f"Błąd gh: {err_msg}")
    return proc.stdout


def fetch_issues(workspace: Path, gh_run: GhRun = _gh_run) -> tuple[list[IssueInfo], bool]:
    """Pobierz otwarte issues przez ``gh issue list``. Zwraca (issues, is_partial)."""
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
        return [], False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return [], False
    if not isinstance(data, list):
        return [], False

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
    is_partial = len(issues) >= 100
    return issues, is_partial


def detect_merged_issues(issues: list[IssueInfo], workspace: Path, gh_run: GhRun = _gh_run) -> None:
    """Oznacz issues, których powiązane PR zostały faktycznie zmergowane na dev."""
    for issue in issues:
        try:
            raw = gh_run(
                [
                    "gh", "pr", "list",
                    "--state", "merged",
                    "--search", f"#{issue.number}",
                    "--json", "number,title,baseRefName,headRefName,body",
                    "--limit", "5",
                ],
                workspace,
            )
        except RuntimeError:
            continue
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
                pr_title = str(pr.get("title", ""))
                pr_head = str(pr.get("headRefName", ""))
                pr_body = str(pr.get("body", ""))

                # Weryfikacja rzeczywistego powiązania (a nie przypadkowego wspomnienia)
                num_pattern = str(issue.number)
                title_linked = (
                    f"#{num_pattern}" in pr_title
                    or f"({num_pattern})" in pr_title
                )
                branch_linked = bool(
                    re.search(rf"[/-]{num_pattern}(?:[-/]|$)", pr_head)
                )
                body_linked = bool(
                    re.search(
                        rf"(?i)\b(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+[:#]?\s*{num_pattern}\b",
                        pr_body,
                    )
                    or re.search(rf"(?i)issues?/{num_pattern}\b", pr_body)
                )

                if title_linked or branch_linked or body_linked:
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
            f"--remove-label ready-for-human --remove-label needs-triage --add-label ready-for-agent"
        )
    if action == "skip":
        return (
            f"gh issue edit {issue.number} --add-label wontfix"
        )
    return f"gh issue edit {issue.number}"


def _sort_with_dependencies(ready: list[IssueInfo]) -> list[IssueInfo]:
    """Sortuj zadania gotowe uwzględniając zależności, a następnie nakład prac (S przed M przed L)."""
    ready_by_num = {i.number: i for i in ready}
    visited: set[int] = set()
    order: list[IssueInfo] = []

    def visit(issue: IssueInfo) -> None:
        if issue.number in visited:
            return
        visited.add(issue.number)
        # Najpierw odwiedź warunki wstępne, które są w liście ready
        for dep_num in issue.dependencies:
            if dep_num in ready_by_num and dep_num not in visited:
                visit(ready_by_num[dep_num])
        order.append(issue)

    # Sortuj wstępnie wg liczby kryteriów akceptacji (S -> M -> L)
    effort_sorted = sorted(ready, key=lambda i: i.acceptance_criteria_count)
    for i in effort_sorted:
        visit(i)

    return order


def render_report(issues: list[IssueInfo], is_partial: bool = False) -> str:
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
    if is_partial:
        lines.append("")
        lines.append("> [!NOTE] Pobrano pierwsze 100 issues (limit zapytania). Backlog może zawierać więcej zgłoszeń.")
    lines.append("")

    if done:
        lines.append("### Kod już na dev (PR zmergowane)")
        lines.append("")
        lines.append("| # | Tytuł | Typ | Etykiety | Stan faktyczny |")
        lines.append("|---|-------|-----|----------|----------------|")
        for i in done:
            lbl_str = ", ".join(f"`{l}`" for l in i.labels) if i.labels else "—"
            lines.append(f"| #{i.number} | {i.clean_title} | {i.issue_type} | {lbl_str} | zmergowane na dev |")
        lines.append("")

    if skipped:
        lines.append("### Pominięte (blokujące etykiety)")
        lines.append("")
        lines.append("| # | Tytuł | Typ | Etykieta | Powód pominięcia |")
        lines.append("|---|-------|-----|----------|------------------|")
        for i in skipped:
            lines.append(f"| #{i.number} | {i.clean_title} | {i.issue_type} | `{i.skip_label}` | blokada triage |")
        lines.append("")

    if not_ready:
        lines.append("### Oczekujące (bez `ready-for-agent`)")
        lines.append("")
        lines.append("| # | Tytuł | Typ | Etykiety | Status przygotowania |")
        lines.append("|---|-------|-----|----------|----------------------|")
        for i in not_ready:
            lbl_str = ", ".join(f"`{l}`" for l in i.labels) if i.labels else "—"
            status = "wymaga grillowania / decyzji" if i.open_questions else "brak etykiety ready-for-agent"
            lines.append(f"| #{i.number} | {i.clean_title} | {i.issue_type} | {lbl_str} | {status} |")
        lines.append("")

    if ready:
        lines.append("### Gotowe do realizacji (`ready-for-agent`)")
        lines.append("")
        lines.append("| # | Tytuł | Typ | Nakład | needs-local | Gotowość |")
        lines.append("|---|-------|-----|--------|------------|----------|")
        for i in ready:
            nl = "tak" if i.needs_local else "nie"
            lines.append(f"| #{i.number} | {i.clean_title} | {i.issue_type} | {i.effort_label} | {nl} | ready-for-agent |")
        lines.append("")

    # Sekcja 2
    lines.append(SECTION_HEADERS[1])
    lines.append("")
    if not ready:
        lines.append("Brak issues gotowych do agenta. Sprawdź sekcję 1 i sekcję 4.")
        lines.append("")
    else:
        priority = _sort_with_dependencies(ready)

        # Graf zależności (ASCII)
        has_deps = any(i.dependencies for i in priority)
        lines.append("### Graf przepływu i zależności")
        lines.append("")
        lines.append("```text")
        if has_deps:
            for i in priority:
                if i.dependencies:
                    dep_str = ", ".join(f"#{d}" for d in i.dependencies)
                    lines.append(f"[{dep_str}] ───► [#{i.number}: {i.clean_title}]")
                else:
                    lines.append(f"[Start] ───► [#{i.number}: {i.clean_title}]")
        else:
            flow_items = " ──► ".join(f"#{i.number}" for i in priority)
            lines.append(f"[Start] ──► {flow_items} ──► [Wdrożone]")
        lines.append("```")
        lines.append("")

        lines.append("### Uzasadnienie kolejności")
        lines.append("")
        if has_deps:
            lines.append(
                "Kolejność uwzględnia warunki wstępne (zadania zależne następują po zadaniach bazowych). "
                "Wśród zadań niezależnych priorytet mają mniejsze moduły (S przed M przed L) "
                "oraz fundamenty infrastrukturalne."
            )
        else:
            lines.append(
                "Zadania są niezależne. Kolejność wynika z minimalizacji ryzyka i natychmiastowego zysku "
                "z dźwigni narzędziowej: najpierw zadania `S` (szybki feedback), następnie `M` i `L`."
            )
        lines.append("")

        lines.append("| Priorytet | # | Tytuł | Typ | Nakład | Zależności | Komenda |")
        lines.append("|-----------|---|-------|-----|--------|------------|---------|")
        for rank, i in enumerate(priority, 1):
            cmd = _night_run_command(i)
            deps = ", ".join(f"#{d}" for d in i.dependencies) if i.dependencies else "brak"
            lines.append(
                f"| {rank} | #{i.number} | {i.clean_title} | {i.issue_type} | {i.effort_label} | {deps} | `{cmd}` |"
            )
        lines.append("")

    # Sekcja 3
    lines.append(SECTION_HEADERS[2])
    lines.append("")
    active_issues = [i for i in issues if not i.merged_pr and i.skip_label != _LABEL_WONTFIX]
    if not active_issues:
        lines.append("Brak aktywnych issues do analizy metodyki.")
        lines.append("")
    else:
        for i in active_issues:
            lines.append(f"### #{i.number} — {i.clean_title}")
            lines.append("")
            criteria = i.acceptance_criteria_count
            lines.append(f"- **Typ:** {i.issue_type} | **Nakład:** {i.effort_label} ({criteria} kryteriów akceptacji, szacunek: {i.estimated_minutes})")
            if i.needs_local:
                lines.append("- **Środowisko:** wymaga lokalnej weryfikacji (`needs-local`)")
            if i.dependencies:
                lines.append(f"- **Wymaga wcześniejszego wykonania:** {', '.join(f'#{d}' for d in i.dependencies)}")
            lines.append("- **Pełna procedura i skille:**")
            if not i.is_ready:
                lines.append(f"  1. *Scope & Alignment:* `/grill-me` (wyjaśnienie otwartych pytań i nadanie `ready-for-agent`)")
            else:
                lines.append(f"  1. *Scope & Alignment:* pominięte (gotowa specyfikacja `ready-for-agent`)")
            lines.append(f"  2. *Start i izolacja:* `/git-start #{i.number}` (+ opcjonalny worktree)")
            lines.append(f"  3. *Implementacja:* `/tdd` (czerwony test → implementacja → zielony → refactor)")
            lines.append(f"  4. *Commit:* `/git-commit` (Conventional Commits)")
            lines.append(f"  5. *Code Review:* `/review-bugbot` + review domenowe (`/review-backend` / `/review-frontend`)")
            lines.append(f"  6. *Finisz:* `/git-end` (lub Superpowers finishing → PR → merge)")
            lines.append(f"- **Komenda night-run:** `{_night_run_command(i)}`")
            if not i.is_ready:
                lines.append(f"- **Gotowe polecenie zmiany etykiety:** `{_gh_edit_command(i, 'ready')}`")
            lines.append("")

    # Sekcja 4
    lines.append(SECTION_HEADERS[3])
    lines.append("")
    unresolved = [i for i in issues if not i.merged_pr and i.skip_label != _LABEL_WONTFIX]
    if not unresolved:
        lines.append("Brak otwartych issues do przeglądu.")
        lines.append("")
    else:
        lines.append("### Tabela gotowości i analizy nakładu pracy")
        lines.append("")
        lines.append(
            "| # | Tytuł | Stan | Nakład (min) | Kryteria | needs-local | Pytania blokujące | Następny krok |"
        )
        lines.append(
            "|---|-------|------|--------------|----------|------------|-------------------|---------------|"
        )
        for i in unresolved:
            stan = "ready-for-agent" if i.is_ready else (i.skip_label or "oczekujące")
            has_crit = f"tak ({i.acceptance_criteria_count})" if i.acceptance_criteria_count > 0 else "brak"
            nl = "tak" if i.needs_local else "—"
            q_count = f"{len(i.open_questions)} pytań" if i.open_questions else "brak"
            if i.is_ready:
                next_step = "gotowe do `/night-run`"
            elif i.open_questions:
                next_step = "zamknąć pytania + `ready-for-agent`"
            else:
                next_step = "nadać `ready-for-agent`"
            lines.append(
                f"| #{i.number} | {i.clean_title} | `{stan}` | {i.estimated_minutes} | {has_crit} | {nl} | {q_count} | {next_step} |"
            )
        lines.append("")

        # Zadania wymagające przygotowania przed night-run
        needs_prep = [i for i in unresolved if not i.is_ready]
        if needs_prep:
            lines.append("### Przygotowanie zadań pod night-run (zdjęcie blokad)")
            lines.append("")
            for i in needs_prep:
                lines.append(f"#### #{i.number} — {i.clean_title}")
                if i.open_questions:
                    lines.append("- **Pytania do rozstrzygnięcia:**")
                    for q in i.open_questions[:4]:
                        lines.append(f"  - {q}")
                lines.append(f"- **Polecenie nadania gotowości:** `{_gh_edit_command(i, 'ready')}`")
                lines.append("")

        # Rekomendacja segmentacji
        lines.append("### Rekomendowane segmenty night-run")
        lines.append("")
        ready_ordered = _sort_with_dependencies(ready) if ready else []
        if ready_ordered:
            # Segmentacja: zadania solo (S lub infrastruktura), duety/zależne
            solo: list[IssueInfo] = [i for i in ready_ordered if i.acceptance_criteria_count <= 2 and not i.dependencies]
            dependent_or_heavy: list[IssueInfo] = [i for i in ready_ordered if i not in solo]

            segment_idx = 1
            if solo:
                solo_cmds = " ".join(f"#{i.number}" for i in solo)
                lines.append(f"- **Segment {segment_idx} (szybkie / niezależne):** `/night-run {solo_cmds} /review-bugbot`")
                segment_idx += 1
            if dependent_or_heavy:
                dep_cmds = " ".join(f"#{i.number}" for i in dependent_or_heavy)
                lines.append(f"- **Segment {segment_idx} (złożone / powiązane):** `/night-run {dep_cmds} /review-bugbot`")
            lines.append("")
            all_cmds = " ".join(f"#{i.number}" for i in ready_ordered)
            lines.append(f"**Łączna komenda dla wszystkich gotowych:** `/night-run {all_cmds} /review-bugbot`")
        else:
            lines.append("Brak zadań z etykietą `ready-for-agent`. Przygotuj zadania powyższymi komendami.")
        lines.append("")

    return "\n".join(lines)


def issue_stats_command(workspace: Path, gh_run: GhRun = _gh_run) -> str:
    """Główna logika komendy ``kit-ai issue stats``."""
    try:
        issues, is_partial = fetch_issues(workspace, gh_run)
    except RuntimeError as err:
        return f"Błąd GitHub CLI podczas pobierania issues: {err}\n"

    if not issues:
        empty_lines = [
            SECTION_HEADERS[0],
            "",
            "Brak otwartych issues w repozytorium.",
            "",
            SECTION_HEADERS[1],
            "",
            "Brak otwartych issues do zaplanowania.",
            "",
            SECTION_HEADERS[2],
            "",
            "Brak otwartych issues do analizy.",
            "",
            SECTION_HEADERS[3],
            "",
            "Brak otwartych issues do przeglądu.",
            "",
        ]
        return "\n".join(empty_lines)

    detect_merged_issues(issues, workspace, gh_run)
    return render_report(issues, is_partial=is_partial)


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
