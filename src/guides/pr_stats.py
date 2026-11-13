"""``kit-ai pr stats`` — inspekcja otwartych PR-ów.

Generuje raport z 3 sekcjami:
  1. Tabela PR (numer, tytuł, baza, autor, checks, review)
  2. Analiza ryzyk
  3. Rekomendowane akcje
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GhRun = Callable[[list[str], Path], str]

PR_SECTION_HEADERS = [
    "## 1. Tabela PR",
    "## 2. Analiza ryzyk",
    "## 3. Rekomendowane akcje",
]

_REVIEW_BOTS = {"coderabbit", "bugbot", "github-advanced-security", "copilot"}


def _clean_md(text: str) -> str:
    """Zabezpiecz tekst przed rozbiciem komórek tabeli Markdown."""
    return text.replace("|", "/").strip()


@dataclass
class CheckRun:
    """Stan jednego check runu PR."""

    name: str
    state: str  # SUCCESS | FAILURE | PENDING | SKIPPED | CANCELLED | ACTION_REQUIRED
    bucket: str  # pass | fail | pending | skipping | cancel


@dataclass
class Review:
    """Recenzja PR-a."""

    author: str
    state: str  # APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
    is_bot: bool = False


@dataclass
class PRInfo:
    """Dane jednego PR."""

    number: int
    title: str
    base_ref: str
    head_ref: str
    author: str
    state: str  # open | closed | merged
    is_draft: bool = False
    checks: list[CheckRun] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    mergeable: str = "UNKNOWN"  # MERGEABLE | CONFLICTING | UNKNOWN

    @property
    def clean_title(self) -> str:
        return _clean_md(self.title)

    @property
    def checks_summary(self) -> str:
        if not self.checks:
            return "brak"
        passed = sum(1 for c in self.checks if c.bucket in ("pass", "skipping") or c.state in ("SUCCESS", "SKIPPED"))
        failed = sum(1 for c in self.checks if c.bucket == "fail" or c.state in ("FAILURE", "ACTION_REQUIRED"))
        pending = sum(1 for c in self.checks if c.bucket == "pending" or c.state in ("PENDING", "QUEUED", "IN_PROGRESS", "STARTING"))
        parts = []
        if passed:
            parts.append(f"✓{passed}")
        if failed:
            parts.append(f"✗{failed}")
        if pending:
            parts.append(f"⌛{pending}")
        return " ".join(parts) if parts else "brak"

    @property
    def has_failing_checks(self) -> bool:
        return any(c.bucket == "fail" or c.state in ("FAILURE", "ACTION_REQUIRED") for c in self.checks)

    @property
    def has_pending_checks(self) -> bool:
        return any(c.bucket == "pending" or c.state in ("PENDING", "QUEUED", "IN_PROGRESS", "STARTING") for c in self.checks)

    @property
    def has_passed_checks(self) -> bool:
        return bool(self.checks) and all(c.bucket in ("pass", "skipping") or c.state in ("SUCCESS", "SKIPPED") for c in self.checks)

    @property
    def review_summary(self) -> str:
        if not self.reviews:
            return "brak"
        approved = sum(1 for r in self.reviews if r.state == "APPROVED")
        changes = sum(1 for r in self.reviews if r.state == "CHANGES_REQUESTED")
        bots = sum(1 for r in self.reviews if r.is_bot)
        parts = []
        if approved:
            parts.append(f"approved:{approved}")
        if changes:
            parts.append(f"changes:{changes}")
        if bots:
            parts.append(f"bot:{bots}")
        return " ".join(parts) if parts else "komentarze"

    @property
    def is_bot_reviewed(self) -> bool:
        return any(r.is_bot for r in self.reviews)

    @property
    def has_human_approval(self) -> bool:
        return any(r.state == "APPROVED" and not r.is_bot for r in self.reviews)

    @property
    def has_changes_requested(self) -> bool:
        return any(r.state == "CHANGES_REQUESTED" for r in self.reviews)

    @property
    def risk_level(self) -> str:
        """Szacunkowy poziom ryzyka merge."""
        if self.has_failing_checks:
            return "HIGH"
        if self.has_changes_requested:
            return "HIGH"
        if self.mergeable == "CONFLICTING":
            return "HIGH"
        if self.has_pending_checks:
            return "MEDIUM"
        if not self.checks:  # niezweryfikowane CI
            return "MEDIUM"
        if not self.has_human_approval:
            return "MEDIUM"
        return "LOW"


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


def _is_bot(login: str) -> bool:
    """Czy author to znany bot review."""
    low = login.lower()
    return any(bot in low for bot in _REVIEW_BOTS) or low.endswith("[bot]")


def fetch_prs(workspace: Path, gh_run: GhRun = _gh_run) -> tuple[list[PRInfo], bool]:
    """Pobierz otwarte PR-y przez ``gh pr list``. Zwraca (prs, is_partial)."""
    raw = gh_run(
        [
            "gh", "pr", "list",
            "--state", "open",
            "--limit", "100",
            "--json",
            "number,title,baseRefName,headRefName,author,state,isDraft,mergeable",
        ],
        workspace,
    )
    if not raw.strip():
        return [], False
    try:
        data: Any = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return [], False
    if not isinstance(data, list):
        return [], False

    prs: list[PRInfo] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        title = item.get("title", "")
        if not isinstance(number, int):
            continue
        author_raw = item.get("author") or {}
        author = author_raw.get("login", "unknown") if isinstance(author_raw, dict) else str(author_raw)
        pr = PRInfo(
            number=number,
            title=str(title),
            base_ref=str(item.get("baseRefName", "")),
            head_ref=str(item.get("headRefName", "")),
            author=str(author),
            state=str(item.get("state", "open")),
            is_draft=bool(item.get("isDraft", False)),
            mergeable=str(item.get("mergeable", "UNKNOWN")),
        )
        prs.append(pr)
    is_partial = len(prs) >= 100
    return prs, is_partial


def fetch_pr_checks(pr: PRInfo, workspace: Path, gh_run: GhRun = _gh_run) -> None:
    """Uzupełnij check runy PR za pomocą obsługiwanych pól name,state,bucket."""
    try:
        raw = gh_run(
            [
                "gh", "pr", "checks", str(pr.number),
                "--json", "name,state,bucket",
            ],
            workspace,
        )
    except RuntimeError:
        return
    if not raw.strip():
        return
    try:
        data: Any = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(data, list):
        return
    pr.checks = [
        CheckRun(
            name=str(c.get("name", "")),
            state=str(c.get("state", "PENDING")),
            bucket=str(c.get("bucket", "pending")),
        )
        for c in data
        if isinstance(c, dict)
    ]


def fetch_pr_reviews(pr: PRInfo, workspace: Path, gh_run: GhRun = _gh_run) -> None:
    """Uzupełnij recenzje PR na podstawie latestReviews (aktualny stan, nie historia)."""
    try:
        raw = gh_run(
            [
                "gh", "pr", "view", str(pr.number),
                "--json", "latestReviews",
            ],
            workspace,
        )
    except RuntimeError:
        return
    if not raw.strip():
        return
    try:
        data: Any = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(data, dict):
        return
    reviews_raw = data.get("latestReviews") or []
    pr.reviews = [
        Review(
            author=str((r.get("author") or {}).get("login", "unknown")),
            state=str(r.get("state", "COMMENTED")),
            is_bot=_is_bot(str((r.get("author") or {}).get("login", ""))),
        )
        for r in reviews_raw
        if isinstance(r, dict)
    ]


def render_pr_report(prs: list[PRInfo], is_partial: bool = False) -> str:
    """Złóż raport PR z 3 sekcjami."""
    lines: list[str] = []

    # Sekcja 1: Tabela PR
    lines.append(PR_SECTION_HEADERS[0])
    lines.append("")
    if is_partial:
        lines.append("> [!NOTE] Pobrano pierwsze 100 PR-ów (limit zapytania).")
        lines.append("")
    if not prs:
        lines.append("Brak otwartych PR-ów.")
        lines.append("")
    else:
        lines.append("| # | Tytuł | Baza | Autor | Draft | Checks | Review | Mergeable | Ryzyko |")
        lines.append("|---|-------|------|-------|-------|--------|--------|-----------|--------|")
        for pr in prs:
            draft = "tak" if pr.is_draft else "—"
            lines.append(
                f"| #{pr.number} | {pr.clean_title} | `{pr.base_ref}` | {pr.author} | {draft} "
                f"| {pr.checks_summary} | {pr.review_summary} | {pr.mergeable} | {pr.risk_level} |"
            )
        lines.append("")

    # Sekcja 2: Analiza ryzyk
    lines.append(PR_SECTION_HEADERS[1])
    lines.append("")
    if not prs:
        lines.append("Brak PR-ów do analizy.")
        lines.append("")
    else:
        high = [pr for pr in prs if pr.risk_level == "HIGH"]
        medium = [pr for pr in prs if pr.risk_level == "MEDIUM"]
        low = [pr for pr in prs if pr.risk_level == "LOW"]

        lines.append(f"- **HIGH ({len(high)}):** {_pr_list(high)}")
        lines.append(f"- **MEDIUM ({len(medium)}):** {_pr_list(medium)}")
        lines.append(f"- **LOW ({len(low)}):** {_pr_list(low)}")
        lines.append("")

        if high:
            lines.append("#### Szczegóły HIGH")
            lines.append("")
            for pr in high:
                reasons = []
                if pr.has_failing_checks:
                    reasons.append("failing checks")
                if pr.has_changes_requested:
                    reasons.append("CHANGES_REQUESTED")
                if pr.mergeable == "CONFLICTING":
                    reasons.append("konflikty merge")
                lines.append(f"- **#{pr.number}** {pr.clean_title}: {', '.join(reasons)}")
            lines.append("")

        if medium:
            lines.append("#### Szczegóły MEDIUM")
            lines.append("")
            for pr in medium:
                reasons = []
                if pr.has_pending_checks:
                    reasons.append("pending checks")
                if not pr.checks:
                    reasons.append("brak danych CI / checks")
                if not pr.has_human_approval:
                    reasons.append("brak human approval")
                lines.append(f"- **#{pr.number}** {pr.clean_title}: {', '.join(reasons)}")
            lines.append("")

    # Sekcja 3: Rekomendowane akcje
    lines.append(PR_SECTION_HEADERS[2])
    lines.append("")
    if not prs:
        lines.append("Brak PR-ów do rekomendacji.")
        lines.append("")
    else:
        merge_ready = [
            pr for pr in prs
            if pr.risk_level == "LOW" and not pr.is_draft and pr.mergeable == "MERGEABLE"
        ]
        needs_fix = [pr for pr in prs if pr.has_failing_checks]
        needs_review = [pr for pr in prs if not pr.has_human_approval and not pr.is_draft]
        conflicts = [pr for pr in prs if pr.mergeable == "CONFLICTING"]

        if merge_ready:
            lines.append("### Gotowe do merge")
            lines.append("")
            for pr in merge_ready:
                lines.append(f"- `gh pr merge {pr.number} --merge`  # #{pr.number} {pr.clean_title}")
            lines.append("")

        if conflicts:
            lines.append("### Konflikty do rozwiązania")
            lines.append("")
            for pr in conflicts:
                lines.append(
                    f"- `gh pr checkout {pr.number} && git merge origin/{pr.base_ref}`"
                    f"  # #{pr.number} {pr.clean_title}"
                )
            lines.append("")

        if needs_fix:
            lines.append("### Failing checks — wymagają naprawy")
            lines.append("")
            for pr in needs_fix:
                failing = [c.name for c in pr.checks if c.bucket == "fail" or c.state in ("FAILURE", "ACTION_REQUIRED")]
                lines.append(
                    f"- **#{pr.number}** {pr.clean_title}: `gh pr checks {pr.number}` "
                    f"(failing: {', '.join(failing[:3])})"
                )
            lines.append("")

        if needs_review:
            lines.append("### Oczekują na review człowieka")
            lines.append("")
            for pr in needs_review:
                lines.append(f"- **#{pr.number}** {pr.clean_title}: `gh pr view {pr.number}`")
            lines.append("")

    return "\n".join(lines)


def _pr_list(prs: list[PRInfo]) -> str:
    if not prs:
        return "—"
    return ", ".join(f"#{pr.number}" for pr in prs)


def pr_stats_command(workspace: Path, gh_run: GhRun = _gh_run) -> str:
    """Główna logika komendy ``kit-ai pr stats``."""
    try:
        prs, is_partial = fetch_prs(workspace, gh_run)
    except RuntimeError as err:
        return f"Błąd GitHub CLI podczas pobierania PR-ów: {err}\n"

    if not prs:
        empty_lines = [
            PR_SECTION_HEADERS[0],
            "",
            "Brak otwartych PR-ów w repozytorium.",
            "",
            PR_SECTION_HEADERS[1],
            "",
            "Brak PR-ów do analizy ryzyk.",
            "",
            PR_SECTION_HEADERS[2],
            "",
            "Brak rekomendacji dla otwartych PR-ów.",
            "",
        ]
        return "\n".join(empty_lines)

    for pr in prs:
        fetch_pr_checks(pr, workspace, gh_run)
        fetch_pr_reviews(pr, workspace, gh_run)
    return render_pr_report(prs, is_partial=is_partial)


def _parse_pr_dict(item: dict) -> PRInfo:
    number = item.get("number", 0)
    title = str(item.get("title", ""))
    base_ref = str(item.get("baseRefName") or item.get("base_ref") or "dev")
    head_ref = str(item.get("headRefName") or item.get("head_ref") or "")
    author_val = item.get("author") or {}
    author = author_val.get("login", "unknown") if isinstance(author_val, dict) else str(author_val)
    state = str(item.get("state", "open"))
    is_draft = bool(item.get("isDraft") if "isDraft" in item else item.get("is_draft", False))
    mergeable = str(item.get("mergeable", "UNKNOWN"))
    checks_raw = item.get("checks") or []
    checks: list[CheckRun] = []
    for c in checks_raw:
        if isinstance(c, CheckRun):
            checks.append(c)
        elif isinstance(c, dict):
            checks.append(CheckRun(
                name=str(c.get("name", "")),
                state=str(c.get("state") or c.get("status") or "SUCCESS"),
                bucket=str(c.get("bucket", "pass")),
            ))
    reviews_raw = item.get("reviews") or []
    reviews: list[Review] = []
    for r in reviews_raw:
        if isinstance(r, Review):
            reviews.append(r)
        elif isinstance(r, dict):
            rev_author = r.get("author")
            rev_login = rev_author.get("login", "") if isinstance(rev_author, dict) else str(rev_author or "")
            rev_state = str(r.get("state", "COMMENTED"))
            reviews.append(Review(
                author=rev_login,
                state=rev_state,
                is_bot=_is_bot(rev_login),
            ))
    pr = PRInfo(
        number=number,
        title=title,
        base_ref=base_ref,
        head_ref=head_ref,
        author=author,
        state=state,
        is_draft=is_draft,
        mergeable=mergeable,
    )
    pr.checks = checks
    pr.reviews = reviews
    return pr


def generate_pr_stats_report(prs: list[dict] | list[PRInfo]) -> str:
    """Generuj 3-sekcyjny raport z listy słowników lub obiektów PRInfo."""
    parsed: list[PRInfo] = []
    for item in prs:
        if isinstance(item, PRInfo):
            parsed.append(item)
        elif isinstance(item, dict):
            parsed.append(_parse_pr_dict(item))
    return render_pr_report(parsed)


def run_pr_stats(repo_root: str | Path = ".") -> str:
    """Wywołaj gh pr list i wygeneruj 3-sekcyjny raport."""
    return pr_stats_command(Path(repo_root))
