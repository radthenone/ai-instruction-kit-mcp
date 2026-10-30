"""Night-run na hoście VPS i z server-guardem (#195): treść szablonu i bundle vps/local."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guides.resolver import resolve_profile

KIT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = KIT_ROOT / "templates" / "shared" / "agents" / "night-run.md"
COPIES = (
    ".claude/agents/night-run.md",
    ".claude/commands/night-run.md",
    ".codex/skills/night-run/SKILL.md",
    ".github/prompts/night-run.prompt.md",
    ".opencode/command/night-run.md",
)
VPS_RULES = ("brak CI = brak merge", "krok odrzucony przez guard = tylko CI")


def _bundles_text(host: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        (ws / ".ai").mkdir(parents=True)
        path = ws / ".ai" / "project.profile.yaml"
        path.write_text("name: t\nbackend: none\nweb: none\nmobile: none\n", encoding="utf-8")
        resolved = resolve_profile(path, kit_root=KIT_ROOT, workspace_root=ws, host_profile=host)
    return "\n".join(b.content for b in resolved.bundles.values())


class TestNightRunTemplate(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def test_no_tmp_paths(self) -> None:
        self.assertNotIn("/tmp/", self.text)
        self.assertIn("~/.cache/night-run-", self.text)

    def test_commit_after_each_green_step(self) -> None:
        self.assertIn("Commit po każdym zielonym kroku", self.text)

    def test_guard_deny_is_rule_not_failure(self) -> None:
        self.assertIn("to reguła, nie awaria", self.text)
        self.assertIn("nie obchodzisz jej", self.text)

    def test_report_has_host_line(self) -> None:
        self.assertIn("Host: <vps | local>", self.text)

    def test_ctx_header_decides_host(self) -> None:
        self.assertIn("`Host:` pochodzi z `kit-ai host`", self.text)

    def test_ctx_header_comes_from_generator(self) -> None:
        self.assertIn("kit-ai night-ctx", self.text)
        self.assertNotIn("infra:vps-lightweight` → `vps", self.text)
        self.assertNotIn("bundle z MCP `get_bundle`", self.text)

    def test_watchdog_halt_on_header_mismatch(self) -> None:
        self.assertIn("halt", self.text)
        self.assertIn("znacznik", self.text)

    def test_vps_without_ci_skips_merge(self) -> None:
        self.assertIn("kroki 7–8 pomijasz", self.text)

    def test_e2e_marked_not_run_on_vps(self) -> None:
        self.assertIn("nieuruchomione lokalnie (VPS), weryfikuje CI", self.text)

    def test_no_sync_only_in_vps_branch(self) -> None:
        outside = self.text.split("## VPS (tylko", 1)[0]
        lines = [ln for ln in outside.splitlines() if "zawsze z `--no-sync`" in ln]
        self.assertNotEqual(lines, [])
        for line in lines:
            self.assertIn("Host: vps", line)

    def test_ci_retry_limit_is_three(self) -> None:
        """Pętla poprawek po czerwonym CI w night-run ma limit 3 prób (zamiast 2)."""
        normalized = " ".join(self.text.split())
        self.assertIn("ponawiasz `/git-end` (maks. 3 próby)", normalized)
        self.assertIn("CI czerwone po 3 próbach naprawy", normalized)
        self.assertNotIn("ponawiasz `/git-end` (maks. 2 próby)", normalized)
        self.assertNotIn("CI czerwone po 2 próbach naprawy", normalized)

    def test_reload_refreshed_client_copies(self) -> None:
        # Parytet bajt w bajt sprawdza test_generated_artifacts; tu tylko, że kopie są po #195.
        for rel in COPIES:
            with self.subTest(copy=rel):
                copy = (KIT_ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("/tmp/", copy)
                self.assertIn("~/.cache/night-run-", copy)


class TestNightRunBundles(unittest.TestCase):
    def test_vps_bundle_has_vps_rules(self) -> None:
        text = _bundles_text("vps")
        for rule in VPS_RULES:
            self.assertIn(rule, text)

    def test_local_bundle_has_no_vps_rules(self) -> None:
        text = _bundles_text("local")
        for rule in VPS_RULES:
            self.assertNotIn(rule, text)


if __name__ == "__main__":
    unittest.main()
