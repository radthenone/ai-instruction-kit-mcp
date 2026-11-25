"""Regresja reloadu: wynik instalacji i reloadu wszystkich klientów zgadza się z zatwierdzonym snapshotem (#533).

Snapshot to SHA-256 każdego pliku Workspace'u (ścieżka względem katalogu repo). Pliki są
normalizowane: ścieżki tymczasowego Workspace'u i kita zastępowane znacznikami, a stamp
``.ai/.kit-bootstrap.json`` (commit kita) pomijany. Jedyny wyjątek to tabela
``### Mapowanie komend kita`` w bloku ``kit:brief`` w AGENTS.md — ona zmienia się razem z
mapowaniem klientów i nie jest pilnowana tym testem.

Zamierzoną zmianę wyniku zatwierdza się lokalnie przez ``KIT_UPDATE_SNAPSHOT=1`` i commit pliku
``tests/fixtures/reload_snapshot.json`` razem z kodem, który ją zmienił. Na CI tryb zapisu
kończy się błędem, nie pominięciem.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _shell import is_ci
from test_bootstrap import KIT_ROOT, _BootstrapTestCase

from guides import cli

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "reload_snapshot.json"
SKIPPED = frozenset({".ai/.kit-bootstrap.json"})
MAPPING_TABLE = re.compile(rb"### Mapowanie komend kita\n(?:\|[^\n]*\n)+")


def _quiet_main(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


def _normalise(data: bytes, app: Path, rel: str) -> bytes:
    """Usuwa to, co zależy od maszyny albo od miejsca tymczasowego katalogu."""
    if rel == "AGENTS.md":
        data = MAPPING_TABLE.sub(b"", data)
    for root, mark in ((app, b"<WORKSPACE>"), (app.resolve(), b"<WORKSPACE>"), (KIT_ROOT, b"<KIT>")):
        for variant in {str(root), root.as_posix(), json.dumps(str(root))[1:-1]}:
            data = data.replace(variant.encode("utf-8"), mark)
    return data


def _digest_tree(app: Path) -> dict[str, str]:
    """SHA-256 znormalizowanej zawartości każdego pliku w Workspace'ie."""
    digests: dict[str, str] = {}
    for path in sorted(app.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(app).as_posix()
        if rel in SKIPPED:
            continue
        digests[rel] = hashlib.sha256(_normalise(path.read_bytes(), app, rel)).hexdigest()
    return digests


def _diff(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    """Różnice w kształcie `+ dodany`, `- usunięty`, `~ zmieniony`."""
    lines = [f"+ {rel}" for rel in sorted(actual.keys() - expected.keys())]
    lines += [f"- {rel}" for rel in sorted(expected.keys() - actual.keys())]
    lines += [
        f"~ {rel}" for rel in sorted(expected.keys() & actual.keys()) if expected[rel] != actual[rel]
    ]
    return lines


class TestReloadSnapshot(_BootstrapTestCase):
    """Install i reload wszystkich klientów dają wynik zgodny z zatwierdzonym snapshotem."""

    def setUp(self) -> None:
        super().setUp()
        # Snapshot powstał na VPS: tam sync-local dopisuje `UV_NO_SYNC=1` (#334). Na CI host to
        # local (`CI`), więc bez przypięcia różniła się tylko `.claude/settings.local.json`.
        env_patch = mock.patch.dict(os.environ, {"KIT_HOST_PROFILE": "vps"})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_install_and_reload_match_approved_snapshot(self) -> None:
        if os.environ.get("KIT_UPDATE_SNAPSHOT") == "1" and is_ci():
            self.fail("KIT_UPDATE_SNAPSHOT=1 na CI: zapisz snapshot lokalnie i commituj.")
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            self.assertEqual(_quiet_main("install", str(app), "--clients", "all")[0], 0)
            code, out = _quiet_main("reload", str(app))
            self.assertEqual(code, 0, out)
            actual = _digest_tree(app)

        if os.environ.get("KIT_UPDATE_SNAPSHOT") == "1":
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(
                json.dumps(actual, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            # Pominięcie, nie zaliczenie: tryb zapisu nie sprawdza regresji i ma być widoczny w raporcie.
            self.skipTest("snapshot zapisany; uruchom bez KIT_UPDATE_SNAPSHOT, żeby sprawdzić regresję")

        expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(
            _diff(expected, actual),
            [],
            "Wynik reloadu różni się od zatwierdzonego snapshotu. Zamierzoną zmianę zatwierdź "
            "przez KIT_UPDATE_SNAPSHOT=1 i commit tests/fixtures/reload_snapshot.json.",
        )


if __name__ == "__main__":
    unittest.main()
