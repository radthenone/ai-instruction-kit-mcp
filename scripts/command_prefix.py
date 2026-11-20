#!/usr/bin/env python3
"""
Prefiks komend per klient (#525): podstawienie @KIT_CMD_PREFIX@ i @KIT_NAME_PREFIX@.

Wartości czyta z sekcji ``command_prefixes`` w manifest.yaml. Czyta jednoliniowe wpisy
bez PyYAML, bo bootstrap działa też na czystym python3. Zgodność z ``load_manifest``
pilnuje tests/test_command_prefix.py.

Użycie:
    command_prefix.py copy MANIFEST TARGET SRC DEST
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CMD_PLACEHOLDER = "@KIT_CMD_PREFIX@"
NAME_PLACEHOLDER = "@KIT_NAME_PREFIX@"
ALLOWED_SIGILS = ("/", "$")
# shortcut: czyta tylko wpisy command_prefixes w jednej linii, bez PyYAML (bootstrap działa na czystym python3); przejść na yaml.safe_load, gdy bootstrap zawsze dostaje KIT_PYTHON z PyYAML. Zgodność z load_manifest pilnuje test_reader_returns_same_values_as_load_manifest.
_ENTRY = re.compile(
    r'^  ([A-Za-z0-9_-]+): \{sigil: "([^"]*)", namespace: "([^"]*)", name_prefix: "([^"]*)"\}\s*$'
)


def resolve(text: str, *, sigil: str, namespace: str, name_prefix: str) -> str:
    """
    Podstaw placeholdery prefiksu w tekście.

    Args:
        text: Treść szablonu.
        sigil: Znak wywołania (``/`` albo ``$``).
        namespace: Przestrzeń nazw w treści.
        name_prefix: Przestrzeń nazw we frontmatter ``name:``.

    Returns:
        str: Treść bez placeholderów prefiksu.
    """
    return text.replace(CMD_PLACEHOLDER, sigil + namespace).replace(NAME_PLACEHOLDER, name_prefix)


def read_values(manifest: Path, target: str) -> tuple[str, str, str]:
    """
    Odczytaj sigil, namespace i name_prefix celu z ``command_prefixes``.

    Args:
        manifest: Ścieżka do manifest.yaml.
        target: Nazwa celu (klient albo ``shared``).

    Returns:
        tuple[str, str, str]: (sigil, namespace, name_prefix).

    Raises:
        ValueError: Gdy cel nie ma wpisu albo sigil jest zły.
    """
    in_section = False
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("command_prefixes:"):
            in_section = True
            continue
        if in_section and line and not line.startswith((" ", "#")):
            break
        match = _ENTRY.match(line) if in_section else None
        if match and match.group(1) == target:
            sigil, namespace, name_prefix = match.group(2), match.group(3), match.group(4)
            if sigil not in ALLOWED_SIGILS:
                raise ValueError(f"command_prefixes.{target}.sigil: dozwolone / albo $, jest {sigil!r}")
            return sigil, namespace, name_prefix
    raise ValueError(f"Brak command_prefixes dla celu: {target}")


def copy_template(manifest: Path, target: str, src: Path, dest: Path) -> None:
    """
    Skopiuj szablon do ``dest``, podstawiając prefiks celu.

    Pliki bez placeholderów idą bajt w bajt, tak jak ``cp``.

    Args:
        manifest: Ścieżka do manifest.yaml.
        target: Nazwa celu.
        src: Plik szablonu.
        dest: Miejsce docelowe.

    Raises:
        ValueError: Gdy cel nie ma wpisu w manifeście.
    """
    sigil, namespace, name_prefix = read_values(manifest, target)
    raw = src.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if CMD_PLACEHOLDER.encode() in raw or NAME_PLACEHOLDER.encode() in raw:
        text = resolve(raw.decode("utf-8"), sigil=sigil, namespace=namespace, name_prefix=name_prefix)
        dest.write_bytes(text.encode("utf-8"))
    else:
        shutil.copyfile(src, dest)
    shutil.copymode(src, dest)


def main(argv: list[str]) -> int:
    """
    Punkt wejścia CLI.

    Args:
        argv: Argumenty z sys.argv: program, ``copy``, MANIFEST, TARGET, SRC, DEST.

    Returns:
        int: Kod wyjścia.
    """
    if len(argv) != 6 or argv[1] != "copy":
        print(__doc__, file=sys.stderr)
        return 1
    try:
        copy_template(Path(argv[2]), argv[3], Path(argv[4]), Path(argv[5]))
    except ValueError as exc:
        print(f"command_prefix: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
