#!/usr/bin/env python3
"""
Scal / usuń hooki guardraili kita w `.agents/hooks.json` (Antigravity).

Użycie:
    antigravity_hooks.py install TARGET_HOOKS_JSON TEMPLATE_HOOKS_JSON
    antigravity_hooks.py prune   TARGET_HOOKS_JSON

`.agents/hooks.json` to workspace'owy plik hooków Antigravity i należy do
użytkownika — trzyma jego własne nazwane hooki obok kitowego. Kit dokłada tam
wyłącznie nazwany hook `kit-guards` i tylko jego zabiera przy prune;
reinstalacja podmienia klucz kita zamiast go duplikować. Gdy plik istnieje, ale
nie da się sparsować (uszkodzony JSON), oryginał idzie do `.bak` (kolejne do `.bak.N`, starszy backup zostaje), a wpis kita
piszemy od zera — cicho zgubiony plik byłby gorszy niż jawny backup.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Nazwa hooka kita w `.agents/hooks.json` — jedyny klucz, który kit podmienia i usuwa.
KIT_HOOK = "kit-guards"


def write(target: Path, data: dict) -> None:
    """
    Zapisz plik hooków albo usuń go, gdy nic w nim nie zostało.

    Args:
        target: Ścieżka `.agents/hooks.json`.
        data: Zawartość do zapisania; pusty słownik usuwa plik.
    """
    if not data:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    mode, target = argv[1], Path(argv[2])

    if mode == "prune":
        if not target.is_file():
            return 0
        try:
            data = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            # Nie umiemy odróżnić wpisu kita od cudzego — zostawiamy plik w spokoju.
            return 0
        if not isinstance(data, dict) or KIT_HOOK not in data:
            return 0
        del data[KIT_HOOK]
        write(target, data)
        return 0

    if mode != "install" or len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2

    template_text = Path(argv[3]).read_text(encoding="utf-8")
    kit = json.loads(template_text)[KIT_HOOK]

    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(template_text, encoding="utf-8", newline="\n")
        return 0

    old_text = target.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(old_text)
        if not isinstance(data, dict):
            raise ValueError("top-level nie jest obiektem")
    except (OSError, ValueError) as exc:
        backup = target.with_name(target.name + ".bak")
        n = 1
        while backup.exists():  # starszego backupu nie nadpisujemy
            backup = target.with_name(f"{target.name}.bak.{n}")
            n += 1
        backup.write_text(old_text, encoding="utf-8", newline="\n")
        print(
            f"  ! {target.name}: nie da się scalić ({exc.__class__.__name__}) — oryginał w "
            f"{backup.name}, przenieś swoje hooki ręcznie",
            file=sys.stderr,
        )
        data = {}

    data[KIT_HOOK] = kit
    write(target, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
