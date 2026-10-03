"""Katalog pytań o projekt z manifestu — warunki ocenione na bieżącym Profilu.

Python niczego tu nie skanuje: sygnały ``detect:`` sprawdza agent w plikach repo.
Ten moduł tylko wybiera pytania aktualne dla Profilu i podpowiedź układu katalogów.
"""

from __future__ import annotations

from guides.manifest import LayoutHint, Manifest, Question

_PROFILE_KEYS = ("backend", "web", "mobile", "codegen")


def active_questions(manifest: Manifest, values: dict[str, str]) -> list[Question]:
    """Pytania, których ``when:`` jest spełnione dla Profilu (kolejność z manifestu)."""
    return [q for q in manifest.questions.values() if q.when.holds(values)]


def layout_hint(manifest: Manifest, values: dict[str, str]) -> LayoutHint | None:
    """Pierwsza podpowiedź układu pasująca do Tierów albo ``None``."""
    return next((hint for hint in manifest.layouts if hint.when.holds(values)), None)


def _target(question: Question) -> str:
    if question.sets.startswith("paths."):
        return f"`{question.sets.removeprefix('paths.')}:` w sekcji `## Ścieżki` w `.ai/project.md`"
    if question.sets:
        return f"`{question.sets}:` w `.ai/project.profile.yaml`"
    actions = ", ".join(
        f"`{key}:` += {', '.join(f'`{v}`' for v in items)}" for key, items in question.on_yes.items()
    )
    return f"przy `yes` dopisz do `.ai/project.profile.yaml`: {actions}"


def render_catalog(manifest: Manifest, values: dict[str, str]) -> str:
    """
    Katalog pytań jako Markdown dla skilla.

    Args:
        manifest: Manifest z sekcjami ``questions`` i ``layouts``.
        values: Bieżący Profil — Tiery (``none`` dla pustych) i efektywny ``codegen``.

    Returns:
        str: Aktywne pytania z opcjami, domyślnymi i sygnałami, lista pominiętych,
            podpowiedź układu katalogów.
    """
    tiers = " ".join(f"{key}=`{values.get(key, 'none')}`" for key in ("backend", "web", "mobile"))
    lines = [
        "# Katalog pytań o projekt",
        "",
        f"Profil teraz: {tiers}.",
        "",
        "Dla każdego pytania najpierw sprawdź `Wykrywanie` w plikach repo (glob od roota, "
        "regex w treści pliku); pytaj tylko o to, czego nie wykryłeś — z numerem, opcjami "
        "i domyślną. Warunki zależą od Profilu: po zapisaniu Tierów wywołaj `list_questions` "
        "ponownie.",
        "",
    ]
    active = active_questions(manifest, values)
    for number, question in enumerate(active, start=1):
        lines.append(f"## {number}. `{question.question_id}` — {question.question}")
        lines.append("")
        if question.options:
            lines.append(f"- Opcje: {' | '.join(f'`{o}`' for o in question.options)}")
        lines.append(f"- Domyślnie: `{question.default_for(values)}`")
        if question.sets in _PROFILE_KEYS:
            lines.append(f"- Teraz w Profilu: `{values.get(question.sets, 'none')}`")
        lines.append(f"- Zapis: {_target(question)}")
        if question.detect:
            signals = "; ".join(
                f"`{s.glob}`" + (f" ~ `{s.pattern}`" if s.pattern else "") + f" → `{s.value}`"
                for s in question.detect
            )
            lines.append(f"- Wykrywanie: {signals}")
        lines.append("")

    skipped = [q.question_id for q in manifest.questions.values() if q not in active]
    if skipped:
        lines.extend(
            [
                "## Pominięte (warunek niespełniony dla Profilu)",
                "",
                ", ".join(f"`{qid}`" for qid in skipped),
                "",
            ]
        )

    lines.extend(["## Układ katalogów", ""])
    hint = layout_hint(manifest, values)
    if hint is not None and hint.warning:
        lines.append(f"⚠ {hint.warning}")
    elif hint is not None and hint.module and hint.module in manifest.modules:
        info = manifest.modules[hint.module]
        lines.append(f"Podpowiedź z `{hint.module}` — dopasuj do repo i zapisz w `## Ścieżki`:")
        lines.append("")
        if info.path.is_file():
            lines.append(info.path.read_text(encoding="utf-8").strip())
    else:
        lines.append(
            "Brak drzewka dla tej kombinacji Tierów — domyślne ścieżki per Tier z pytań `paths-*`."
        )
    return "\n".join(lines)
