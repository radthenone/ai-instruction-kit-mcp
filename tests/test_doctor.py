"""Testy ``doctor`` — rozjazd ścieżek i komend w regułach projektu z repo (#242)."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides import cli, server
from guides.bugbot_md import MAX_MIGRATED_LINES, read_template_history
from guides.bugbot_md import render as render_bugbot
from guides.doctor import run_doctor


def setUpModule() -> None:
    """Doctor czyta pluginy z pustego CLAUDE_HOME, nie z prawdziwego ~/.claude (#316)."""
    tmp = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(tmp.cleanup)
    patcher = mock.patch.dict("os.environ", {"CLAUDE_HOME": tmp.name})
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


KIT_ROOT = Path(__file__).resolve().parents[1]

PROFILE = """\
name: doctor-test
language: pl
clients: claude

backend: none
web: none
mobile: none

codegen: none
"""


def _workspace(tmp: str) -> Path:
    workspace = Path(tmp) / "workspace"
    workspace.mkdir()
    (workspace / ".ai").mkdir()
    (workspace / ".ai" / "project.profile.yaml").write_text(PROFILE, encoding="utf-8")
    return workspace


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _rules_block(line: str, block: str = "rules") -> str:
    """Reguła w bloku projektu — plik z blokiem nie jest kandydatem do migracji (#277)."""
    return f"<!-- project:{block} -->\n{line}\n<!-- /project:{block} -->\n"


def _report(workspace: Path, clients: str = "claude"):
    return run_doctor(workspace, clients=clients)


class TestPathFindings(unittest.TestCase):
    def test_missing_path_warns_with_file_and_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                "# Bugbot\n\nReguła: `src/auth/` blokuje merge.\n",
            )

            report = _report(workspace)

            self.assertEqual(len(report.warnings), 1, report.render())
            finding = report.warnings[0]
            self.assertEqual(finding.file, "BUGBOT.md")
            self.assertEqual(finding.line, 3)
            self.assertIn("src/auth/", finding.message)
            self.assertIn("doctor: OSTRZEŻENIE BUGBOT.md:3", report.render())

    def test_existing_path_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "src" / "auth" / "__init__.py", "")
            _write(workspace / "BUGBOT.md", "Reguła: `src/auth/`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_glob_and_placeholder_do_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                "\n".join(
                    [
                        "Glob: `**/auth/**`, `packages/*/src`.",
                        "Placeholder: `src/<tier>/x.py`, `<N>`.",
                        "Wzorzec: `**/*_test.py`.",
                    ]
                )
                + "\n",
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_windows_separators_are_normalised(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "src" / "guides" / "cli.py", "")
            _write(workspace / "BUGBOT.md", "Plik: `src\\guides\\cli.py`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_bare_filename_is_found_below_root(self) -> None:
        """`server.py` w overlayu bywa skrótem do pliku w podkatalogu — nie alarmuj."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "src" / "guides" / "server.py", "")
            _write(workspace / "BUGBOT.md", "Serwer: `server.py`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_dependency_file_alternatives_do_not_warn(self) -> None:
        """Reguła wymienia lockfile'y różnych menedżerów — brak jednego to nie rozjazd."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "package.json", "{}\n")
            _write(
                workspace / "BUGBOT.md",
                "If dependency files change (`package.json`, `bun.lock`, "
                "`requirements.txt`, `uv.lock`):\n",
            )

            self.assertEqual(_report(workspace).warnings, ())


    def test_app_path_missing_warns_even_when_kit_has_it(self) -> None:
        """Repo aplikacji bez `src/` i `README.md` — kit je ma, ale to nie maskuje braku."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", _rules_block("Reguła: `src/` i `README.md`."))

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            self.assertEqual(len(warnings), 2, warnings)

    def test_kit_only_paths_are_skipped_in_app_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "AGENTS.md",
                _rules_block(
                    "Kit: `templates/shared/agents/`, `manifest.yaml`, "
                    "`scripts/bootstrap-project.sh`, `modules/`.",
                    "agents",
                ),
            )

            self.assertEqual(run_doctor(workspace, KIT_ROOT, clients="claude").warnings, ())

    def test_bare_filename_in_node_modules_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "node_modules" / "pkg" / "server.py", "")
            _write(workspace / "BUGBOT.md", "Serwer: `server.py`.\n")

            self.assertEqual(len(_report(workspace).warnings), 1)


    def test_lines_copied_from_kit_template_are_skipped_in_app_repo(self) -> None:
        """Treść szablonu kita (komendy Tierów spoza Profilu) to nie reguły użytkownika."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            kit = Path(tmp) / "kit"
            _write(kit / "templates" / "AGENTS.md", "- `/teacher-backend` i `CONTEXT.md`\n")
            _write(
                workspace / "AGENTS.md",
                "- `/teacher-backend` i `CONTEXT.md`\nWłasna: `/review-ghost`.\n",
            )

            warnings = run_doctor(workspace, kit, clients="claude").warnings

            self.assertEqual([w.line for w in warnings], [2], warnings)


class TestOverlayPaths(unittest.TestCase):
    def test_missing_overlay_directory_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "backend").mkdir()
            _write(
                workspace / ".ai" / "project.md",
                "\n".join(
                    [
                        "# Overlay",
                        "",
                        "## Ścieżki",
                        "",
                        "- backend: `backend/`",
                        "- web: `frontend/web/`",
                    ]
                )
                + "\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertEqual(warnings[0].file, ".ai/project.md")
            self.assertEqual(warnings[0].line, 6)
            self.assertIn("web:", warnings[0].message)
            self.assertIn("frontend/web/", warnings[0].message)

    def test_overlay_key_may_point_to_existing_file(self) -> None:
        """F7: klucz `## Ścieżki` wskazujący istniejący plik to nie rozjazd."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / ".ai" / "project.md",
                "## Ścieżki\n\n- Taskfile: `Taskfile.yml` — punkt wejścia\n",
            )
            _write(workspace / "Taskfile.yml", "version: 3\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_overlay_key_pointing_to_missing_file_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / ".ai" / "project.md",
                "## Ścieżki\n\n- Taskfile: `Taskfile.yml` — punkt wejścia\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("taskfile:", warnings[0].message)

    def test_overlay_path_is_not_reported_twice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- backend: `backend/`\n")

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("backend:", warnings[0].message)


MONOREPO_OVERLAY = """\
# Overlay

## Ścieżki

- backend: `backend/`
- frontend: `frontend/`
- web: `frontend/web/`
- mobile: `frontend/mobile/`
- Taskfile: `Taskfile.yml` — główny punkt wejścia komend

## Backend

- Konfiguracja: `core/envs.py`, ceny: `apps/products/pricing.py`.
- Web: `web/app/tokens.css`, mobile: `mobile/tailwind.config.js`.
- Nawigacja przez `next/navigation`, użytkownik z `request.user`.
- **Brak `apps/files`** — pliki trzymamy w S3.
- **Nie istnieje po stronie frontendu:** `features/catalog`, `features/cart`.
- API przez DRF pod prefiksem `customers/` (`customers/profile`, `customers/addresses`).
- Web: komponenty w `ui/`, layout w `app/`, helpery w `src/lib/`.
"""


def _monorepo(tmp: str) -> Path:
    """Fikstura #266: backend + web + mobile + pakiety workspace'u."""
    workspace = _workspace(tmp)
    for rel in (
        "backend/src/core/envs.py",
        "backend/src/apps/products/pricing.py",
        "frontend/web/src/components/ui/button.tsx",
        "frontend/web/src/lib/utils.ts",
        "frontend/web/app/tokens.css",
        "frontend/mobile/tailwind.config.js",
        "frontend/packages/api/generated/index.ts",
        "Taskfile.yml",
    ):
        _write(workspace / rel, "")
    _write(
        workspace / "package.json",
        json.dumps({"workspaces": ["frontend/packages/*", "frontend/web", "frontend/mobile"]}),
    )
    _write(workspace / "frontend/web/package.json", json.dumps({"dependencies": {"next": "15"}}))
    _write(workspace / "frontend/packages/api/package.json", "{}")
    _write(workspace / ".ai" / "project.md", MONOREPO_OVERLAY)
    return workspace


class TestFalsePositives(unittest.TestCase):
    """#266: klasy F1–F7 nie dają ostrzeżeń, realny rozjazd — jedno z propozycją."""

    def test_monorepo_overlay_with_every_false_positive_class_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)

            report = _report(workspace)

            self.assertEqual(report.warnings, (), report.render())

    def test_real_stale_path_warns_once_with_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / "BUGBOT.md",
                "<!-- project:rules -->\nUI: `frontend/web/components/ui/`.\n"
                "<!-- /project:rules -->\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertEqual(warnings[0].kind, "stale-path")
            self.assertEqual(warnings[0].suggestion, "frontend/web/src/components/ui/")

    def test_api_segment_inside_path_is_not_url_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "BUGBOT.md", "Regeneruj `frontend/src/api/generated/`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([w.value for w in warnings], ["frontend/src/api/generated/"])
            self.assertEqual(warnings[0].suggestion, "frontend/packages/api/generated/")

    def test_negated_path_that_exists_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY + "- Brak `backend/src/core/` w tym repo.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertEqual(warnings[0].kind, "negated-path-exists")
            self.assertIn("nie istnieje, a istnieje", warnings[0].message)

    def test_negated_existing_path_outside_overlay_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "AGENTS.md", "- Brak `backend/src/core/` w tym repo.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_negation_word_far_from_backtick_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            (workspace / "tests").mkdir()
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY
                + "- Do not edit `backend/src/core/envs.py` ręcznie.\n"
                + "- Brak testów → `tests/`.\n"
                + "- No raw SQL outside `backend/src/db/`.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(
                [(w.kind, w.value) for w in warnings], [("stale-path", "backend/src/db/")]
            )

    def test_router_and_endpoint_words_do_not_hide_stale_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / "BUGBOT.md",
                "- Router w `frontend/web/src/router/`.\n"
                "- Endpointy w `backend/src/endpoints/`.\n"
                "- Klient `/api/` w `frontend/web/src/client.ts`.\n"
                "- Trasa `api/v1/users/` bez zmian.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(
                [w.value for w in warnings],
                [
                    "frontend/web/src/router/",
                    "backend/src/endpoints/",
                    "frontend/web/src/client.ts",
                ],
            )

    def test_python_stdlib_name_is_not_module_specifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "BUGBOT.md", "- Schematy w `json/schemas/`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([w.value for w in warnings], ["json/schemas/"])

    def test_bare_name_in_build_output_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "frontend/web/.next/manifest.ts", "")
            _write(workspace / "BUGBOT.md", "- Manifest: `manifest.ts`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([w.value for w in warnings], ["manifest.ts"])

    def test_missing_infra_file_with_known_extension_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "BUGBOT.md", "- Infra: `main.tf`, szablon `nginx.j2`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([w.value for w in warnings], ["main.tf", "nginx.j2"])

    def test_negation_after_backtick_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY + "- `features/orders/` nie istnieje po stronie web.\n",
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_removed_and_no_longer_phrases_silence_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY
                + "- `apps/example/` removed.\n"
                + "- Katalog `apps/legacy/` usunięty.\n"
                + "- `apps/old/` no longer exists.\n"
                + "- Removed: `apps/gone/`.\n"
                + "- `apps/a/`, `apps/b/` removed.\n",
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_removed_phrase_on_existing_path_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY + "- `backend/src/core/` removed.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual([w.kind for w in warnings], ["negated-path-exists"])

    def test_removed_word_does_not_silence_later_path_in_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY
                + "- `apps/example/` removed, kod w `backend/src/db/`.\n"
                + "- `apps/old/` removed, kod teraz w: `backend/src/models/`.\n"
                + "- Removed legacy app, moved to: `apps/new/`.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(
                [(w.kind, w.value) for w in warnings],
                [
                    ("stale-path", "backend/src/db/"),
                    ("stale-path", "backend/src/models/"),
                    ("stale-path", "apps/new/"),
                ],
            )

    def test_removal_phrase_with_continuation_is_not_negation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(
                workspace / ".ai" / "project.md",
                MONOREPO_OVERLAY
                + "- `backend/src/core/` no longer uses Celery.\n"
                + "- `backend/src/core/` removed from CI.\n"
                + "- `apps/ci/` usunięty z pipeline'u.\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual([(w.kind, w.value) for w in warnings], [("stale-path", "apps/ci/")])


OLD_BUGBOT = """\
# Bugbot

## Frontend

- UI w `frontend/web/components/ui/` musi być czyste.
- Klient z `frontend/src/api/generated/` regeneruj po zmianie API.
- Zmiana `app.json` wymaga buildu natywnego.
"""

OLD_AGENTS = """\
# AGENTS.md

Hooki: `.claude/hooks/gate-push.sh` i `.claude/hooks/gate-destructive.sh`.
"""


def _kit_with_history(tmp: str) -> Path:
    """Kit z gitem: stare wersje szablonów, potem aktualne (historia jak w `bugbot_md`)."""
    kit = Path(tmp) / "kit"
    bugbot = _write(kit / "templates" / "cursor" / "BUGBOT.md", OLD_BUGBOT)
    agents = _write(kit / "templates" / "AGENTS.md", OLD_AGENTS)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(kit), *args],
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )

    git("init", "-q")
    git("config", "user.email", "test@test.local")
    git("config", "user.name", "test")
    git("add", ".")
    git("commit", "-q", "-m", "old")
    _write(bugbot, "# Bugbot\n\n<!-- project:rules -->\n<!-- /project:rules -->\n")
    _write(agents, "# AGENTS.md\n\nGuardy: `git-guard.mjs`.\n")
    git("commit", "-q", "-am", "current")
    return kit


TIERED_OVERLAY = """\
## Ścieżki

- backend: `backend/`
- web: `frontend/web/`
"""


def _tiered(tmp: str) -> Path:
    """Backend + web; ``config/settings.json`` w obu Tierach, ``utils/date.ts`` tylko w web."""
    workspace = _workspace(tmp)
    for rel in (
        "backend/config/settings.json",
        "frontend/web/config/settings.json",
        "frontend/web/src/utils/date.ts",
    ):
        _write(workspace / rel, "")
    _write(workspace / ".ai" / "project.md", TIERED_OVERLAY)
    return workspace


class TestVerboseCandidates(unittest.TestCase):
    """#268: ``--verbose`` pokazuje kandydatów, gdy ścieżka pasuje do kilku miejsc."""

    def test_verbose_lists_candidates_when_path_matches_several_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "Ustawienia: `config/settings.json`.\n")

            report = run_doctor(workspace, clients="claude", verbose=True)

            self.assertEqual(report.warnings, (), report.render())
            [info] = [f for f in report.infos if f.kind == "path-candidates"]
            self.assertEqual((info.file, info.line, info.value), ("BUGBOT.md", 1, "config/settings.json"))
            self.assertIn("`backend/config/settings.json`", info.message)
            self.assertIn("`frontend/web/config/settings.json`", info.message)

    def test_without_verbose_ambiguous_path_adds_no_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "Ustawienia: `config/settings.json`.\n")

            report = _report(workspace)

            self.assertEqual(report.findings, (), report.render())

    def test_verbose_single_candidate_adds_no_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "Daty: `utils/date.ts`.\n")

            report = run_doctor(workspace, clients="claude", verbose=True)

            self.assertEqual(report.findings, (), report.render())


class TestTierScopedRoots(unittest.TestCase):
    """#268: ścieżka przy Tierze (nagłówek / prefiks linii) liczy się tylko w jego rootach."""

    def test_path_under_tier_heading_existing_only_in_other_tier_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "# Reguły\n\n## Backend\n\nDaty: `utils/date.ts`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([(w.kind, w.line, w.value) for w in warnings], [("stale-path", 5, "utils/date.ts")])

    def test_bare_name_under_tier_heading_existing_only_in_other_tier_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "## Backend\n\nDaty: `date.ts`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual([(w.kind, w.value) for w in warnings], [("stale-path", "date.ts")])

    def test_path_under_its_own_tier_heading_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "## Frontend (web)\n\n### Helpery\n\nDaty: `utils/date.ts`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_tier_line_prefix_overrides_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "## Backend\n\n- web: `utils/date.ts`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_heading_without_tier_resets_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "## Backend\n\n## Ogólne\n\nDaty: `utils/date.ts`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_verbose_candidates_are_limited_to_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "## Backend\n\nUstawienia: `config/settings.json`.\n")

            report = run_doctor(workspace, clients="claude", verbose=True)

            self.assertEqual(report.findings, (), report.render())


class TestStaleKitContent(unittest.TestCase):
    """#266: treść starej wersji szablonu kita to jedno zgłoszenie, nie N ścieżek."""

    def _kit(self, tmp: str) -> Path:
        try:
            return _kit_with_history(tmp)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("brak gita w środowisku")

    def test_bugbot_from_old_template_is_one_stale_kit_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            # Dopisana reguła (bez zmiany linii szablonu) — migracja pewna, nie #277.
            _write(workspace / "BUGBOT.md", OLD_BUGBOT + "- Nasza reguła projektu bez ścieżek.\n")

            warnings = run_doctor(workspace, kit, clients="claude").warnings

            self.assertEqual([w.kind for w in warnings], ["stale-kit-content"], warnings)
            self.assertEqual(warnings[0].file, "BUGBOT.md")
            # 3 reguły; krótki nagłówek `## Frontend` nie jest dowodem starej wersji.
            self.assertIn("3 linie", warnings[0].message)

    def test_agents_from_old_template_is_stale_kit_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            _write(workspace / "AGENTS.md", OLD_AGENTS)

            warnings = run_doctor(workspace, kit, clients="claude").warnings

            self.assertEqual([(w.kind, w.file) for w in warnings], [("stale-kit-content", "AGENTS.md")])

    def test_stale_agents_counts_for_mode_c(self) -> None:
        """#269: reload odświeża część kitową AGENTS.md, więc zgłoszenie jest do naprawy."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            _write(workspace / "AGENTS.md", OLD_AGENTS)

            report = run_doctor(workspace, kit, clients="claude")

            self.assertEqual(len(report.warnings), 1)
            self.assertEqual(report.fixable, report.warnings)
            self.assertIn('/kit-project-edit "napraw zgłoszenia doctora"', report.warnings[0].message)


class TestUncertainMigration(unittest.TestCase):
    """#277: niepewna migracja to jedno zgłoszenie z propozycją bloku projektu."""

    def _kit(self, tmp: str) -> Path:
        try:
            return _kit_with_history(tmp)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("brak gita w środowisku")

    def _uncertain(self, report, rel: str) -> list:
        return [w for w in report.warnings if w.kind == "uncertain-migration" and w.file == rel]

    def test_bugbot_changed_template_line_proposes_project_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            text = OLD_BUGBOT.replace("# Bugbot", "# Bugbot (nasz)") + "- Moja reguła A.\n"
            path = _write(workspace / "BUGBOT.md", text)

            report = run_doctor(workspace, kit, clients="claude")

            found = self._uncertain(report, "BUGBOT.md")
            self.assertEqual(len(found), 1, report.findings)
            self.assertEqual(found[0].value, "# Bugbot (nasz)\n- Moja reguła A.")
            self.assertIn("project:rules", found[0].message)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_bugbot_template_part_is_silenced(self) -> None:
        """Szablonowa część: bez `stale-path` / `stale-kit-content`; część projektu — bez zmian."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                OLD_BUGBOT.replace("# Bugbot", "# Bugbot (nasz)") + "- Patrz `docs/brak.md`.\n",
            )

            warnings = run_doctor(workspace, kit, clients="claude").warnings

            self.assertEqual(
                [(w.kind, w.value) for w in warnings if w.kind != "uncertain-migration"],
                [("stale-path", "docs/brak.md")],
                warnings,
            )

    def test_bugbot_over_limit_proposes_full_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            added = [f"- reguła projektu {i}" for i in range(MAX_MIGRATED_LINES + 1)]
            _write(workspace / "BUGBOT.md", OLD_BUGBOT + "\n" + "\n".join(added) + "\n")

            found = self._uncertain(run_doctor(workspace, kit, clients="claude"), "BUGBOT.md")

            self.assertEqual(len(found), 1)
            self.assertEqual((found[0].value or "").splitlines(), added)

    def test_without_template_history_no_uncertain_migration(self) -> None:
        """Kit bez gita (koło): brak propozycji — zostaje linia reloadu (`bugbot_md`)."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            _write(kit / "templates" / "cursor" / "BUGBOT.md", "# Bugbot\n\n<!-- project:rules -->\n<!-- /project:rules -->\n")
            _write(kit / "templates" / "AGENTS.md", "# AGENTS.md\n")
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", OLD_BUGBOT.replace("# Bugbot", "# Bugbot (nasz)"))
            _write(workspace / "AGENTS.md", OLD_AGENTS.replace("# AGENTS.md", "# AGENTS (nasz)"))

            report = run_doctor(workspace, kit, clients="claude")

            self.assertEqual([w for w in report.warnings if w.kind == "uncertain-migration"], [])

    def test_agents_changed_template_line_proposes_project_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            text = OLD_AGENTS.replace("# AGENTS.md", "# AGENTS (nasz)") + "Nasza zasada A.\n"
            path = _write(workspace / "AGENTS.md", text)

            report = run_doctor(workspace, kit, clients="claude")

            found = self._uncertain(report, "AGENTS.md")
            self.assertEqual(len(found), 1, report.findings)
            self.assertEqual(found[0].value, "# AGENTS (nasz)\nNasza zasada A.")
            self.assertIn("project:agents", found[0].message)
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            # `.claude/hooks/…` z szablonowej części nie istnieją — wyciszone.
            self.assertEqual(
                [w.kind for w in report.warnings if w.file == "AGENTS.md"],
                ["uncertain-migration"],
            )

    def test_agents_aside_section_is_not_silenced(self) -> None:
        """`## Agent skills` to treść spoza szablonu — jej zgłoszenia zostają (review #277)."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            _write(
                workspace / "AGENTS.md",
                OLD_AGENTS.replace("# AGENTS.md", "# AGENTS (nasz)")
                + "\n## Agent skills\n\nSee `docs/agents/brak.md`.\n",
            )

            warnings = run_doctor(workspace, kit, clients="claude").warnings

            self.assertEqual(
                [(w.kind, w.value) for w in warnings if w.kind != "uncertain-migration"],
                [("stale-path", "docs/agents/brak.md")],
                warnings,
            )

    def test_only_removed_template_lines_says_what_to_do(self) -> None:
        """Pusta propozycja: komunikat mówi, że wystarczy pusty blok i reload (review #277)."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", OLD_BUGBOT.replace("- Zmiana `app.json` wymaga buildu natywnego.\n", ""))

            found = self._uncertain(run_doctor(workspace, kit, clients="claude"), "BUGBOT.md")

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].value, "")
            self.assertIn("brak linii projektu", found[0].message)
            self.assertIn("pusty blok project:rules", found[0].message)

    def test_real_kit_project_line_keeps_stale_path(self) -> None:
        """Kit z historią (repo kita): linia projektu w pliku bez bloku nadal daje `stale-path`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "Reguła: `docs/brak.md`.\n")

            kinds = [w.kind for w in run_doctor(workspace, KIT_ROOT, clients="claude").warnings]

            self.assertIn("stale-path", kinds)
            if read_template_history(KIT_ROOT, "templates/cursor/BUGBOT.md"):
                self.assertIn("uncertain-migration", kinds)

    def test_agents_over_limit_proposes_full_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit(tmp)
            workspace = _workspace(tmp)
            added = [f"Zasada projektu numer {i}." for i in range(MAX_MIGRATED_LINES + 1)]
            _write(workspace / "AGENTS.md", OLD_AGENTS + "\n" + "\n".join(added) + "\n")

            found = self._uncertain(run_doctor(workspace, kit, clients="claude"), "AGENTS.md")

            self.assertEqual(len(found), 1)
            self.assertEqual((found[0].value or "").splitlines(), added)


class TestBugbotPathKeys(unittest.TestCase):
    """#266: reguła szablonu na ścieżce domyślnej, której nie ma — `missing-path-key`."""

    TEMPLATE = (KIT_ROOT / "templates" / "cursor" / "BUGBOT.md").read_text(encoding="utf-8")

    def test_missing_key_with_absent_default_warns_with_detected_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "backend").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "# Overlay\n")
            _write(workspace / "BUGBOT.md", render_bugbot(self.TEMPLATE, "backend"))

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            self.assertEqual([w.kind for w in warnings], ["missing-path-key"], warnings)
            self.assertEqual(warnings[0].value, "backend")
            self.assertEqual(warnings[0].suggestion, "apps/backend/")

    def test_client_keys_missing_with_absent_defaults_warn(self) -> None:
        """#270: `ui:`/`web:`/`mobile:`/`api-generated:` bez klucza i bez domyślnej."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "web" / "src" / "components" / "ui").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- backend: `apps/`\n")
            _write(workspace / "BUGBOT.md", render_bugbot(self.TEMPLATE, "backend client"))

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            by_key = {w.value: w for w in warnings if w.kind == "missing-path-key"}
            self.assertEqual(set(by_key), {"ui", "web", "mobile", "api-generated"}, warnings)
            self.assertEqual(by_key["ui"].suggestion, "apps/web/src/components/ui/")

    def test_key_set_for_one_placeholder_still_reports_its_neighbour(self) -> None:
        """Klucz `web:` ustawiony, `mobile:` nie — linia z obiema ścieżkami nadal sprawdzana."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "web" / "src" / "components" / "ui").mkdir(parents=True)
            overlay = "## Ścieżki\n\n- web: `apps/web/`\n"
            _write(workspace / ".ai" / "project.md", overlay)
            _write(
                workspace / "BUGBOT.md",
                render_bugbot(self.TEMPLATE, "client", paths={"web": "apps/web/"}),
            )

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            self.assertEqual(
                [w.value for w in warnings if w.kind == "missing-path-key"], ["mobile"], warnings
            )

    def test_derived_ui_path_under_web_key_is_silent(self) -> None:
        """#280: `web: apps/web/` + istniejące `apps/web/src/components/ui/` → bez `ui`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "web" / "src" / "components" / "ui").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- web: `apps/web/`\n")
            _write(
                workspace / "BUGBOT.md",
                render_bugbot(self.TEMPLATE, "client", paths={"web": "apps/web/"}),
            )

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            keys = [w.value for w in warnings if w.kind == "missing-path-key"]
            self.assertNotIn("ui", keys, warnings)

    def test_derived_default_is_reported_rendered(self) -> None:
        """#280: zgłoszenie mówi o wyrenderowanej pochodnej, nie o `@web/…`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "web").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- web: `apps/web/`\n")
            _write(
                workspace / "BUGBOT.md",
                render_bugbot(self.TEMPLATE, "client", paths={"web": "apps/web/"}),
            )

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            [ui] = [w for w in warnings if w.kind == "missing-path-key" and w.value == "ui"]
            self.assertIn("`apps/web/src/components/ui/`", ui.message)

    def test_several_candidates_are_listed(self) -> None:
        """#280: kilku kandydatów → lista w zgłoszeniu, bez `suggestion`."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            for app in ("admin", "shop"):
                (workspace / "apps" / app / "src" / "components" / "ui").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "# Overlay\n")
            _write(workspace / "BUGBOT.md", render_bugbot(self.TEMPLATE, "client"))

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            [ui] = [w for w in warnings if w.kind == "missing-path-key" and w.value == "ui"]
            self.assertIsNone(ui.suggestion)
            self.assertIn("`apps/admin/src/components/ui/`", ui.message)
            self.assertIn("`apps/shop/src/components/ui/`", ui.message)

    def test_codegen_output_alias_satisfies_api_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "gen").mkdir()
            for default in ("backend", "frontend/web/src/components/ui", "frontend/mobile"):
                (workspace / default).mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- codegen-output: `gen/`\n")
            rendered = render_bugbot(
                self.TEMPLATE, "backend client", paths={"api-generated": "gen/"}
            )
            self.assertIn("`gen/`", rendered)
            _write(workspace / "BUGBOT.md", rendered)

            self.assertEqual(run_doctor(workspace, KIT_ROOT, clients="claude").warnings, ())

    def test_rendered_template_does_not_read_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "backend").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- backend: `apps/backend/`\n")
            _write(
                workspace / "BUGBOT.md",
                render_bugbot(self.TEMPLATE, "backend", paths={"backend": "apps/backend/"}),
            )

            with mock.patch("guides.doctor.read_template_history") as history:
                run_doctor(workspace, KIT_ROOT, clients="claude")

            history.assert_not_called()

    def test_rendered_overlay_path_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            (workspace / "apps" / "backend").mkdir(parents=True)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- backend: `apps/backend/`\n")
            _write(
                workspace / "BUGBOT.md",
                render_bugbot(self.TEMPLATE, "backend", paths={"backend": "apps/backend/"}),
            )

            self.assertEqual(run_doctor(workspace, KIT_ROOT, clients="claude").warnings, ())


class TestCommands(unittest.TestCase):
    def test_command_without_agent_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "# Bugbot\n\nUruchom `/review-security`.\n")

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertEqual(warnings[0].line, 3)
            self.assertIn("/review-security", warnings[0].message)
            self.assertIn("claude", warnings[0].message)

    def test_command_with_installed_skill_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / ".claude" / "skills" / "review-security" / "SKILL.md",
                "---\nname: review-security\n---\n",
            )
            _write(workspace / "BUGBOT.md", "Uruchom `/review-security`.\n")

            self.assertEqual(_report(workspace).warnings, ())

    def test_command_only_for_unconfigured_client_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / ".cursor" / "skills" / "review-security" / "SKILL.md",
                "---\nname: review-security\n---\n",
            )
            _write(workspace / "BUGBOT.md", _rules_block("Uruchom `/review-security`."))

            warnings = run_doctor(workspace, KIT_ROOT, clients="claude").warnings

            self.assertEqual(len(warnings), 1, warnings)

    def test_external_layer_commands_are_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                "Niejasny scope → `/grill-me`; test-first → `/tdd`; etykiety → `/triage`.\n",
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_kit_templates_are_not_checked_in_app_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            kit = Path(tmp) / "kit"
            _write(kit / "manifest.yaml", "modules: {}\n")
            _write(
                kit / "templates" / "shared" / "agents" / "review-custom.md",
                "Uruchom `/review-ghost`.\n",
            )

            self.assertEqual(run_doctor(workspace, kit, clients="claude").warnings, ())

    def test_commands_from_kit_agent_templates_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = _workspace(tmp)
            _write(kit / "manifest.yaml", "modules: {}\n")
            _write(
                kit / "templates" / "shared" / "agents" / "review-custom.md",
                "Uruchom `/review-ghost`.\n",
            )

            warnings = run_doctor(kit, kit, clients="claude").warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("templates/shared/agents/review-custom.md:1", warnings[0].render())
            self.assertIn("/review-ghost", warnings[0].message)


class TestWorkspacePackages(unittest.TestCase):
    def test_npm_workspace_package_is_information(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "package.json",
                json.dumps({"workspaces": ["packages/*"]}) + "\n",
            )
            _write(workspace / "packages" / "foo" / "package.json", "{}\n")
            _write(workspace / ".ai" / "project.md", "# Overlay\n\n## Ścieżki\n\n- web: `apps/`\n")
            _write(workspace / "apps" / "package.json", "{}\n")

            report = _report(workspace)

            self.assertEqual(report.warnings, ())
            self.assertEqual(len(report.infos), 1, report.render())
            self.assertIn("packages/foo/", report.infos[0].message)
            self.assertIn("doctor: INFO", report.render())

    def test_described_package_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "package.json",
                json.dumps({"workspaces": ["packages/*"]}) + "\n",
            )
            _write(workspace / "packages" / "foo" / "package.json", "{}\n")
            _write(
                workspace / ".ai" / "project.md",
                "# Overlay\n\nPakiety: `packages/foo/`.\n",
            )

            self.assertEqual(_report(workspace).findings, ())

    def test_pnpm_and_uv_workspaces_are_read(self) -> None:
        cases = {
            "pnpm": (
                "pnpm-workspace.yaml",
                "packages:\n  - 'libs/*'\n",
                "libs/core",
            ),
            "uv": (
                "pyproject.toml",
                "[tool.uv.workspace]\nmembers = [\"libs/*\"]\n",
                "libs/core",
            ),
        }
        for name, (filename, content, member) in cases.items():
            with self.subTest(workspace=name), tempfile.TemporaryDirectory() as tmp:
                workspace = _workspace(tmp)
                _write(workspace / filename, content)
                _write(workspace / member / "package.json", "{}\n")

                report = _report(workspace)

                self.assertEqual(report.warnings, ())
                self.assertEqual(len(report.infos), 1, report.render())


class TestNeverBlocks(unittest.TestCase):
    def test_bogus_clients_falls_back_to_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)

            rendered = run_doctor(workspace, clients="bogus").render()

            self.assertIn("clients", rendered)
            self.assertIn("bogus", rendered)

    def test_odd_workspace_patterns_do_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "package.json",
                json.dumps({"workspaces": {"packages": "packages/*"}}),
            )
            _write(workspace / "pnpm-workspace.yaml", "packages:\n  - /abs/*\n  - ''\n")
            _write(
                workspace / "pyproject.toml",
                '[tool.uv.workspace]\nmembers = "packages/*"\n',
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_absolute_npm_workspace_pattern_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "package.json", json.dumps({"workspaces": ["/abs/*", ""]}))

            self.assertEqual(_report(workspace).infos, ())


class TestStaleProjectBrief(unittest.TestCase):
    """Brief w AGENTS.md musi odpowiadać Profilowi i overlayowi (#307)."""

    def _agents_with_brief(self, brief: str) -> str:
        template = (KIT_ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        return render_bugbot(template, "", block="agents", brief=brief)

    def test_current_brief_has_no_finding(self) -> None:
        from guides.resolver import resolve_workspace_profile

        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / ".ai" / "project.md", "# Overlay\n\nbase: dev\n")
            resolved = resolve_workspace_profile(workspace, kit_root=KIT_ROOT)
            _write(workspace / "AGENTS.md", self._agents_with_brief(resolved.project_brief))

            report = run_doctor(workspace, KIT_ROOT, clients="claude")

        self.assertNotIn("stale-project-brief", {finding.kind for finding in report.findings})

    def test_outdated_brief_warns_with_reload_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / ".ai" / "project.md", "# Overlay\n\nbase: dev\n")
            _write(workspace / "AGENTS.md", self._agents_with_brief("> stary brief"))

            report = run_doctor(workspace, KIT_ROOT, clients="claude")

        findings = [f for f in report.findings if f.kind == "stale-project-brief"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].file, "AGENTS.md")
        self.assertIn("reload", findings[0].message)


class TestReport(unittest.TestCase):
    def test_clean_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)

            rendered = _report(workspace).render()

            self.assertTrue(rendered.startswith("doctor:"))
            self.assertIn("brak zgłoszeń", rendered)

    def test_every_line_has_doctor_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "`src/missing/`\n")

            rendered = _report(workspace).render()

            for line in rendered.splitlines():
                self.assertTrue(line.startswith("doctor:"), line)


class TestCli(unittest.TestCase):
    def _main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_doctor_command_reports_warning_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "`src/missing/`\n")

            code, out = self._main("doctor", str(workspace))

            self.assertEqual(code, 0, out)
            self.assertIn("doctor: OSTRZEŻENIE BUGBOT.md:1", out)

    def test_reload_with_warnings_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                "# Bugbot\n\n<!-- project:rules -->\nReguła: `src/missing/`.\n"
                "<!-- /project:rules -->\n",
            )

            code, out = self._main("reload", str(workspace))

            self.assertEqual(code, 0, out)
            self.assertIn("doctor:", out)
            self.assertIn("src/missing/", out)


    def test_reload_with_warnings_points_to_mode_c_and_writes_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- web: `frontend/web/`\n")
            state = workspace / ".ai" / ".kit-doctor.json"

            code, out = self._main("reload", str(workspace))

            self.assertEqual(code, 0, out)
            self.assertEqual(
                out.rstrip().splitlines()[-1],
                'doctor: 1 do naprawy → /kit-project-edit "napraw zgłoszenia doctora"',
            )
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["warnings"], 1)

            (workspace / "frontend" / "web").mkdir(parents=True)
            code, out = self._main("reload", str(workspace))

            self.assertEqual(code, 0, out)
            self.assertNotIn("do naprawy", out)
            self.assertFalse(state.exists())

    def test_doctor_json_lists_kind_value_and_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _monorepo(tmp)
            _write(workspace / "BUGBOT.md", _rules_block("UI: `frontend/web/components/ui/`."))

            code, out = self._main("doctor", str(workspace), "--json")

            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertEqual(data["warnings"], 1, out)
            [finding] = [f for f in data["findings"] if f["severity"] == "warning"]
            self.assertEqual(
                {k: finding[k] for k in ("kind", "file", "line", "value", "suggestion")},
                {
                    "kind": "stale-path",
                    "file": "BUGBOT.md",
                    "line": 2,
                    "value": "frontend/web/components/ui/",
                    "suggestion": "frontend/web/src/components/ui/",
                },
            )

    def test_doctor_verbose_prints_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _tiered(tmp)
            _write(workspace / "BUGBOT.md", "Ustawienia: `config/settings.json`.\n")

            code, out = self._main("doctor", str(workspace), "--verbose")

            self.assertEqual(code, 0, out)
            self.assertIn("backend/config/settings.json", out)
            self.assertIn("frontend/web/config/settings.json", out)

    def test_doctor_with_bogus_profile_clients_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(PROFILE.replace("clients: claude", "clients: bogus"), encoding="utf-8")

            code, out = self._main("doctor", str(workspace))

            self.assertEqual(code, 0, out)
            self.assertIn("doctor:", out)

    def test_doctor_report_never_raises(self) -> None:
        with mock.patch.object(cli, "run_doctor", side_effect=RuntimeError("boom")):
            out = cli.doctor_report(Path("."), KIT_ROOT)

        self.assertEqual(out, "doctor: błąd RuntimeError: boom")


class TestReadmeVerification(unittest.TestCase):
    """#268: sekcja „Weryfikacja” README opisuje zachowanie doctora."""

    def test_verification_section_covers_doctor_behaviour(self) -> None:
        text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        section = text.split("### 3. Weryfikacja", 1)[1].split("\n### ", 1)[0]

        for needle in (
            "`stale-path`",
            "`negated-path-exists`",
            "`stale-kit-content`",
            "`missing-path-key`",
            "kit-ai doctor --json",
            "kit-ai doctor --verbose",
            "`path-candidates`",
            ".ai/.kit-doctor.json",
            "Tier",
        ):
            self.assertIn(needle, section)


class TestKitProjectEditMode(unittest.TestCase):
    """`/kit-project-edit` ma tryb naprawy zgłoszeń doctora (#242)."""

    def test_mode_c_fixes_overlay_and_project_rules(self) -> None:
        text = (
            KIT_ROOT / "templates" / "shared" / "agents" / "kit-project-edit.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Tryb C — napraw zgłoszenia doctora", text)
        self.assertIn("napraw zgłoszenia doctora", text)
        self.assertIn("project:rules", text)
        self.assertIn("kit-ai doctor", text)
        self.assertIn("Nie edytuj szablonowych sekcji `BUGBOT.md`", text)
        # #266: partia z pliku stanu reloadu / `--json`, jeden podgląd, start bez prośby.
        self.assertIn(".ai/.kit-doctor.json", text)
        self.assertIn("kit-ai doctor --json", text)
        self.assertIn("Jeden podgląd na całą partię", text)
        # #277: niepewna migracja — propozycja bloku projektu, zapis po akceptacji.
        self.assertIn("| `uncertain-migration`", text)
        # #280: kilku kandydatów dla `missing-path-key` — wybór z listy.
        row = next(line for line in text.splitlines() if line.startswith("   | `missing-path-key`"))
        self.assertIn("kandydaci w drzewie", row)
        self.assertIn("do wyboru", row)


class TestMcpReload(unittest.TestCase):
    def test_reload_workspace_with_warnings_tells_agent_to_run_mode_c(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "<!-- project:rules -->\n`src/missing/`\n<!-- /project:rules -->\n")

            with (
                mock.patch.object(server, "_workspace_root", workspace),
                mock.patch.object(server, "_kit_root", KIT_ROOT),
            ):
                out = server.reload_workspace(dry_run=False)

            self.assertIn("doctor: OSTRZEŻENIE", out)
            self.assertIn('Uruchom teraz `/kit-project-edit "napraw zgłoszenia doctora"`', out)


class TestMcpStatus(unittest.TestCase):
    def test_check_kit_status_appends_doctor_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "BUGBOT.md", "`src/missing/`\n")

            with (
                mock.patch.object(server, "_workspace_root", workspace),
                mock.patch.object(server, "_kit_root", KIT_ROOT),
            ):
                out = server.check_kit_status()

            self.assertIn("Kit status", out)
            self.assertIn("doctor: OSTRZEŻENIE BUGBOT.md:1", out)


if __name__ == "__main__":
    unittest.main()
