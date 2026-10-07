"""Testy bootstrap_workspace — instalacja plików kita z poziomu serwera MCP.

Suita odpala **prawdziwy** ``scripts/bootstrap-project.sh`` (na kopii w katalogu
tymczasowym), bo cała wartość tego narzędzia polega na tym, że skrypt zostaje
jedynym źródłem prawdy o rozkładzie plików. Bez basha: skip lokalnie, błąd na CI —
ta sama polityka co w `test_shell_suites`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, resolve_bash

from guides import server
from guides.bootstrap import BootstrapError, find_bash, plan_bootstrap, run_bootstrap

KIT_ROOT = Path(__file__).resolve().parents[1]
KIT_SKILLS_TEMPLATE = (KIT_ROOT / "templates" / "gitignore-kit.txt").read_text(encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    """Zawartość wszystkich plików pod ``root`` — do porównania „nic nie ruszono”."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class _BootstrapTestCase(unittest.TestCase):
    """Wspólny strażnik dostępności basha."""

    def setUp(self) -> None:
        if not resolve_bash():
            if is_ci():
                self.fail("brak bash w środowisku CI — bootstrap musi się wykonać")
            self.skipTest("brak bash / Git for Windows w PATH")


class TestFindBash(_BootstrapTestCase):
    def test_find_bash_points_at_existing_interpreter(self) -> None:
        """Na Windows to ma być konkretny bash.exe, nie samo słowo `bash`."""
        bash = find_bash()
        self.assertTrue(bash)
        if bash != "bash":
            self.assertTrue(Path(bash).is_file())


class TestDryRun(_BootstrapTestCase):
    def test_dry_run_does_not_touch_workspace(self) -> None:
        """Plan powstaje z przebiegu w sandboxie — repo aplikacji zostaje nietknięte."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            (workspace / "README.md").write_text("app\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)

            self.assertIn(".claude/hooks/git-guard.mjs", plan.created)
            self.assertIn(".claude/settings.json", plan.created)
            self.assertIn(".ai/.kit-bootstrap.json", plan.created)
            self.assertEqual(plan.modified, [])
            self.assertEqual(plan.deleted, [])

    def test_dry_run_reports_deletions_from_client_pruning(self) -> None:
        """Sprzątanie klientów spoza --clients też widać w planie, zanim skasuje."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".cursor" / "hooks").mkdir(parents=True)
            (workspace / ".cursor" / "mcp.json").write_text("{}\n", encoding="utf-8")

            before = _snapshot(workspace)
            plan = plan_bootstrap(
                workspace_root=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
            )
            self.assertEqual(_snapshot(workspace), before)
            self.assertIn(".cursor/mcp.json", plan.deleted)


class TestRealRun(_BootstrapTestCase):
    def test_run_installs_hooks_settings_and_stamp(self) -> None:
        """Kryterium ukończenia z issue #31 — hooki, PreToolUse i stamp na dysku."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertTrue((workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())
            self.assertTrue((workspace / ".ai" / ".kit-bootstrap.json").is_file())
            settings = (workspace / ".claude" / "settings.json").read_text(encoding="utf-8")
            self.assertIn("PreToolUse", settings)

    def test_local_source_uses_uv_run_not_uvx(self) -> None:
        """Lokalny klon: `uv run --project` czyta kod i moduły z dysku.

        `uvx --from <katalog>` cache'uje koło pod wersję pakietu, więc edycja modułu
        (albo kodu serwera) nie dociera do klienta, dopóki wersja nie wzrośnie.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(
                target=workspace,
                kit_root=KIT_ROOT,
                clients="claude,codex,vscode,opencode",
                from_src=str(KIT_ROOT),
            )

            for rel in (
                ".mcp.json",
                ".codex/config.toml",
                ".vscode/mcp.json",
                "opencode.json",
            ):
                with self.subTest(config=rel):
                    text = (workspace / rel).read_text(encoding="utf-8")
                    self.assertIn('"uv"', text)
                    self.assertNotIn('"uvx"', text)
                    self.assertIn('"run", "--project"', text)
                    self.assertNotIn("--codegen", text)
                    self.assertNotIn('"--from"', text)
                    self.assertIn("--kit-root", text)

    def test_remote_source_keeps_uvx(self) -> None:
        """Przy źródle zdalnym klonu nie ma — `uvx` jest poprawny, a `--kit-root` wskazywałby w pustkę."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(
                target=workspace,
                kit_root=KIT_ROOT,
                clients="claude",
                from_src="git+https://example.com/kit.git",
            )

            text = (workspace / ".mcp.json").read_text(encoding="utf-8")
            self.assertIn('"uvx"', text)
            self.assertIn('"--from"', text)
            self.assertNotIn("--kit-root", text)

    def test_gitattributes_installed_only_when_missing(self) -> None:
        """Brak pliku → szablon z LF; własny plik projektu zostaje nietknięty."""
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "fresh"
            fresh.mkdir()
            run_bootstrap(target=fresh, kit_root=KIT_ROOT, clients="claude")
            self.assertIn("* text=auto eol=lf", (fresh / ".gitattributes").read_text(encoding="utf-8"))

            own = Path(tmp) / "own"
            own.mkdir()
            (own / ".gitattributes").write_bytes(b"*.png binary\n")
            run_bootstrap(target=own, kit_root=KIT_ROOT, clients="claude")
            self.assertEqual((own / ".gitattributes").read_bytes(), b"*.png binary\n")

    def test_gitignore_section_is_added_and_idempotent(self) -> None:
        """Sekcja kita wchodzi raz, nie duplikuje się i nie depcze reguł projektu."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            gitignore = workspace / ".gitignore"
            gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            first = gitignore.read_text(encoding="utf-8")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            second = gitignore.read_text(encoding="utf-8")

            self.assertEqual(first, second, "druga instalacja zmieniła .gitignore")
            self.assertEqual(second.count("# >>> instruction-kit >>>"), 1)
            self.assertIn("node_modules/", second)
            self.assertIn(".claude/settings.local.json", second)
            self.assertIn(".agents/skills/", second)

    def test_gitignore_allows_kit_skills_by_name_only(self) -> None:
        """Katalog skilli miesza pliki kita z dowiązaniami do ignorowanego `.agents/skills/`.

        Whitelist musi wymieniać skille kita po nazwie — `!.claude/skills/**` wciągnąłby
        też te dowiązania, a w repo byłyby linkami donikąd (ze ścieżką absolutną maszyny).
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            gitignore = (workspace / ".gitignore").read_text(encoding="utf-8")

            self.assertIn(".claude/skills/*", gitignore)
            self.assertNotIn("!.claude/skills/**", gitignore)
            self.assertIn("@KIT_SKILLS_CLAUDE@", KIT_SKILLS_TEMPLATE)
            self.assertNotIn("@KIT_SKILLS_CLAUDE@", gitignore)

            for name in sorted(
                p.name for p in (KIT_ROOT / "templates" / "shared" / "skills").iterdir()
                if p.is_dir()
            ):
                with self.subTest(skill=name):
                    self.assertIn(f"!.claude/skills/{name}/", gitignore)

    # Konfigi MCP, które bootstrap renderuje ze ścieżką maszyny (`uv run --project`,
    # `--kit-root`, absolutny `--workspace`) — po jednym na klienta.
    MCP_CONFIGS = (
        ".mcp.json",
        ".cursor/mcp.json",
        ".vscode/mcp.json",
        ".codex/config.toml",
        ".kiro/settings/mcp.json",
        ".kilocode/mcp.json",
        ".agents/mcp_config.json",
        "opencode.json",
    )

    @staticmethod
    def _git(cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()

    def _git_repo(self, workspace: Path) -> None:
        workspace.mkdir()
        self._git(workspace, "init", "-q")
        self._git(workspace, "config", "user.email", "test@test.local")
        self._git(workspace, "config", "user.name", "test")

    def test_gitignore_keeps_machine_specific_files_out_of_git(self) -> None:
        """Konfigi MCP i stamp są per maszyna — bootstrap renderuje w nich ścieżkę klona.

        Zacommitowane z jednej maszyny psują serwer MCP na każdej innej (issue #69:
        `uv run --directory M:/…` na Linuksie → CONNECTION_CLOSED). Reszta konfiguracji
        AI (hooki, agenci, skille, settings.json) ma zostać wersjonowana jak dotąd.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="all")

            for rel in (*self.MCP_CONFIGS, ".ai/.kit-bootstrap.json"):
                with self.subTest(ignored=rel):
                    self.assertTrue(
                        (workspace / rel).is_file(), f"{rel} nie został wygenerowany"
                    )
                    self.assertEqual(
                        self._git(workspace, "check-ignore", rel), rel, f"{rel} nie jest ignorowany"
                    )

            for rel in (
                ".ai/project.md",
                ".claude/settings.json",
                ".claude/hooks/git-guard.mjs",
                ".codex/skills/skill-authoring/SKILL.md",
                ".cursor/hooks.json",
                ".github/copilot-instructions.md",
            ):
                with self.subTest(versioned=rel):
                    self.assertEqual(
                        self._git(workspace, "check-ignore", rel), "", f"{rel} jest ignorowany"
                    )

    def test_bootstrap_warns_about_tracked_mcp_configs(self) -> None:
        """Wpis w .gitignore nie odśledza pliku, który już siedzi w indeksie.

        Repo zbootstrapowane przed #69 mają konfigi MCP zacommitowane — bootstrap ma to
        wykryć i podać gotową komendę, ale nie ruszać indeksu gita za użytkownika.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)
            (workspace / ".vscode").mkdir()
            (workspace / ".mcp.json").write_text("{}\n", encoding="utf-8")
            (workspace / ".vscode" / "mcp.json").write_text("{}\n", encoding="utf-8")
            self._git(workspace, "add", ".mcp.json", ".vscode/mcp.json")
            self._git(workspace, "commit", "-q", "-m", "old bootstrap")

            out = run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,vscode")

            self.assertIn(" rm --cached .mcp.json .vscode/mcp.json", out)
            self.assertEqual(
                self._git(workspace, "ls-files", ".mcp.json"), ".mcp.json",
                "bootstrap sam odśledził plik — to decyzja użytkownika",
            )

    def test_bootstrap_is_quiet_when_nothing_machine_specific_is_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._git_repo(workspace)

            out = run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")

            self.assertNotIn("git rm --cached", out)

    def test_missing_script_is_an_error(self) -> None:
        """Kit bez skryptu bootstrapu — jasny błąd zamiast cichego nic."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_kit = Path(tmp) / "kit"
            fake_kit.mkdir()
            with self.assertRaises(BootstrapError) as ctx:
                run_bootstrap(target=Path(tmp) / "app", kit_root=fake_kit)
            self.assertIn("bootstrap-project.sh", str(ctx.exception))


BACKEND_AGENTS = {"review-backend", "teacher-backend", "subagent-backend"}
CLIENT_AGENTS = {"review-frontend", "teacher-frontend", "subagent-frontend", "review-ui"}


class TestUserConfigMerge(_BootstrapTestCase):
    """Reload podmienia tylko wpis kita w configach klientów, nie cały plik (#160)."""

    def _run(self, workspace: Path, clients: str) -> str:
        return run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)

    def test_json_configs_keep_user_servers_and_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._run(workspace, "claude,vscode,opencode")

            mine = {"command": "my-server"}
            edits = {
                ".mcp.json": ("mcpServers", {}),
                ".vscode/mcp.json": ("servers", {"inputs": []}),
                "opencode.json": ("mcp", {"model": "anthropic/claude-x"}),
            }
            for rel, (key, extra) in edits.items():
                path = workspace / rel
                data = json.loads(path.read_text(encoding="utf-8"))
                data[key]["mine"] = mine
                data[key]["project-guides"] = {"command": "stale"}
                data.update(extra)
                path.write_text(json.dumps(data), encoding="utf-8")

            self._run(workspace, "claude,vscode,opencode")

            for rel, (key, extra) in edits.items():
                with self.subTest(config=rel):
                    data = json.loads((workspace / rel).read_text(encoding="utf-8"))
                    self.assertEqual(data[key]["mine"], mine)
                    self.assertNotEqual(data[key]["project-guides"], {"command": "stale"})
                    for k, v in extra.items():
                        self.assertEqual(data[k], v)
                    self.assertFalse((workspace / (rel + ".bak")).exists())

    def test_codex_toml_keeps_user_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._run(workspace, "codex")
            path = workspace / ".codex" / "config.toml"
            text = path.read_text(encoding="utf-8").replace('"guides-mcp"', '"stale"')
            mine = '# mój serwer\n[mcp_servers.mine]\ncommand = "x"\n'
            path.write_text('model = "o3"\n\n' + text + "\n" + mine, encoding="utf-8")

            self._run(workspace, "codex")

            text = path.read_text(encoding="utf-8")
            self.assertIn('model = "o3"', text)
            self.assertIn(mine, text)
            self.assertIn('"guides-mcp"', text)
            self.assertNotIn('"stale"', text)
            self.assertEqual(text.count("[mcp_servers.project-guides]"), 1)

    def test_unchanged_config_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._run(workspace, "claude")
            path = workspace / ".mcp.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["mcpServers"]["mine"] = {"command": "x"}
            text = json.dumps(data, indent=4)
            path.write_text(text, encoding="utf-8")

            self._run(workspace, "claude")

            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_unparseable_config_goes_to_bak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            original = '{\n  // komentarz JSONC\n  "mcp": {}\n}\n'
            (workspace / "opencode.json").write_text(original, encoding="utf-8")
            (workspace / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

            out = self._run(workspace, "opencode")

            self.assertEqual((workspace / "opencode.json.bak").read_text(encoding="utf-8"), original)
            self.assertIn("project-guides", json.loads((workspace / "opencode.json").read_text(encoding="utf-8"))["mcp"])
            self.assertIn("opencode.json.bak", out)
            # Backup ma tę samą treść co config, łącznie z tokenami — nie może wejść do gita.
            self.assertIn("/opencode.json.bak\n", (workspace / ".gitignore").read_text(encoding="utf-8"))


class TestTierAgents(_BootstrapTestCase):
    """Agenci Stacku tylko dla wybranych Tierów; treść bez Stacka na sztywno."""

    def _bootstrap(self, workspace: Path, backend: str, web: str, mobile: str) -> set[str]:
        (workspace / ".ai").mkdir(parents=True, exist_ok=True)
        (workspace / ".ai" / "project.profile.yaml").write_text(
            f"name: t\nbackend: {backend}\nweb: {web}\nmobile: {mobile}\n", encoding="utf-8"
        )
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex,opencode")
        return {p.stem for p in (workspace / ".claude" / "agents").glob("*.md")}

    def test_agents_follow_tiers(self) -> None:
        cases = {
            ("none", "none", "none"): set(),
            ("fastapi", "none", "none"): BACKEND_AGENTS,
            ("none", "react", "none"): CLIENT_AGENTS,
            ("none", "none", "expo"): CLIENT_AGENTS,
            ("django", "react", "none"): BACKEND_AGENTS | CLIENT_AGENTS,
        }
        for tiers, expected in cases.items():
            with self.subTest(tiers=tiers), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp) / "app"
                installed = self._bootstrap(workspace, *tiers)
                self.assertEqual(installed & (BACKEND_AGENTS | CLIENT_AGENTS), expected)
                self.assertIn("review-architecture", installed)
                self.assertIn("teacher-architecture", installed)
                codex = {p.name for p in (workspace / ".codex" / "skills").iterdir()}
                self.assertEqual(codex & (BACKEND_AGENTS | CLIENT_AGENTS), expected)
                bugbot = (workspace / "BUGBOT.md").read_text(encoding="utf-8")
                self.assertEqual("## Backend" in bugbot, "fastapi" in tiers or "django" in tiers)
                self.assertNotIn("<!-- tier:", bugbot)

    def test_tier_set_to_none_removes_its_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self.assertEqual(self._bootstrap(workspace, "none", "none", "none") & BACKEND_AGENTS, set())
            self.assertNotIn("## Backend", (workspace / "BUGBOT.md").read_text(encoding="utf-8"))
            self.assertEqual(self._bootstrap(workspace, "django", "none", "none") & BACKEND_AGENTS, BACKEND_AGENTS)
            # Nietknięty BUGBOT.md podąża za Tierami (install zawsze zaczyna od `none`).
            self.assertIn("## Backend", (workspace / "BUGBOT.md").read_text(encoding="utf-8"))
            self.assertEqual(self._bootstrap(workspace, "none", "none", "none") & BACKEND_AGENTS, set())
            for rel in (".claude/commands/review-backend.md", ".codex/skills/review-backend",
                        ".opencode/command/review-backend.md"):
                self.assertFalse((workspace / rel).exists(), rel)

    def test_installed_descriptions_name_no_stack(self) -> None:
        """Opis agenta nie zakłada Django/Expo — Stack przychodzi z Bundle'a."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            self._bootstrap(workspace, "fastapi", "react", "expo")
            for agent in (workspace / ".claude" / "agents").glob("*.md"):
                text = agent.read_text(encoding="utf-8")
                description = next(l for l in text.splitlines() if l.startswith("description:"))
                with self.subTest(agent=agent.name):
                    self.assertNotRegex(description, "Django|DRF|Expo")
                    self.assertNotIn("\ntier:", text)


class TestServerTool(_BootstrapTestCase):
    """Narzędzie MCP — domyślki, bramka dry-run i odmowy."""

    def setUp(self) -> None:
        super().setUp()
        self._saved = (
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._legacy_config,
        )
        server._kit_root = KIT_ROOT
        server._clients = ["claude"]
        server._legacy_config = False
        self._tmp = tempfile.mkdtemp(prefix="guides-tool-test-")
        self.addCleanup(shutil.rmtree, self._tmp, True)
        self.workspace = Path(self._tmp) / "app"
        self.workspace.mkdir()
        server._workspace_root = self.workspace

    def tearDown(self) -> None:
        (
            server._kit_root,
            server._workspace_root,
            server._clients,
            server._legacy_config,
        ) = self._saved

    def test_default_call_is_dry_run(self) -> None:
        """Bez argumentów narzędzie planuje, nie instaluje."""
        before = _snapshot(self.workspace)
        out = server.bootstrap_workspace()
        self.assertIn("dry run", out)
        self.assertIn(".ai/.kit-bootstrap.json", out)
        self.assertEqual(_snapshot(self.workspace), before)

    def test_explicit_dry_run_false_installs(self) -> None:
        """Zapis wymaga jawnego dry_run=False."""
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("zainstalowano", out)
        self.assertTrue((self.workspace / ".ai" / ".kit-bootstrap.json").is_file())
        self.assertTrue((self.workspace / ".claude" / "hooks" / "git-guard.mjs").is_file())

    def test_report_has_no_empty_sections(self) -> None:
        """Każdy nagłówek `##` w raporcie musi mieć pod sobą wyliczenie."""
        server.bootstrap_workspace(dry_run=False)
        out = server.bootstrap_workspace()

        self.assertIn("Bez zmian:", out)
        self.assertNotIn("## Bez zmian", out)
        lines = out.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("## "):
                continue
            body = [rest for rest in lines[index + 1 :] if rest.strip()]
            self.assertTrue(body and body[0].startswith("- `"), msg=f"pusta sekcja: {line}")

    def test_missing_workspace_errors_instead_of_writing_cwd(self) -> None:
        """Brak --workspace: błąd, a bieżący katalog procesu zostaje nietknięty."""
        server._workspace_root = None
        cwd_sentinel = Path(self._tmp) / "cwd"
        cwd_sentinel.mkdir()
        previous = Path.cwd()
        os.chdir(cwd_sentinel)
        self.addCleanup(os.chdir, previous)

        out = server.bootstrap_workspace(dry_run=False)

        self.assertIn("błąd", out)
        self.assertIn("--workspace", out)
        self.assertEqual(_snapshot(cwd_sentinel), {})

    def test_workspace_equal_to_kit_is_refused(self) -> None:
        """Bootstrap repo kita samym sobą to pomyłka, nie funkcja."""
        server._workspace_root = KIT_ROOT
        out = server.bootstrap_workspace(dry_run=False)
        self.assertIn("błąd", out)
        self.assertIn("ten sam katalog", out)

    def test_invalid_clients_is_reported_not_raised(self) -> None:
        """Zła wartość --clients wraca jako komunikat narzędzia."""
        out = server.bootstrap_workspace(clients="nieistniejacy-klient")
        self.assertIn("błąd", out)


class TestTestNamePolicy(_BootstrapTestCase):
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

    def test_bugbot_blocks_non_english_test_names(self) -> None:
        """Zbootstrapowany BUGBOT.md ma blokującą regułę na nieangielskie nazwy."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            bugbot = (workspace / "BUGBOT.md").read_text(encoding="utf-8")
            rule = bugbot[bugbot.index("Non-English identifier") - 300:]
            self.assertIn("`test_*`", rule)
            self.assertIn("blocking bug", rule)


if __name__ == "__main__":
    unittest.main()
