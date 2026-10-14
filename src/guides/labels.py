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

from guides.resolver import TIER_NONE, resolve_workspace_profile

LABELS_REL_PATH = Path("templates/shared/labels.tsv")
TRIAGE_REL_PATH = Path("docs/agents/triage-labels.md")
STATE_LABELS = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")

Runner = Callable[[list[str]], subprocess.CompletedProcess]


@dataclass(frozen=True)
class Label:
    """Wiersz ``labels.tsv``: ``when`` = ``always`` albo Tiery po przecinku."""

    name: str
    color: str
    description: str
    when: str

    def active(self, tiers: dict[str, str]) -> bool:
        """Etykieta potrzebna przy tych Tierach (którykolwiek z ``when`` ≠ ``none``)."""
        if self.when == "always":
            return True
        return any(tiers.get(tier, TIER_NONE) != TIER_NONE for tier in self.when.split(","))


def read_label_set(kit_root: Path) -> list[Label]:
    """Kanoniczny zestaw etykiet kita."""
    text = (kit_root / LABELS_REL_PATH).read_text(encoding="utf-8")
    return [Label(*line.split("\t")) for line in text.splitlines() if line.strip()]


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


def _gh(run: Runner, args: list[str]) -> subprocess.CompletedProcess | str:
    """Wywołaj ``gh``; błąd jako jedna linia tekstu zamiast wyjątku."""
    try:
        result = run(["gh", *args])
    except FileNotFoundError:
        return "labels: brak `gh` — zainstaluj GitHub CLI i `gh auth login`."
    if result.returncode != 0:
        first = next((ln for ln in (result.stderr or "").splitlines() if ln.strip()), "")
        return f"labels: `gh {args[0]} {args[1]}` nie działa (auth / remote GitHub?): {first.strip()}"
    return result


def ensure_labels(
    workspace: Path,
    kit_root: Path,
    *,
    dry_run: bool = True,
    run: Runner | None = None,
    tiers: dict[str, str] | None = None,
) -> str:
    """
    Załóż w repo GitHuba brakujące etykiety kita.

    Args:
        workspace: Repo aplikacji (Profil + opcjonalnie ``docs/agents/triage-labels.md``).
        kit_root: Root kita (``labels.tsv``).
        dry_run: ``True`` — tylko plan, bez ``gh label create``.
        run: Runner komend (domyślnie ``subprocess.run`` w ``workspace``).
        tiers: Tiery projektu; ``None`` = z Profilu.

    Returns:
        str: Licznik ``created/to create, existing, skipped (Tier none)`` + nazwy;
            przy braku ``gh``/auth/remote — jedna linia.
    """
    if run is None:
        def run(args: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(args, cwd=workspace, capture_output=True, text=True, check=False)

    if tiers is None:
        tiers = resolve_workspace_profile(workspace, kit_root=kit_root).tiers
    mapped = triage_names(workspace)
    labels = [replace(lb, name=mapped.get(lb.name, lb.name)) for lb in read_label_set(kit_root)]
    wanted = [lb for lb in labels if lb.active(tiers)]
    skipped = [lb for lb in labels if not lb.active(tiers)]

    listed = _gh(run, ["label", "list", "--limit", "200", "--json", "name"])
    if isinstance(listed, str):
        return listed
    existing = {item["name"].lower() for item in json.loads(listed.stdout or "[]")}
    missing = [lb for lb in wanted if lb.name.lower() not in existing]

    if not dry_run:
        for count, lb in enumerate(missing):
            done = _gh(run, ["label", "create", lb.name, "--color", lb.color,
                             "--description", lb.description])
            if isinstance(done, str):
                return f"{done} (utworzone wcześniej: {count})"

    verb = "to create" if dry_run else "created"
    lines = [
        f"{verb}: {len(missing)}, existing: {len(wanted) - len(missing)}, "
        f"skipped (Tier none): {len(skipped)}",
        *(f"+ {lb.name}" for lb in missing),
        *(f"- {lb.name} (Tier none)" for lb in skipped),
    ]
    return "\n".join(lines)

