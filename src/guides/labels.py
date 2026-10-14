"""Provisioning etykiet GitHuba z zestawu kita (``templates/shared/labels.tsv``, #187).

Zakłada tylko brakujące etykiety, istniejących nie rusza (żadnego ``--force``).
Etykiety stanu biorą nazwy z ``docs/agents/triage-labels.md`` projektu, gdy jest —
to słownik skilli mattpocock, kit go konsumuje, nie definiuje.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from guides.clients import expand_clients, parse_clients
from guides.resolver import PROFILE_REL_PATH, TIER_NONE, resolve_workspace_profile

LABELS_REL_PATH = Path("templates/shared/labels.tsv")
TRIAGE_REL_PATH = Path("docs/agents/triage-labels.md")
STATE_LABELS = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")
# Ten sam limit w agentach (`gh label list --limit 200`) — inaczej agent i provisioning
# różnie widzą, co istnieje.
LIST_LIMIT = "200"
_GH_TIMEOUT_SECONDS = 30
# Sesję designu robi człowiek w Claude Code (#189) — bez `claude` w `clients:` etykiety
# `design: *` nie miałyby kto obsłużyć.
DESIGN_PREFIX = "design: "
DESIGN_CLIENT = "claude"

Runner = Callable[[list[str]], subprocess.CompletedProcess]


class LabelsError(RuntimeError):
    """``gh`` niedostępne, bez auth/remote albo nie odpowiada — komunikat w jednej linii."""


@dataclass(frozen=True)
class Label:
    """Wiersz ``labels.tsv``: ``when`` = ``always`` albo Tiery po przecinku."""

    name: str
    color: str
    description: str
    when: str

    def active(self, tiers: dict[str, str], clients: set[str]) -> bool:
        """Etykieta potrzebna przy tych Tierach (którykolwiek z ``when`` ≠ ``none``) i klientach."""
        if self.name.startswith(DESIGN_PREFIX) and DESIGN_CLIENT not in clients:
            return False
        if self.when == "always":
            return True
        return any(
            tiers.get(tier.strip(), TIER_NONE) != TIER_NONE for tier in self.when.split(",")
        )


def read_label_set(kit_root: Path) -> list[Label]:
    """Kanoniczny zestaw etykiet kita."""
    path = kit_root / LABELS_REL_PATH
    labels = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) != 4:
            raise ValueError(f"{path}:{number}: oczekiwane 4 kolumny (TAB), jest {len(cols)}")
        labels.append(Label(*cols))
    return labels


def triage_names(root: Path) -> dict[str, str]:
    """Rola triage → nazwa etykiety z prawej kolumny ``triage-labels.md`` (brak pliku = ``{}``)."""
    path = root / TRIAGE_REL_PATH
    if not path.is_file():
        return {}
    names: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip().strip("`").strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in STATE_LABELS and cells[1]:
            names[cells[0]] = cells[1]
    return names


def project_clients(workspace: Path) -> set[str]:
    """Klienci z ``clients:`` Profilu (string albo lista YAML; brak = wszyscy)."""
    path = workspace / PROFILE_REL_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    raw = data.get("clients") if isinstance(data, dict) else None
    if isinstance(raw, list):
        raw = ",".join(str(item) for item in raw)
    return set(expand_clients(parse_clients(str(raw) if raw else None)))


def _gh(run: Runner, args: list[str]) -> subprocess.CompletedProcess:
    """Wywołaj ``gh``; każdy błąd jako :class:`LabelsError` z jedną linią."""
    try:
        result = run(["gh", *args])
    except FileNotFoundError:
        raise LabelsError("labels: brak `gh` — zainstaluj GitHub CLI i `gh auth login`.") from None
    except subprocess.TimeoutExpired:
        raise LabelsError(
            f"labels: `gh {args[0]} {args[1]}` nie odpowiada po {_GH_TIMEOUT_SECONDS} s."
        ) from None
    if result.returncode != 0:
        first = next((ln for ln in (result.stderr or "").splitlines() if ln.strip()), "")
        raise LabelsError(
            f"labels: `gh {args[0]} {args[1]}` nie działa (auth / remote GitHub?): {first.strip()}"
        )
    return result


def _run_gh(workspace: Path) -> Runner:
    def run(args: list[str]) -> subprocess.CompletedProcess:
        # stdin=DEVNULL: pod serwerem MCP dziecko dziedziczy potok bez EOF i `gh`
        # czekające na wejście wisi (ten sam powód co w kit_status._git).
        return subprocess.run(
            args, cwd=workspace, capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=_GH_TIMEOUT_SECONDS,
        )

    return run


def ensure_labels(
    workspace: Path,
    kit_root: Path,
    *,
    dry_run: bool = True,
    run: Runner | None = None,
    tiers: dict[str, str] | None = None,
    clients: set[str] | None = None,
) -> str:
    """
    Załóż w repo GitHuba brakujące etykiety kita.

    Args:
        workspace: Repo aplikacji (Profil + opcjonalnie ``docs/agents/triage-labels.md``).
        kit_root: Root kita (``labels.tsv``).
        dry_run: ``True`` — tylko plan, bez ``gh label create``.
        run: Runner komend (domyślnie ``subprocess.run`` w ``workspace``).
        tiers: Tiery projektu; ``None`` = z Profilu.
        clients: Klienci projektu; ``None`` = ``clients:`` z Profilu.

    Returns:
        str: Licznik ``created/to create, existing, skipped (Tier none)`` + nazwy.

    Raises:
        LabelsError: Brak ``gh``, auth albo remote GitHub, timeout.
    """
    run = run or _run_gh(workspace)

    if tiers is None:
        tiers = resolve_workspace_profile(workspace, kit_root=kit_root).tiers
    if clients is None:
        clients = project_clients(workspace)
    mapped = triage_names(workspace)
    labels = [replace(lb, name=mapped.get(lb.name, lb.name)) for lb in read_label_set(kit_root)]
    wanted = [lb for lb in labels if lb.active(tiers, clients)]
    skipped = [lb for lb in labels if not lb.active(tiers, clients)]

    listed = _gh(run, ["label", "list", "--limit", LIST_LIMIT, "--json", "name"])
    existing = {item["name"].lower() for item in json.loads(listed.stdout or "[]")}
    missing = [lb for lb in wanted if lb.name.lower() not in existing]

    if not dry_run:
        for count, lb in enumerate(missing):
            try:
                _gh(run, ["label", "create", lb.name, "--color", lb.color,
                          "--description", lb.description])
            except LabelsError as exc:
                raise LabelsError(f"{exc} (utworzone wcześniej: {count})") from None

    verb = "to create" if dry_run else "created"
    lines = [
        f"{verb}: {len(missing)}, existing: {len(wanted) - len(missing)}, "
        f"skipped (Tier none / bez claude): {len(skipped)}",
        *(f"+ {lb.name}" for lb in missing),
        *(f"- {lb.name} (Tier none / bez claude)" for lb in skipped),
    ]
    return "\n".join(lines)

