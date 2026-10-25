"""Każdy `/review-*` z modułów i AGENTS.md ma agenta kita i render u każdego klienta (#243).

Kontrola jest ta sama, którą ma wykonywać `doctor`: odwołanie w instrukcjach nie może
wskazywać komendy, której kit nie dostarcza. Render sprawdzamy na prawdziwym
bootstrapie (`--clients all`, Tiery backend + web), a nie powtarzając mapę ścieżek
z kodu produkcyjnego — inaczej test powtórzyłby też jego błędy.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _shell import is_ci, posix_path, resolve_bash
from guides.clients import KNOWN_CLIENTS

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = KIT_ROOT / "templates" / "shared" / "agents"

# Ścieżki, pod którymi bootstrap kładzie agenta u klienta (README: „Klienci AI”).
CLIENT_PATHS: dict[str, tuple[str, ...]] = {
    "cursor": (".cursor/agents/{name}.md",),
    "claude": (".claude/agents/{name}.md", ".claude/commands/{name}.md"),
    "codex": (".codex/skills/{name}/SKILL.md",),
    "vscode": (".github/prompts/{name}.prompt.md",),
    "kiro": (".kiro/agents/{name}.md",),
    "kilo": (".kilocode/workflows/{name}.md",),
    "antigravity": (".agents/skills/{name}/SKILL.md",),
    "opencode": (".opencode/command/{name}.md",),
}

# Profil z oboma Tierami: inaczej agenci `tier: backend` / `tier: client` są pomijani.
RENDER_PROFILE = """\
name: review-render
language: pl
clients: all

backend: fastapi
web: react
mobile: none

codegen: none
"""


def referenced_review_agents() -> list[str]:
    """
    Nazwy `/review-*` wymienione w `modules/` i `AGENTS.md`, bez prefiksu `/`.

    Returns:
        list[str]: Posortowane, unikalne nazwy agentów, np. ``["review-security"]``.
    """
    sources = [KIT_ROOT / "AGENTS.md", *sorted((KIT_ROOT / "modules").rglob("*.md"))]
    names = {
        match.removeprefix("/")
        for path in sources
        for match in re.findall(r"/review-[a-z0-9-]+", path.read_text(encoding="utf-8"))
    }
    return sorted(names)


class TestReviewAgentReferences(unittest.TestCase):
    def test_map_covers_every_known_client(self) -> None:
        """Nowy klient w `KNOWN_CLIENTS` nie może umknąć kontroli renderu."""
        self.assertEqual(set(CLIENT_PATHS), set(KNOWN_CLIENTS))

    def test_sources_name_review_agents(self) -> None:
        """Sanity: ekstrakcja nie może przejść na pustej liście."""
        names = referenced_review_agents()
        self.assertIn("review-security", names)
        self.assertIn("review-bugbot", names)

    def test_every_referenced_review_agent_has_template(self) -> None:
        missing = [
            name for name in referenced_review_agents() if not (AGENTS_DIR / f"{name}.md").is_file()
        ]
        self.assertEqual(missing, [], msg=f"komendy bez szablonu agenta: {missing}")


class TestReviewAgentRendering(unittest.TestCase):
    """Bootstrap z `--clients all` renderuje każdego `/review-*` u każdego klienta."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="kit-review-agents-")
        target = Path(cls._tmp) / "generated"
        (target / ".ai").mkdir(parents=True)
        (target / ".ai" / "project.profile.yaml").write_text(RENDER_PROFILE, encoding="utf-8")

        bash = resolve_bash()
        if not bash:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            if is_ci():
                raise AssertionError("brak bash na CI — render agentów musi być sprawdzony")
            raise unittest.SkipTest("brak bash — pomijam render agentów")

        result = subprocess.run(
            [
                bash,
                "--noprofile",
                "--norc",
                posix_path(KIT_ROOT / "scripts" / "bootstrap-project.sh"),
                str(target),
                "--clients",
                "all",
                "--from",
                str(KIT_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise AssertionError(f"bootstrap nie wystartował ({result.returncode}): {result.stderr}")
        cls.generated = target

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_every_review_agent_rendered_for_every_client(self) -> None:
        stale: list[str] = []
        for name in referenced_review_agents():
            for client in KNOWN_CLIENTS:
                for pattern in CLIENT_PATHS[client]:
                    rel = pattern.format(name=name)
                    if not (self.generated / rel).is_file():
                        stale.append(f"{client}: {rel}")
        self.assertEqual(stale, [], msg=f"brak renderu agentów: {stale}")


class TestReviewSecurityContent(unittest.TestCase):
    """`review-security` musi pokrywać obszary z issue i nie edytować plików."""

    def setUp(self) -> None:
        self.path = AGENTS_DIR / "review-security.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_frontmatter_is_readonly_standard_review(self) -> None:
        self.assertTrue(self.text.startswith("---\nname: review-security\n"))
        self.assertIn("readonly: true", self.text)
        self.assertIn("model-tier: standard", self.text)

    def test_uses_mcp_stack_and_coding_standards(self) -> None:
        self.assertIn("get_bundle", self.text)
        self.assertIn("get_overlay", self.text)
        self.assertIn("CODING_STANDARDS.md", self.text)

    def test_report_format(self) -> None:
        self.assertIn("| Severity | Location | Finding | Fix |", self.text)

    def test_security_areas(self) -> None:
        areas = (
            "CSRF",
            "MFA",
            "token",
            "ACL",
            "IDOR",
            "webhook",
            "idempotenc",
            "sekrety",
            "dane osobowe",
            "log",
            "URL",
            "limit",
            "auth",
        )
        for needle in areas:
            with self.subTest(area=needle):
                self.assertIn(needle.lower(), self.text.lower())

    def test_does_not_edit_files(self) -> None:
        self.assertIn("Nie edytujesz", self.text)


if __name__ == "__main__":
    unittest.main()
