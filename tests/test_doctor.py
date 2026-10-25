"""Testy ``doctor`` — rozjazd ścieżek i komend w regułach projektu z repo (#242)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guides import cli, server
from guides.doctor import run_doctor

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


class TestOverlayPaths(unittest.TestCase):
    def test_missing_overlay_directory_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / "backend", "")
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

    def test_overlay_file_path_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / ".ai" / "project.md",
                "## Ścieżki\n\n- Taskfile: `Taskfile.yml` — punkt wejścia\n",
            )

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("Taskfile:", warnings[0].message)

    def test_overlay_path_is_not_reported_twice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(workspace / ".ai" / "project.md", "## Ścieżki\n\n- backend: `backend/`\n")

            warnings = _report(workspace).warnings

            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("backend:", warnings[0].message)


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
            _write(workspace / "BUGBOT.md", "Uruchom `/review-security`.\n")

            self.assertEqual(len(_report(workspace, clients="claude").warnings), 1)

    def test_external_layer_commands_are_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            _write(
                workspace / "BUGBOT.md",
                "Niejasny scope → `/grill-me`; test-first → `/tdd`; etykiety → `/triage`.\n",
            )

            self.assertEqual(_report(workspace).warnings, ())

    def test_commands_from_kit_agent_templates_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _workspace(tmp)
            kit = Path(tmp) / "kit"
            _write(
                kit / "templates" / "shared" / "agents" / "review-custom.md",
                "Uruchom `/review-ghost`.\n",
            )

            warnings = run_doctor(workspace, kit, clients="claude").warnings

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
