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
from unittest import mock

from _shell import is_ci, resolve_bash

from guides import server
from guides.bootstrap import BootstrapError, find_bash, plan_bootstrap, run_bootstrap
from guides.bugbot_md import extract_rules

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
        # Globalny config opencode z tej maszyny nie może przeciekać do wyniku (#167).
        config_home = tempfile.TemporaryDirectory()
        self.addCleanup(config_home.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config_home.name})
        patcher.start()
        self.addCleanup(patcher.stop)


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

    def test_dry_run_skips_headless_runs(self) -> None:
        """Logi i worktree runów /headless (#183) nie są kopiowane do sandboxu planu."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run = workspace / ".ai" / "headless-runs" / "r1"
            run.mkdir(parents=True)
            (run / "headless.log").write_text("log\n", encoding="utf-8")

            plan = plan_bootstrap(workspace_root=workspace, kit_root=KIT_ROOT, clients="claude")
            listed = plan.created + plan.modified + plan.deleted + plan.unchanged
            self.assertFalse([rel for rel in listed if "headless-runs" in rel], listed)


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
                ".agents/hooks/git-guard.mjs",
                ".agents/hooks.json",
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


class TestBugbotProjectRules(_BootstrapTestCase):
    """BUGBOT.md odświeża się z szablonu, a blok ``project:rules`` zostaje (#240)."""

    # Render starej wersji szablonu — bez bloku `project:rules`.
    OLD_TEMPLATE = """# Bugbot — reguły projektu

Intro (stara wersja szablonu).

## Ogólne

- stara reguła kita

<!-- tier:backend -->
## Backend

- stara reguła backendu
<!-- /tier:backend -->
"""

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

    def test_block_survives_reload_and_rest_is_refreshed(self) -> None:
        """Blok reguł projektu wraca bajt w bajt, reszta pliku jest z szablonu."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor")
            template = (KIT_ROOT / "templates" / "cursor" / "BUGBOT.md").read_text(
                encoding="utf-8"
            )
            hint = extract_rules(template)
            assert hint is not None
            rules = "\n- Reguła projektu A\n- Reguła projektu B\n"
            for rel in ("BUGBOT.md", ".cursor/BUGBOT.md"):
                path = workspace / rel
                text = path.read_text(encoding="utf-8")
                self.assertIn(hint, text)
                # Zmiana poza blokiem też ma zniknąć przy reloadzie.
                text = text.replace(hint, rules).replace(
                    "- Preferuj minimalny diff", "- moja zmiana kita"
                )
                path.write_text(text, encoding="utf-8", newline="\n")

            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor")

            for rel in ("BUGBOT.md", ".cursor/BUGBOT.md"):
                text = (workspace / rel).read_text(encoding="utf-8")
                self.assertEqual(extract_rules(text), rules, rel)
                self.assertIn("- Preferuj minimalny diff", text, rel)
                self.assertNotIn("moja zmiana kita", text, rel)

    def test_migration_moves_added_rules_into_block(self) -> None:
        """Stary render + 2 dopisane reguły → bieżący szablon z regułami w bloku."""
        with tempfile.TemporaryDirectory() as tmp:
            kit = self._kit_with_history(Path(tmp) / "kit")
            workspace = Path(tmp) / "app"
            run_bootstrap(target=workspace, kit_root=kit, clients="claude,cursor")

            dest = workspace / "BUGBOT.md"
            for path in (dest, workspace / ".cursor" / "BUGBOT.md"):
                old = path.read_text(encoding="utf-8")
                self.assertNotIn("project:rules", old)
                path.write_text(
                    old + "\n- Reguła projektu A\n- Reguła projektu B\n",
                    encoding="utf-8",
                    newline="\n",
                )

            (kit / "templates" / "cursor" / "BUGBOT.md").write_text(
                (KIT_ROOT / "templates" / "cursor" / "BUGBOT.md").read_text(encoding="utf-8"),
                encoding="utf-8",
                newline="\n",
            )
            self._git(kit, "commit", "-q", "-am", "current template")

            out = run_bootstrap(target=workspace, kit_root=kit, clients="claude,cursor")

            for path in (dest, workspace / ".cursor" / "BUGBOT.md"):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(
                    extract_rules(text), "\n- Reguła projektu A\n- Reguła projektu B\n"
                )
                self.assertIn("## Ogólne", text)
                self.assertNotIn("stara reguła kita", text)
            self.assertIn("Reguła projektu A", out)
            self.assertIn("Reguła projektu B", out)
            # Kopia natywnego BugBota też raportuje przeniesione linie (#240).
            self.assertIn("  ~ BUGBOT.md: reguły", out)
            self.assertIn("  ~ .cursor/BUGBOT.md: reguły", out)


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



class TestModelTiers(_BootstrapTestCase):
    """`models:` / `agents:` w Profilu → `model:` u Claude i opencode (#168)."""

    def _install(self, workspace: Path, profile_extra: str = "") -> None:
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")
        if profile_extra:
            profile = workspace / ".ai" / "project.profile.yaml"
            profile.write_text(profile.read_text(encoding="utf-8") + profile_extra, encoding="utf-8")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,opencode")

    def test_without_models_agents_have_no_model_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace)
            profile = (workspace / ".ai" / "project.profile.yaml").read_text(encoding="utf-8")
            self.assertIn("\nagents:\n  light: ", profile)
            for rel in (".claude/agents/git-start.md", ".opencode/command/git-start.md"):
                text = (workspace / rel).read_text(encoding="utf-8")
                self.assertNotIn("model:", text.split("---")[1], rel)
                self.assertNotIn("model-tier", text, rel)

    def test_models_mapping_renders_model_for_claude_and_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(
                workspace,
                "\nmodels:\n  claude:\n    light: haiku\n  opencode:\n    light: anthropic/claude-haiku-5-5\n",
            )
            read = lambda rel: (workspace / rel).read_text(encoding="utf-8")  # noqa: E731
            self.assertIn("\nmodel: haiku\n---", read(".claude/agents/git-start.md"))
            self.assertIn(
                "\nmodel: anthropic/claude-haiku-5-5\n---", read(".opencode/command/git-start.md")
            )
            self.assertNotIn("model:", read(".claude/commands/git-start.md").split("---")[1])
            self.assertNotIn("model:", read(".claude/agents/night-run.md").split("---")[1])

    def test_invalid_agents_block_fails_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            with self.assertRaises(BootstrapError) as ctx:
                self._install(workspace, "\nmodels:\n  claude:\n    turbo: haiku\n")
            self.assertIn("models.claude.turbo", str(ctx.exception))


class TestOpencodeGuards(_BootstrapTestCase):
    """`--clients opencode` kładzie plugin guardów i guardy w `.opencode/` (#166)."""

    def test_opencode_gets_guard_plugin_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
            self.assertTrue((workspace / ".opencode/plugins/kit-guards.js").is_file())
            for guard in ("invoke-hook.js", "git-guard.mjs", "sensitive-files-guard.mjs"):
                with self.subTest(guard=guard):
                    self.assertEqual(
                        (workspace / ".opencode/hooks" / guard).read_bytes(),
                        (KIT_ROOT / "templates/shared/guards" / guard).read_bytes(),
                    )

    def test_dropping_opencode_removes_its_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude")
            self.assertFalse((workspace / ".opencode").exists())


class TestServerGuardInstall(_BootstrapTestCase):
    """Server-guard i jego JSON trafiają do hooków claude, cursor i opencode (#194)."""

    def test_guard_wired_and_config_rendered_for_each_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            (workspace / ".ai").mkdir(parents=True)
            (workspace / ".ai/project.profile.yaml").write_text(
                'server:\n  deny:\n    - "bunx eas-cli"\n', encoding="utf-8"
            )
            (workspace / "Taskfile.yml").write_text(
                "version: '3'\ntasks:\n  up:\n    cmds:\n      - docker compose up -d\n", encoding="utf-8"
            )
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,cursor,opencode")
            for hooks in (".claude/hooks", ".cursor/hooks", ".opencode/hooks"):
                with self.subTest(hooks=hooks):
                    self.assertEqual(
                        (workspace / hooks / "server-guard.mjs").read_bytes(),
                        (KIT_ROOT / "templates/shared/guards/server-guard.mjs").read_bytes(),
                    )
                    config = json.loads((workspace / hooks / "server-guard.json").read_text(encoding="utf-8"))
                    self.assertEqual(config["project_deny"], ["bunx eas-cli"])
                    self.assertTrue(any("task up" in w["chain"] for w in config["wrappers"]))
            settings = json.loads((workspace / ".claude/settings.json").read_text(encoding="utf-8"))
            pre = settings["hooks"]["PreToolUse"]
            bash = next(e for e in pre if e["matcher"] == "Bash")
            self.assertTrue(any("server-guard.mjs" in h["command"] for h in bash["hooks"]))
            self.assertTrue(any("playwright" in e["matcher"] and "server-guard.mjs" in e["hooks"][0]["command"] for e in pre))
            self.assertIn("server-guard.mjs", (workspace / ".cursor/hooks.json").read_text(encoding="utf-8"))
            self.assertIn("server-guard.mjs", (workspace / ".opencode/plugins/kit-guards.js").read_text(encoding="utf-8"))


class TestSensitiveGuardBashWiring(_BootstrapTestCase):
    """Sensitive guard widzi Bash tam, gdzie git-guard już go widzi (#231)."""

    def test_shell_reads_wired_for_each_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="claude,codex,cursor,vscode")

            settings = json.loads((workspace / ".claude/settings.json").read_text(encoding="utf-8"))
            bash = next(e for e in settings["hooks"]["PreToolUse"] if "Bash" in e["matcher"].split("|"))
            self.assertTrue(
                any("sensitive-files-guard.mjs" in h["command"] for h in bash["hooks"]), bash
            )

            codex = json.loads((workspace / ".codex/hooks.json").read_text(encoding="utf-8"))
            bash = next(e for e in codex["hooks"]["PreToolUse"] if "Bash" in e["matcher"].split("|"))
            self.assertTrue(
                any("sensitive-files-guard.mjs" in h["command"] for h in bash["hooks"]), bash
            )

            cursor = json.loads((workspace / ".cursor/hooks.json").read_text(encoding="utf-8"))
            shell_guards = [h["command"] for h in cursor["hooks"]["beforeShellExecution"]]
            self.assertTrue(
                any("sensitive-files-guard.mjs" in c for c in shell_guards), shell_guards
            )

            # VS Code: hooki PreToolUse bez matchera widzą wszystkie narzędzia, także Bash.
            copilot = json.loads(
                (workspace / ".github/hooks/kit-guards.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                any("sensitive-files-guard.mjs" in e["command"] for e in copilot["hooks"]["PreToolUse"]),
                copilot,
            )


class TestOpencodeDefaultModel(_BootstrapTestCase):
    """Projektowy `opencode.json` dziedziczy `model` z globalnego configu (#167)."""

    def _run(self, home: Path, workspace: Path) -> dict:
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home)}):
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients="opencode")
        return json.loads((workspace / "opencode.json").read_text(encoding="utf-8"))

    def _global(self, home: Path, name: str, text: str) -> None:
        (home / "opencode").mkdir(parents=True, exist_ok=True)
        (home / "opencode" / name).write_text(text, encoding="utf-8")

    def test_missing_project_model_is_copied_from_global(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark", "theme": "x"}')
            data = self._run(home, workspace)
            self.assertEqual(data["model"], "opencode/muse-spark")
            self.assertNotIn("theme", data)

    def test_project_model_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark"}')
            self._run(home, workspace)
            path = workspace / "opencode.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["model"] = "anthropic/claude-x"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(self._run(home, workspace)["model"], "anthropic/claude-x")

    def test_no_global_config_or_model_leaves_field_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self.assertNotIn("model", self._run(home, workspace))
            self._global(home, "opencode.json", '{"theme": "x"}')
            self.assertNotIn("model", self._run(home, workspace))
            self._global(home, "opencode.json", "{ zepsuty")
            self.assertNotIn("model", self._run(home, workspace))

    def test_inherited_model_keeps_kit_layout_of_opencode_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(home, "opencode.json", '{"model": "opencode/muse-spark"}')
            self._run(home, workspace)
            text = (workspace / "opencode.json").read_text(encoding="utf-8")
            self.assertIn('"run", "--project"', text)

    def test_last_global_file_wins_like_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(home, "config.json", '{"model": "a/legacy"}')
            self._global(home, "opencode.json", '{"model": "a/json"}')
            self._global(home, "opencode.jsonc", '{"model": "a/jsonc"}')
            self.assertEqual(self._run(home, workspace)["model"], "a/jsonc")

    def test_global_config_with_bom_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(home, "opencode.json", '\ufeff{"model": "a/bom"}')
            self.assertEqual(self._run(home, workspace)["model"], "a/bom")

    def test_jsonc_global_config_with_comments_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, workspace = Path(tmp) / "cfg", Path(tmp) / "app"
            workspace.mkdir()
            self._global(
                home,
                "opencode.jsonc",
                '{\n  // domyślny\n  "$schema": "https://opencode.ai/config.json",\n'
                '  /* darmowy */ "model": "opencode/muse-spark",\n}\n',
            )
            self.assertEqual(self._run(home, workspace)["model"], "opencode/muse-spark")



class TestHeadlessAgent(_BootstrapTestCase):
    """Agent `/headless` i wrapper tylko przy ≥2 klientach z trybem headless (#169)."""

    HOST_FILES = {
        "claude": (".claude/agents/headless.md", ".claude/commands/headless.md"),
        "opencode": (".opencode/command/headless.md",),
        "codex": (".codex/skills/headless/SKILL.md",),
        "cursor": (".cursor/agents/headless.md",),
    }

    def _install(self, workspace: Path, clients: str) -> None:
        run_bootstrap(target=workspace, kit_root=KIT_ROOT, clients=clients)

    def test_installed_for_every_host_with_its_own_host_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode,codex,cursor")
            self.assertEqual(
                (workspace / ".ai/headless.mjs").read_bytes(),
                (KIT_ROOT / "templates/shared/headless/headless.mjs").read_bytes(),
            )
            for host, files in self.HOST_FILES.items():
                for rel in files:
                    with self.subTest(file=rel):
                        text = (workspace / rel).read_text(encoding="utf-8")
                        self.assertIn(f"--host {host} ", text)
                        self.assertNotIn("@KIT_HOST@", text)

    def test_not_installed_with_fewer_than_two_headless_clients(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,codex,cursor")
            self.assertFalse((workspace / ".ai/headless.mjs").exists())
            self.assertFalse((workspace / ".claude/agents/headless.md").exists())
            self.assertFalse((workspace / ".codex/skills/headless").exists())

    def test_removed_when_clients_drop_below_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode,antigravity")
            self.assertTrue((workspace / ".agents/skills/headless/SKILL.md").is_file())
            self._install(workspace, "claude,antigravity")
            self.assertFalse((workspace / ".agents/skills/headless").exists())
            self.assertFalse((workspace / ".ai/headless.mjs").exists())
            self.assertFalse((workspace / ".claude/agents/headless.md").exists())
            self.assertFalse((workspace / ".claude/commands/headless.md").exists())

    def test_light_tier_model_lands_in_claude_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode")
            agent = workspace / ".claude/agents/headless.md"
            self.assertNotIn("model:", agent.read_text(encoding="utf-8").split("---")[1])
            profile = workspace / ".ai/project.profile.yaml"
            profile.write_text(
                profile.read_text(encoding="utf-8") + "\nmodels:\n  claude:\n    light: haiku\n",
                encoding="utf-8",
            )
            self._install(workspace, "claude,opencode")
            self.assertIn("\nmodel: haiku\n---", agent.read_text(encoding="utf-8"))

    def test_remove_deletes_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "app"
            workspace.mkdir()
            self._install(workspace, "claude,opencode")
            run_bootstrap(target=workspace, kit_root=KIT_ROOT, remove=True)
            self.assertFalse((workspace / ".ai/headless.mjs").exists())


if __name__ == "__main__":
    unittest.main()
