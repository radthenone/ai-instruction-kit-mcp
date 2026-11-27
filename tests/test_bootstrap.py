"""Szybkie testy jednostkowe bootstrapa oraz wspólna baza testów E2E.

Testy w tym module wywołują bezpośrednio funkcje z ``guides.bootstrap`` w pamięci
(scalanie ``codex.toml``, JSON, sekcja ``.gitignore``, dobór agentów i dziedziczenie
modelu OpenCode) bez uruchamiania ``scripts/bootstrap-project.sh`` przez basha.
Suity integracyjne powłoki są rozbite na ``tests/test_bootstrap_*.py``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _shell import is_ci, resolve_bash

from guides import server
from guides.bootstrap import (
    detect_profile_tiers,
    find_bash,
    inherit_opencode_model,
    load_jsonc,
    merge_gitignore_text,
    merge_json_config,
    merge_toml_config,
    render_gitignore_section,
    render_mcp_template,
    stage_shared_agents,
    sync_gitignore_file,
    sync_mcp_file,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
KIT_SKILLS_TEMPLATE = (KIT_ROOT / "templates" / "gitignore-kit.txt").read_text(encoding="utf-8")

_MACHINE_FILES = (
    ".mcp.json",
    ".cursor/mcp.json",
    ".vscode/mcp.json",
    ".codex/config.toml",
    ".kiro/settings/mcp.json",
    ".kilocode/mcp.json",
    ".agents/mcp_config.json",
    "opencode.json",
    ".ai/.kit-bootstrap.json",
    ".ai/.kit-doctor.json",
)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Zawartość wszystkich plików pod ``root`` — do porównania „nic nie ruszono”."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class _BootstrapTestCase(unittest.TestCase):
    """Wspólny strażnik dostępności basha dla suit integracyjnych ``test_bootstrap_*``."""

    # Render starej wersji szablonu BUGBOT.md — bez bloku `project:rules`.
    OLD_TEMPLATE = """# Bugbot — reguły projektu

Intro (stara wersja szablonu).

## Ogólne

- stara reguła kita

<!-- tier:backend -->
## Backend

- stara reguła backendu
<!-- /tier:backend -->
"""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI — bootstrap musi się wykonać")
            self.skipTest("brak bash / Git for Windows w PATH")
        # Globalny config opencode z tej maszyny nie może przeciekać do wyniku (#167).
        config_home = tempfile.TemporaryDirectory()
        self.addCleanup(config_home.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config_home.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _git(self, cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()

    def _kit_with_history(self, root: Path) -> Path:
        """Kopia kita z commitem starego szablonu — do testu migracji."""
        for rel in ("templates", "scripts", "src", "manifest.yaml"):
            src = KIT_ROOT / rel
            if src.is_dir():
                shutil.copytree(
                    src,
                    root / rel,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            elif src.is_file():
                root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, root / rel)
        try:
            self._git(root, "init", "-q")
        except FileNotFoundError:
            self.skipTest("brak gita w środowisku")
        self._git(root, "config", "user.email", "test@test.local")
        self._git(root, "config", "user.name", "test")
        template = root / "templates" / "cursor" / "BUGBOT.md"
        template.write_text(self.OLD_TEMPLATE, encoding="utf-8", newline="\n")
        self._git(root, "add", ".")
        self._git(root, "commit", "-q", "-m", "old template")
        return root


class TestFindBash(unittest.TestCase):
    """Wykrywanie interpretera bash w Pythonie."""

    def test_find_bash_points_at_existing_interpreter(self) -> None:
        """Na Windows to ma być konkretny bash.exe, nie samo słowo `bash`."""
        bash = find_bash()
        self.assertTrue(bash)
        if bash != "bash":
            self.assertTrue(Path(bash).is_file())


class TestJsonConfigMergeUnit(unittest.TestCase):
    """Scalanie konfiguracji JSON klientów MCP bez uruchamiania basha (#160)."""

    def _render(self, template_rel: str, clients_arg: str) -> str:
        src = KIT_ROOT / template_rel
        return render_mcp_template(
            src.read_text(encoding="utf-8"),
            from_src=str(KIT_ROOT),
            language="pl",
            clients_arg=clients_arg,
            workspace_repl="/tmp/app",
        )

    def test_json_configs_keep_user_servers_and_keys(self) -> None:
        """Reload podmienia tylko wpis kita, zachowuje serwery i klucze użytkownika."""
        mine = {"command": "my-server"}
        cases = {
            "templates/claude/mcp.json": ("mcpServers", {}),
            "templates/vscode/mcp.json": ("servers", {"inputs": []}),
            "templates/opencode/opencode.json": ("mcp", {"model": "anthropic/claude-x"}),
        }
        for template_rel, (key, extra) in cases.items():
            with self.subTest(template=template_rel):
                new_text = self._render(template_rel, "claude,vscode,opencode")
                data = json.loads(new_text)
                data[key]["mine"] = mine
                data[key]["kit-ai-mcp"] = {"command": "stale"}
                data[key]["project-guides"] = {"command": "legacy"}
                data.update(extra)

                merged = json.loads(merge_json_config(json.dumps(data), new_text))
                self.assertEqual(merged[key]["mine"], mine)
                self.assertNotEqual(merged[key]["kit-ai-mcp"], {"command": "stale"})
                self.assertNotIn("project-guides", merged[key])
                for k, v in extra.items():
                    self.assertEqual(merged[k], v)

    def test_unchanged_config_is_not_rewritten(self) -> None:
        """Niezmieniony plik JSON nie jest nadpisywany (zachowane formatowanie i mtime)."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            dest = workspace / ".mcp.json"
            src = KIT_ROOT / "templates/claude/mcp.json"

            sync_mcp_file(
                src,
                dest,
                from_src=str(KIT_ROOT),
                language="pl",
                clients_arg="claude",
            )
            data = json.loads(dest.read_text(encoding="utf-8"))
            data["mcpServers"]["mine"] = {"command": "x"}
            custom_text = json.dumps(data, indent=4)
            dest.write_text(custom_text, encoding="utf-8")

            warning = sync_mcp_file(
                src,
                dest,
                from_src=str(KIT_ROOT),
                language="pl",
                clients_arg="claude",
            )
            self.assertIsNone(warning)
            self.assertEqual(dest.read_text(encoding="utf-8"), custom_text)

    def test_unparseable_config_goes_to_bak(self) -> None:
        """Nieparsowalny JSONC trafia do ``.bak``, a wynikowy plik ma świeży wpis kita."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            dest = workspace / "opencode.json"
            original = '{\n  // komentarz JSONC\n  "mcp": {}\n}\n'
            dest.write_text(original, encoding="utf-8")

            warning = sync_mcp_file(
                KIT_ROOT / "templates/opencode/opencode.json",
                dest,
                from_src=str(KIT_ROOT),
                language="pl",
                clients_arg="opencode",
                workspace_repl=workspace.as_posix(),
            )

            self.assertIsNotNone(warning)
            assert warning is not None
            self.assertIn("opencode.json.bak", warning)
            self.assertEqual((workspace / "opencode.json.bak").read_text(encoding="utf-8"), original)
            self.assertIn("kit-ai-mcp", json.loads(dest.read_text(encoding="utf-8"))["mcp"])


class TestCodexTomlMergeUnit(unittest.TestCase):
    """Przypadki brzegowe scalania ``.codex/config.toml`` w pamięci (#160, #580)."""

    def _base_toml(self) -> str:
        return render_mcp_template(
            (KIT_ROOT / "templates/codex/config.toml").read_text(encoding="utf-8"),
            from_src=str(KIT_ROOT),
            language="pl",
            clients_arg="codex",
            workspace_repl="/tmp/app",
        )

    def test_codex_toml_keeps_user_tables(self) -> None:
        """Własne pola i tabele użytkownika zostają, wpis kita jest podmieniany."""
        base = self._base_toml()
        stale = base.replace('"guides-mcp"', '"stale"')
        mine = '# mój serwer\n[mcp_servers.mine]\ncommand = "x"\n'
        old_text = 'model = "o3"\n\n' + stale + "\n" + mine

        merged = merge_toml_config(old_text, base)
        self.assertIn('model = "o3"', merged)
        self.assertIn(mine, merged)
        self.assertIn('"guides-mcp"', merged)
        self.assertNotIn('"stale"', merged)
        self.assertEqual(merged.count("[mcp_servers.kit-ai-mcp]"), 1)

    def test_codex_toml_drops_legacy_kit_table(self) -> None:
        """Podtabela legacy oddzielona cudzą tabelą zostaje w całości usunięta."""
        base = self._base_toml()
        legacy = (
            '\n[mcp_servers.project-guides]\ncommand = "old"\n'
            '\n[mcp_servers.mine]\ncommand = "x"\n'
            '\n[mcp_servers.project-guides.env]\nKEY = "old"\n'
        )
        merged = merge_toml_config(base + legacy, base)
        self.assertNotIn("project-guides", merged)
        self.assertNotIn('"old"', merged)
        self.assertIn('[mcp_servers.mine]\ncommand = "x"\n', merged)
        self.assertEqual(merged.count("[mcp_servers.kit-ai-mcp]"), 1)

    def test_codex_toml_keeps_legacy_header_inside_multiline_string(self) -> None:
        """Nagłówek tabeli legacy wewnątrz ciągu wielowierszowego nie jest traktowany jako tabela."""
        base = self._base_toml()
        mine = (
            '\n[mcp_servers.mine.env]\nEXAMPLE = """\n'
            '[mcp_servers.project-guides]\ncommand = "example"\n[other]\n"""\n'
        )
        merged = merge_toml_config(base + mine, base)
        self.assertIn(mine, merged)

    def test_codex_toml_comment_delimiter_does_not_hide_next_table(self) -> None:
        """Ogranicznik ciągu w komentarzu TOML nie otwiera ciągu wielowierszowego."""
        base = self._base_toml()
        legacy = '\n[mcp_servers.project-guides]\ncommand = "old"\n# """\n'
        mine = '[mcp_servers.mine]\ncommand = "x"\n'
        merged = merge_toml_config(base + legacy + mine, base)
        self.assertNotIn("project-guides", merged)
        self.assertIn(mine, merged)

    def test_codex_toml_escaped_backslash_closes_multiline_string(self) -> None:
        """Parzyste ukośniki przed ``\"\"\"`` pozwalają na zamknięcie ciągu wielowierszowego."""
        base = self._base_toml()
        legacy = '\n[mcp_servers.project-guides]\ncommand = """path\\\\"""\n'
        mine = '[mcp_servers.mine]\ncommand = "x"\n'
        merged = merge_toml_config(base + legacy + mine, base)
        self.assertNotIn("project-guides", merged)
        self.assertIn(mine, merged)

    def test_codex_toml_extra_closing_quotes_end_multiline_string(self) -> None:
        """Dodatkowe cudzysłowy na końcu ``\"\"\"\"`` zamykają ciąg wielowierszowy."""
        base = self._base_toml()
        legacy = '\n[mcp_servers.project-guides]\nargs = ["""old"""", """next"""]\n'
        mine = '[mcp_servers.mine]\ncommand = "x"\n'
        merged = merge_toml_config(base + legacy + mine, base)
        self.assertNotIn("project-guides", merged)
        self.assertIn(mine, merged)

    def test_codex_toml_unsafe_merge_falls_back_to_bak(self) -> None:
        """Niezgodność danych poza kitem po scalaniu odkłada oryginał do ``.bak``."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            codex_dir = workspace / ".codex"
            codex_dir.mkdir(parents=True)
            path = codex_dir / "config.toml"
            base = self._base_toml()
            legacy = '\n[mcp_servers.project-guides]\nargs = [\n  [1, 2]\n]\n'
            mine = '[mcp_servers.mine]\ncommand = "x"\n'
            path.write_text(base + legacy + mine, encoding="utf-8")

            warning = sync_mcp_file(
                KIT_ROOT / "templates/codex/config.toml",
                path,
                from_src=str(KIT_ROOT),
                language="pl",
                clients_arg="codex",
                workspace_repl=workspace.as_posix(),
            )

            self.assertIsNotNone(warning)
            backup = codex_dir / "config.toml.bak"
            self.assertTrue(backup.is_file())
            self.assertIn(mine, backup.read_text(encoding="utf-8"))

    def test_codex_toml_keeps_quoted_server_with_legacy_prefix(self) -> None:
        """Tabela o nazwie z prefiksem legacy w cudzysłowie nie jest usuwana."""
        base = self._base_toml()
        helper = '\n[mcp_servers."project-guides.helper"]\ncommand = "helper"\n'
        merged = merge_toml_config(base + helper, base)
        self.assertIn(helper, merged)

    def test_codex_toml_without_tomllib_falls_back_to_bak(self) -> None:
        """Brak ``tomllib`` przy obecnej tabeli kita/legacy przerywa scalanie i robi ``.bak`` (#580)."""
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            with tempfile.TemporaryDirectory() as tmp:
                for server_name in ("project-guides", "kit-ai-mcp"):
                    with self.subTest(server_name=server_name):
                        workspace = Path(tmp) / f"app-{server_name}"
                        codex_dir = workspace / ".codex"
                        codex_dir.mkdir(parents=True)
                        original = (
                            f'[mcp_servers.{server_name}]\ncommand = "old"\n\n'
                            '[mcp_servers.mine]\ncommand = "x"\n'
                        )
                        (codex_dir / "config.toml").write_text(original, encoding="utf-8")

                        warning = sync_mcp_file(
                            KIT_ROOT / "templates/codex/config.toml",
                            codex_dir / "config.toml",
                            from_src=str(KIT_ROOT),
                            language="pl",
                            clients_arg="codex",
                            workspace_repl=workspace.as_posix(),
                        )

                        self.assertIsNotNone(warning)
                        assert warning is not None
                        backup = codex_dir / "config.toml.bak"
                        self.assertTrue(backup.is_file())
                        self.assertEqual(backup.read_text(encoding="utf-8"), original)
                        self.assertIn("config.toml.bak", warning)
                        self.assertIn("3.11+", warning)

                clean_ws = Path(tmp) / "app-foreign-only"
                (clean_ws / ".codex").mkdir(parents=True)
                foreign_cfg = '[mcp_servers.mine]\ncommand = "x"\n'
                (clean_ws / ".codex" / "config.toml").write_text(foreign_cfg, encoding="utf-8")

                warning = sync_mcp_file(
                    KIT_ROOT / "templates/codex/config.toml",
                    clean_ws / ".codex" / "config.toml",
                    from_src=str(KIT_ROOT),
                    language="pl",
                    clients_arg="codex",
                    workspace_repl=clean_ws.as_posix(),
                )

                self.assertIsNone(warning)
                self.assertFalse((clean_ws / ".codex" / "config.toml.bak").exists())
                merged = (clean_ws / ".codex" / "config.toml").read_text(encoding="utf-8")
                self.assertIn(foreign_cfg, merged)
                self.assertIn("[mcp_servers.kit-ai-mcp]", merged)


class TestGitignoreSectionUnit(unittest.TestCase):
    """Renderowanie i idempotentne scalanie sekcji ``.gitignore`` w Pythonie."""

    def test_gitignore_section_is_added_and_idempotent(self) -> None:
        """Sekcja kita wchodzi raz, nie duplikuje się i zachowuje reguły projektu."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / ".gitignore"
            dest.write_text("node_modules/\n.env\n", encoding="utf-8")

            def sync() -> str | None:
                return sync_gitignore_file(
                    dest=dest,
                    template_path=KIT_ROOT / "templates" / "gitignore-kit.txt",
                    shared_skills_dir=KIT_ROOT / "templates" / "shared" / "skills",
                    shared_agents_dir=KIT_ROOT / "templates" / "shared" / "agents",
                    cursor_skills_dir=KIT_ROOT / "templates" / "cursor" / "skills",
                    machine_files=_MACHINE_FILES,
                )

            first_action = sync()
            first = dest.read_text(encoding="utf-8")
            second_action = sync()
            second = dest.read_text(encoding="utf-8")

            self.assertEqual(first_action, "dodano")
            self.assertIsNone(second_action)
            self.assertEqual(first, second)
            self.assertEqual(second.count("# >>> instruction-kit >>>"), 1)
            self.assertIn("node_modules/", second)
            self.assertIn(".claude/settings.local.json", second)
            self.assertIn(".agents/skills/", second)

    def test_gitignore_allows_kit_skills_by_name_only(self) -> None:
        """Whitelist wymienia skille kita po nazwie — nie używa ``!.claude/skills/**``."""
        rendered = render_gitignore_section(
            template_text=KIT_SKILLS_TEMPLATE,
            shared_skills_dir=KIT_ROOT / "templates" / "shared" / "skills",
            shared_agents_dir=KIT_ROOT / "templates" / "shared" / "agents",
            cursor_skills_dir=KIT_ROOT / "templates" / "cursor" / "skills",
            machine_files=_MACHINE_FILES,
        )

        self.assertIn(".claude/skills/*", rendered)
        self.assertNotIn("!.claude/skills/**", rendered)
        self.assertIn("@KIT_SKILLS_CLAUDE@", KIT_SKILLS_TEMPLATE)
        self.assertNotIn("@KIT_SKILLS_CLAUDE@", rendered)

        for name in sorted(
            p.name for p in (KIT_ROOT / "templates" / "shared" / "skills").iterdir() if p.is_dir()
        ):
            with self.subTest(skill=name):
                self.assertIn(f"!.claude/skills/{name}/", rendered)

    def test_gitignore_appends_when_end_marker_missing(self) -> None:
        """Brak markera końcowego nie kasuje reguł użytkownika po markerze początkowym."""
        existing = "# >>> instruction-kit >>>\ncustom_rule/\n"
        updated, action = merge_gitignore_text(existing, "# >>> instruction-kit >>>\nkit\n# <<< instruction-kit <<<\n")
        self.assertEqual(action, "dodano")
        self.assertIn("custom_rule/", updated)


class TestAgentSelectionUnit(unittest.TestCase):
    """Dobór tierów z Profilu i filtrowanie agentów w pamięci."""

    def test_detect_profile_tiers(self) -> None:
        """Tiery backend/client działają dla aktualnych i legacy pól Profilu."""
        self.assertEqual(detect_profile_tiers(""), [])
        self.assertEqual(detect_profile_tiers("backend: none\nweb: none\nmobile: none\n"), [])
        self.assertEqual(detect_profile_tiers("backend: fastapi\nweb: none\n"), ["backend"])
        self.assertEqual(detect_profile_tiers("backend: none\nweb: react\n"), ["client"])
        self.assertEqual(detect_profile_tiers("backend: none\nmobile: expo\n"), ["client"])
        self.assertEqual(detect_profile_tiers("backend: django\nweb: react\n"), ["backend", "client"])
        self.assertEqual(
            detect_profile_tiers("stacks:\n  django-drf: true\n  expo-router: false\n"),
            ["backend"],
        )

    def test_stage_shared_agents_filters_by_tier_and_headless(self) -> None:
        """Staging filtruje po ``tier:``, ``headless``, usuwa metadane i ocenia ``<!-- clients: -->``."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "staged"
            skipped = stage_shared_agents(
                src_dir=KIT_ROOT / "templates" / "shared" / "agents",
                dest_dir=dest,
                tiers={"backend"},
                clients={"opencode"},
                headless_enabled=False,
            )
            self.assertIn("headless", skipped)
            self.assertIn("review-frontend", skipped)
            self.assertNotIn("review-backend", skipped)
            self.assertTrue((dest / "review-backend.md").is_file())
            self.assertFalse((dest / "review-frontend.md").exists())
            backend_text = (dest / "review-backend.md").read_text(encoding="utf-8")
            self.assertNotIn("\ntier:", backend_text)
            self.assertNotIn("\nmodel-tier:", backend_text)
            self.assertNotIn("\nclassification:", backend_text)
            night_run_text = (dest / "night-run.md").read_text(encoding="utf-8")
            self.assertNotIn("<!-- clients:", night_run_text)

    def test_stage_shared_agents_rejects_unclosed_client_block(self) -> None:
        """Niedomknięty znacznik ``<!-- clients: -->`` podnosi ``ValueError``."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            src.mkdir()
            (src / "broken.md").write_text(
                "---\nname: broken\n---\n<!-- clients: claude -->\nbody\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                stage_shared_agents(
                    src_dir=src,
                    dest_dir=dest,
                    tiers=set(),
                    clients={"claude"},
                    headless_enabled=False,
                )


class TestOpencodeDefaultModelUnit(unittest.TestCase):
    """Dziedziczenie ``model`` z globalnego configu OpenCode w Pythonie (#167)."""

    def _new_project_config(self, workspace: Path) -> Path:
        dest = workspace / "opencode.json"
        sync_mcp_file(
            KIT_ROOT / "templates/opencode/opencode.json",
            dest,
            from_src=str(KIT_ROOT),
            language="pl",
            clients_arg="opencode",
            workspace_repl=workspace.as_posix(),
        )
        return dest

    def _global(self, home: Path, name: str, text: str) -> Path:
        cfg_dir = home / "opencode"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        path = cfg_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_missing_project_model_is_copied_from_global(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark", "theme": "x"}')

            res = inherit_opencode_model(dest, config_dir=home / "opencode")
            self.assertIsNotNone(res)
            data = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "opencode/muse-spark")
            self.assertNotIn("theme", data)

    def test_project_model_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark"}')
            data = json.loads(dest.read_text(encoding="utf-8"))
            data["model"] = "anthropic/claude-x"
            dest.write_text(json.dumps(data), encoding="utf-8")

            self.assertIsNone(inherit_opencode_model(dest, config_dir=home / "opencode"))
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["model"], "anthropic/claude-x")

    def test_no_global_config_or_model_leaves_field_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self.assertIsNone(inherit_opencode_model(dest, config_dir=home / "opencode"))
            self.assertNotIn("model", json.loads(dest.read_text(encoding="utf-8")))
            self._global(home, "opencode.json", '{"theme": "x"}')
            self.assertIsNone(inherit_opencode_model(dest, config_dir=home / "opencode"))
            self._global(home, "opencode.json", "{ zepsuty")
            self.assertIsNone(inherit_opencode_model(dest, config_dir=home / "opencode"))

    def test_inherited_model_keeps_kit_layout_of_opencode_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark"}')

            inherit_opencode_model(dest, config_dir=home / "opencode")
            self.assertIn('"run", "--project"', dest.read_text(encoding="utf-8"))

    def test_last_global_file_wins_like_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(home, "config.json", '{"model": "a/legacy"}')
            self._global(home, "opencode.json", '{"model": "a/json"}')
            self._global(home, "opencode.jsonc", '{"model": "a/jsonc"}')

            inherit_opencode_model(dest, config_dir=home / "opencode")
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["model"], "a/jsonc")

    def test_global_config_with_bom_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(home, "opencode.json", '\ufeff{"model": "a/bom"}')

            inherit_opencode_model(dest, config_dir=home / "opencode")
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["model"], "a/bom")

    def test_jsonc_global_config_with_comments_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            dest = self._new_project_config(workspace)
            self._global(
                home,
                "opencode.jsonc",
                '{\n  // domyślny\n  "$schema": "https://opencode.ai/config.json",\n'
                '  /* darmowy */ "model": "opencode/muse-spark",\n}\n',
            )
            parsed = load_jsonc((home / "opencode" / "opencode.jsonc").read_text(encoding="utf-8"))
            self.assertEqual(parsed["model"], "opencode/muse-spark")
            inherit_opencode_model(dest, config_dir=home / "opencode")
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["model"], "opencode/muse-spark")


class TestTestNamePolicy(unittest.TestCase):
    """Nazwy testów zawsze po angielsku, także przy `language: pl` (#163)."""

    def _language(self, lang: str) -> str:
        saved = (server._kit_root, server._workspace_root, server._language_override)
        with tempfile.TemporaryDirectory() as tmp:
            server._kit_root, server._workspace_root, server._language_override = KIT_ROOT, Path(tmp), lang
            try:
                return server.get_language()
            finally:
                server._kit_root, server._workspace_root, server._language_override = saved

    def test_get_language_names_tests_and_tdd_override(self) -> None:
        """Polityka identyfikatorów wymienia nazwy testów, a `pl` wskazuje override `/tdd`."""
        out = self._language("pl")
        self.assertIn("test function and class names", out)
        self.assertIn("/tdd", out)
        en = self._language("en")
        self.assertIn("test function and class names", en)
        self.assertNotIn("/tdd", en)


if __name__ == "__main__":
    unittest.main()
