"""Kontrakt skilli Matta Pococka i ``CODING_STANDARDS.md`` w repo aplikacji (#241).

Kit nie kopiuje skilli Matta — czyta ich **ziarna setupu** w momencie reloadu
(``.agents/skills/setup-matt-pocock-skills/*.md``), więc format idzie za Mattem
bez zmian w kicie. Renderowane są tylko brakujące pliki ``docs/agents/*``
(użytkownik może je edytować) oraz blok ``## Agent skills`` w ``AGENTS.md``.

``CODING_STANDARDS.md`` jest indeksem źródeł standardów (bez kopii reguł),
odświeżanym przy każdym reloadzie. Korzystają z niego agenci ``/review-*`` kita
i skill ``/code-review`` Matta.

Moduł jest stdlib-only: bootstrap woła go przez ``scripts/matt_contract.py``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CODING_STANDARDS_REL = "CODING_STANDARDS.md"
LOCK_REL = "skills-lock.json"
MATT_SOURCE = "mattpocock/skills"
SEED_REL = Path(".agents/skills/setup-matt-pocock-skills")
AGENTS_REL = Path("AGENTS.md")
DOCS_AGENTS_REL = Path("docs/agents")
CONTEXT_MAP_REL = "CONTEXT-MAP.md"
AGENT_SKILLS_HEADING = "## Agent skills"

# Kolejność jak w ``templates/shared/labels.tsv`` — to samo źródło co ``ensure_labels``.
STATE_LABELS = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")

_HEADING_RE = re.compile(r"(?m)^## Agent skills[ \t]*$")
_NEXT_SECTION_RE = re.compile(r"(?m)^## ")
# Tylko nazwy plików słownika z ziarna Matta — inne wystąpienia słowa zostają.
_GLOSSARY_RE = re.compile(r"\bGLOSSARY(?=(?:-MAP)?\.md\b)")


@dataclass(frozen=True)
class Change:
    """Jedna zmiana wykonana w repo aplikacji."""

    path: str
    action: str  # created | updated | removed | unchanged | kept


def has_matt_skills(workspace: Path) -> bool:
    """
    Czy ``skills-lock.json`` repo zawiera skille Matta?

    Args:
        workspace: Root repo aplikacji.

    Returns:
        bool: ``True`` gdy którykolwiek wpis ma ``source: mattpocock/skills``.
            Brak pliku, uszkodzony JSON albo inny format = ``False``.
    """
    try:
        data = json.loads((workspace / LOCK_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        return False
    return any(
        isinstance(entry, dict) and str(entry.get("source", "")).strip("/") == MATT_SOURCE
        for entry in skills.values()
    )


def _seed(workspace: Path, name: str) -> str | None:
    """Ziarno setupu Matta znormalizowane do LF; brak pliku → ``None``."""
    path = workspace / SEED_REL / name
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n") + "\n"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def triage_labels(kit_root: Path) -> tuple[tuple[str, str], ...]:
    """
    Role triage z kita → nazwy etykiet (to samo źródło co ``ensure_labels``).

    ``labels.tsv`` ma jedną kolumnę nazwy (pierwszą); kit nazywa etykiety stanu
    tak jak role Matta, więc rola trafia do mapy tylko wtedy, gdy ``labels.tsv``
    ma etykietę o tej nazwie. Rola bez etykiety w kicie zostaje z wartością ziarna.

    Args:
        kit_root: Root instruction-kita (``templates/shared/labels.tsv``).

    Returns:
        tuple: Pary ``(rola, nazwa etykiety)`` w kolejności ``STATE_LABELS``.
    """
    path = kit_root / "templates" / "shared" / "labels.tsv"
    if not path.is_file():
        return ()
    names = {line.split("\t", 1)[0] for line in _read(path).splitlines()}
    return tuple((role, role) for role in STATE_LABELS if role in names)


def render_triage_labels(seed: str, labels: tuple[tuple[str, str], ...]) -> str:
    """
    Podmień prawą kolumnę tabeli triage na nazwy etykiet z kita.

    Args:
        seed: Treść ziarna ``triage-labels.md``.
        labels: Pary ``(rola, nazwa etykiety)`` z :func:`triage_labels`.

    Returns:
        str: Tabela w formacie Matta z nazwami kita (LF, końcowy newline).
    """
    mapping = dict(labels)
    lines: list[str] = []
    for line in seed.strip("\n").splitlines():
        cells = line.split("|")
        if len(cells) >= 4:
            role = cells[1].strip().strip("`")
            if role in mapping:
                cells[2] = f" `{mapping[role]}` "
                line = "|".join(cells)
        lines.append(line)
    return "\n".join(lines) + "\n"


def domain_layout(workspace: Path) -> str:
    """Układ dokumentacji domeny: ``multi-context`` przy ``CONTEXT-MAP.md``, inaczej single."""
    return "multi-context" if (workspace / CONTEXT_MAP_REL).is_file() else "single-context"


def render_domain(seed: str, layout: str) -> str:
    """
    Dopasuj ziarno ``domain.md`` do nazw dokumentów kita.

    Ziarno Matta mówi o ``GLOSSARY.md`` / ``GLOSSARY-MAP.md``; kit używa
    ``CONTEXT.md`` / ``CONTEXT-MAP.md``. Poza podmianą nazw i linią układu treść
    zostaje z ziarna, więc aktualizacja skilli płynie bez zmian w kicie.

    Args:
        seed: Treść ziarna ``domain.md``.
        layout: ``single-context`` albo ``multi-context``.

    Returns:
        str: Treść ``docs/agents/domain.md`` (LF).
    """
    text = _GLOSSARY_RE.sub("CONTEXT", seed)
    if layout == "multi-context":
        note = (
            "**Layout in this repo:** multi-context (`CONTEXT-MAP.md` with per-context "
            "`CONTEXT.md` and `docs/adr/`).\n"
        )
    else:
        note = "**Layout in this repo:** single-context (`CONTEXT.md` + `docs/adr/`).\n"

    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join([lines[0], "", note.rstrip("\n"), *lines[1:]]).strip("\n") + "\n"
    return note + text


def agent_skills_block(workspace: Path) -> str:
    """
    Blok ``## Agent skills`` w formacie setupu Matta.

    Args:
        workspace: Root repo aplikacji (decyduje o układzie domeny).

    Returns:
        str: Blok z podsekcjami Issue tracker / Triage labels / Domain docs (LF).
    """
    layout = domain_layout(workspace)
    if layout == "multi-context":
        domain = "Multi-context (`CONTEXT-MAP.md` + per-context `CONTEXT.md` and `docs/adr/`)."
    else:
        domain = "Single-context (`CONTEXT.md` + `docs/adr/`)."

    return (
        f"{AGENT_SKILLS_HEADING}\n\n"
        "### Issue tracker\n\n"
        "GitHub issues (`gh` CLI). See `docs/agents/issue-tracker.md`.\n\n"
        "### Triage labels\n\n"
        "Canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, "
        "`ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.\n\n"
        "### Domain docs\n\n"
        f"{domain} See `docs/agents/domain.md`.\n"
    )


def merge_agent_skills(text: str, block: str) -> str:
    """
    Wstaw albo odśwież blok ``## Agent skills``, resztę pliku zostawiając bez zmian.

    Args:
        text: Treść ``AGENTS.md``.
        block: Render :func:`agent_skills_block`.

    Returns:
        str: Nowa treść pliku (LF).
    """
    block = block.strip("\n") + "\n"
    match = _HEADING_RE.search(text)
    if match is None:
        if not text.strip():
            return block
        return text.rstrip("\n") + "\n\n" + block

    next_section = _NEXT_SECTION_RE.search(text, match.end())
    prefix = text[: match.start()]
    if prefix and not prefix.endswith("\n\n"):
        prefix = prefix.rstrip("\n") + "\n\n"
    suffix = text[next_section.start() :] if next_section else ""
    merged = prefix + block
    if suffix:
        merged += "\n" + suffix.lstrip("\n")
    return merged


def _strip_agent_skills(text: str, block: str) -> str:
    """Usuń blok tylko wtedy, gdy jest nietkniętym renderem kita."""
    match = _HEADING_RE.search(text)
    if match is None:
        return text
    next_section = _NEXT_SECTION_RE.search(text, match.end())
    end = next_section.start() if next_section else len(text)
    section = text[match.start() : end].strip("\n")
    if section != block.strip("\n"):
        return text
    prefix = text[: match.start()]
    suffix = text[end:]
    merged = prefix.rstrip("\n") + "\n" if prefix.strip() else ""
    if suffix:
        merged += "\n" + suffix.lstrip("\n") if merged else suffix.lstrip("\n")
    return merged


def coding_standards(workspace: Path) -> str:
    """
    Indeks źródeł standardów projektu — tylko pozycje istniejące w repo.

    Treść to **sam indeks**: żadnych kopii reguł. Kolejność oznacza ważność.

    Args:
        workspace: Root repo aplikacji.

    Returns:
        str: Treść ``CODING_STANDARDS.md`` (LF).
    """
    sources: list[tuple[str, str]] = []
    if (workspace / "AGENTS.md").is_file():
        sources.append(("AGENTS.md", "reguły pracy agentów w tym repo (najwyższy priorytet)"))
    if (workspace / ".ai" / "project.md").is_file():
        sources.append(
            (
                ".ai/project.md",
                "overlay projektu: nazewnictwo, konwencje API, biblioteka UI, ścieżki",
            )
        )
    if (workspace / "BUGBOT.md").is_file():
        sources.append(("BUGBOT.md", "reguły review, w tym blok `project:rules`"))
    if (workspace / "docs" / "adr").is_dir():
        sources.append(("docs/adr/", "decyzje architektoniczne wiążące dla zmian"))
    if (workspace / "CONTEXT.md").is_file():
        sources.append(("CONTEXT.md", "słownik domeny — nazwy pojęć i ich znaczenie"))
    sources.append(
        (
            "MCP `project-guides`",
            "`get_bundle` (Stack i Tiery) oraz `get_overlay` (overlay projektu)",
        )
    )

    lines = [
        "# Coding standards",
        "",
        "Indeks źródeł standardów projektu — **kolejność oznacza ważność**. Ten plik",
        "utrzymuje instruction-kit i odświeża go przy każdym reloadzie; reguły żyją",
        "w źródłach, nie tutaj.",
        "",
    ]
    lines.extend(
        f"{number}. **`{name}`** — {role}" if not name.startswith("MCP ")
        else f"{number}. **{name}** — {role}"
        for number, (name, role) in enumerate(sources, start=1)
    )
    return "\n".join(lines) + "\n"


def _contract_targets() -> tuple[tuple[str, str], ...]:
    """Pliki ``docs/agents/*`` renderowane z ziaren Matta: ``(ścieżka, ziarno)``."""
    return (
        ("issue-tracker.md", "issue-tracker-github.md"),
        ("triage-labels.md", "triage-labels.md"),
        ("domain.md", "domain.md"),
    )


def _render_doc(name: str, seed: str, workspace: Path, kit_root: Path) -> str:
    if name == "issue-tracker.md":
        return seed
    if name == "triage-labels.md":
        return render_triage_labels(seed, triage_labels(kit_root))
    return render_domain(seed, domain_layout(workspace))


def sync(workspace: Path, kit_root: Path) -> list[Change]:
    """
    Dołóż brakujące pliki kontraktu Matta i odśwież ``CODING_STANDARDS.md``.

    Args:
        workspace: Root repo aplikacji.
        kit_root: Root instruction-kita.

    Returns:
        list[Change]: Wykonane zmiany (``created`` / ``updated`` / ``unchanged`` / ``kept``).
    """
    changes: list[Change] = []
    matt = has_matt_skills(workspace)
    seeds = workspace / SEED_REL

    if matt and seeds.is_dir():
        for name, seed_name in _contract_targets():
            target = workspace / DOCS_AGENTS_REL / name
            if target.is_file():
                changes.append(Change(target.relative_to(workspace).as_posix(), "kept"))
                continue
            seed = _seed(workspace, seed_name)
            if seed is None:
                continue
            _write(target, _render_doc(name, seed, workspace, kit_root))
            changes.append(Change(target.relative_to(workspace).as_posix(), "created"))

        agents = workspace / AGENTS_REL
        if agents.is_file():
            current = _read(agents)
            merged = merge_agent_skills(current, agent_skills_block(workspace))
            if merged == current:
                changes.append(Change(AGENTS_REL.as_posix(), "unchanged"))
            else:
                _write(agents, merged)
                changes.append(Change(AGENTS_REL.as_posix(), "updated"))

    target = workspace / CODING_STANDARDS_REL
    rendered = coding_standards(workspace)
    if not target.is_file():
        _write(target, rendered)
        changes.append(Change(CODING_STANDARDS_REL, "created"))
    elif _read(target) != rendered:
        _write(target, rendered)
        changes.append(Change(CODING_STANDARDS_REL, "updated"))
    else:
        changes.append(Change(CODING_STANDARDS_REL, "unchanged"))

    return changes


def _prune_empty_dirs(path: Path, stop: Path) -> None:
    """Usuń puste katalogi nad plikiem, zatrzymując się na ``stop``."""
    while path != stop and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        path = path.parent


def remove(workspace: Path, kit_root: Path) -> list[Change]:
    """
    Usuń pliki kontraktu, ale tylko gdy są nietkniętym renderem kita.

    ``--remove`` nie może skasować tego, co użytkownik dostosował: porównujemy
    treść z bieżącym renderem (ziarna Matta czytane teraz, jak przy reloadzie).

    Args:
        workspace: Root repo aplikacji.
        kit_root: Root instruction-kita.

    Returns:
        list[Change]: Wykonane zmiany (``removed`` / ``kept`` / ``updated``).
    """
    changes: list[Change] = []
    seeds = workspace / SEED_REL

    for name, seed_name in _contract_targets():
        target = workspace / DOCS_AGENTS_REL / name
        if not target.is_file():
            continue
        seed = _seed(workspace, seed_name)
        if seed is not None and _read(target) == _render_doc(name, seed, workspace, kit_root):
            target.unlink()
            changes.append(Change(target.relative_to(workspace).as_posix(), "removed"))
        else:
            changes.append(Change(target.relative_to(workspace).as_posix(), "kept"))
    _prune_empty_dirs(workspace / DOCS_AGENTS_REL, workspace)

    standards = workspace / CODING_STANDARDS_REL
    if standards.is_file():
        if _read(standards) == coding_standards(workspace):
            standards.unlink()
            changes.append(Change(CODING_STANDARDS_REL, "removed"))
        else:
            changes.append(Change(CODING_STANDARDS_REL, "kept"))

    agents = workspace / AGENTS_REL
    if agents.is_file():
        current = _read(agents)
        stripped = _strip_agent_skills(current, agent_skills_block(workspace))
        if stripped != current:
            _write(agents, stripped)
            changes.append(Change(AGENTS_REL.as_posix(), "updated"))

    return changes


def main(argv: list[str] | None = None) -> int:
    """
    Wejście z bootstrapu: ``matt_contract.py WORKSPACE KIT_ROOT [--remove]``.

    Args:
        argv: Argumenty (domyślnie ``sys.argv[1:]``).

    Returns:
        int: Kod wyjścia (zawsze 0 — brak ziaren/skilli nie jest błędem).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    removing = "--remove" in args
    args = [arg for arg in args if arg != "--remove"]
    if len(args) != 2:
        print("użycie: matt_contract.py WORKSPACE KIT_ROOT [--remove]", file=sys.stderr)
        return 2

    workspace, kit_root = Path(args[0]), Path(args[1])
    changes = remove(workspace, kit_root) if removing else sync(workspace, kit_root)
    for change in changes:
        if change.action == "created":
            print(f"  + {change.path} (kontrakt Matta / indeks standardów)")
        elif change.action == "updated":
            print(f"  + {change.path} (odświeżono)")
        elif change.action == "removed":
            print(f"  - {change.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
