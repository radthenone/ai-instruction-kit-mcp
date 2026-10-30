"""``kit-ai night-ctx`` — deterministyczny nagłówek CTX nocy (#314).

Nagłówek ma znacznik generatora, ``Host:`` równe ``kit-ai host``, BASE wg wspólnej
reguły bazy, bramki szybkie z overlayu albo CI i język z Profilu. Wartości bez
deterministycznego źródła są jawnie oznaczone jako „założenie”.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides import cli

KIT_ROOT = Path(__file__).resolve().parents[1]


def _run(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    out = io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=False):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
    return code, out.getvalue()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _init_repo(repo: Path, *, dev: str | None = "same", default: str = "main") -> None:
    """Repo z ``origin/<default>`` i opcjonalnie ``origin/dev``.

    ``dev="same"`` — dev na tej samej commitcie co default; ``"behind"`` — dev jest
    przodkiem default; ``"ahead"`` — dev ma własny commit; ``None`` — brak dev.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", default)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if dev is not None:
        if dev == "ahead":
            _git(repo, "checkout", "-q", "-b", "dev")
            (repo / "dev.txt").write_text("d\n", encoding="utf-8")
            _git(repo, "add", "dev.txt")
            _git(repo, "commit", "-q", "-m", "dev")
            dev_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
            _git(repo, "checkout", "-q", default)
        elif dev == "behind":
            dev_sha = base
            (repo / "main.txt").write_text("m\n", encoding="utf-8")
            _git(repo, "add", "main.txt")
            _git(repo, "commit", "-q", "-m", "main")
            base = _git(repo, "rev-parse", "HEAD").stdout.strip()
        else:
            dev_sha = base
        _git(repo, "update-ref", "refs/remotes/origin/dev", dev_sha)
    _git(repo, "update-ref", f"refs/remotes/origin/{default}", base)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{default}")


def _write_overlay(repo: Path, *, base: str | None = None, commands: tuple[str, ...] = ()) -> None:
    (repo / ".ai").mkdir(parents=True, exist_ok=True)
    lines = ["# Overlay projektu"]
    if base:
        lines.append(f"base: {base}")
    if commands:
        lines += ["", "## Komendy", *(f"- {c}" for c in commands)]
    (repo / ".ai" / "project.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_profile(repo: Path, *, language: str = "pl") -> None:
    (repo / ".ai").mkdir(parents=True, exist_ok=True)
    (repo / ".ai" / "project.profile.yaml").write_text(
        f"name: demo\nlanguage: {language}\nbackend: none\nweb: none\nmobile: none\n",
        encoding="utf-8",
    )


class NightCtxTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ctx(self, *, env: dict[str, str] | None = None) -> str:
        code, out = _run("night-ctx", str(self.repo), env=env or {"KIT_HOST_PROFILE": "vps"})
        self.assertEqual(code, 0, out)
        return out

    def test_marker_and_host_from_override(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo)
        _write_profile(self.repo)
        for host in ("vps", "local"):
            with self.subTest(host=host):
                out = self._ctx(env={"KIT_HOST_PROFILE": host, "GUIDES_HOST_PROFILE": ""})
                self.assertIn(f"<!-- kit-ai night-ctx v1 host={host} -->", out)
                self.assertIn(f"Host: `{host}`", out)

    def test_language_from_profile(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo)
        _write_profile(self.repo, language="en")
        out = self._ctx()
        self.assertIn("Język: `en`", out)

    def test_base_from_overlay_wins(self) -> None:
        _init_repo(self.repo, dev="behind")
        _write_overlay(self.repo, base="release")
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("BASE: `release`", out)
        self.assertIn("base: z project.md", out)

    def test_active_dev_is_base(self) -> None:
        _init_repo(self.repo, dev="ahead")
        _write_overlay(self.repo)
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("BASE: `dev`", out)
        self.assertIn("dev aktywny", out)

    def test_dev_behind_default_falls_back_to_default(self) -> None:
        _init_repo(self.repo, dev="behind")
        _write_overlay(self.repo)
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("BASE: `main`", out)
        self.assertIn("dev w tyle", out)

    def test_missing_dev_falls_back_to_default(self) -> None:
        _init_repo(self.repo, dev=None)
        _write_overlay(self.repo)
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("BASE: `main`", out)
        self.assertIn("brak dev", out)

    def test_quick_gates_from_overlay(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo, commands=("Szybko: `make test-fast`",))
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("Bramki szybkie: `make test-fast`", out)
        self.assertIn("overlay", out)

    def test_quick_gates_merge_overlay_and_ci(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo, commands=("Szybko: `make test-fast`",))
        _write_profile(self.repo)
        workflows = self.repo / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text(
            "name: CI\non: [pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: make test-fast\n"
            "      - run: uv run python -m unittest discover -s tests\n",
            encoding="utf-8",
        )
        out = self._ctx()
        gates = next(ln for ln in out.splitlines() if ln.startswith("- Bramki szybkie:"))
        self.assertIn("`make test-fast`", gates)
        self.assertIn("`uv run python -m unittest discover -s tests`", gates)
        self.assertEqual(gates.count("`make test-fast`"), 1, gates)
        self.assertIn("overlay + CI", gates)

    def test_quick_gates_from_ci_without_overlay_commands(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo)
        _write_profile(self.repo)
        workflows = self.repo / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text(
            "name: CI\non: [pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - name: Tests\n        run: uv run python -m unittest discover -s tests\n"
            "      - name: Deploy\n        run: ./deploy.sh\n",
            encoding="utf-8",
        )
        out = self._ctx()
        self.assertIn("uv run python -m unittest discover -s tests", out)
        self.assertIn("CI", out)
        self.assertNotIn("deploy.sh", out)

    def test_no_sources_marks_assumption(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo)
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("założenie", out)

    def test_header_says_full_suite_only_in_ci(self) -> None:
        _init_repo(self.repo)
        _write_overlay(self.repo)
        _write_profile(self.repo)
        out = self._ctx()
        self.assertIn("Pełny zestaw testów: tylko CI", out)


if __name__ == "__main__":
    unittest.main()
