import re
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"
FILES = ["git-start.md", "git-check.md", "git-end.md", "night-run.md"]


def base_block(text):
    start = text.index("Baza (ta sama reguła")
    return text[start : text.index("```\n", text.index("```bash", start) + 7)]


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _init_repo(repo: Path, *, dev: str | None = "same", default: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", default)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "branch", "-M", default)
    _git(repo, "update-ref", f"refs/remotes/origin/{default}", default)
    if dev == "same":
        _git(repo, "branch", "dev", default)
        _git(repo, "update-ref", "refs/remotes/origin/dev", "dev")
    elif dev == "ahead":
        _git(repo, "branch", "dev", default)
        _git(repo, "checkout", "-q", "dev")
        (repo / "dev.txt").write_text("dev\n", encoding="utf-8")
        _git(repo, "add", "dev.txt")
        _git(repo, "commit", "-q", "-m", "dev ahead")
        _git(repo, "update-ref", "refs/remotes/origin/dev", "dev")
        _git(repo, "checkout", "-q", default)
    elif dev == "behind":
        _git(repo, "branch", "dev", default)
        _git(repo, "update-ref", "refs/remotes/origin/dev", "dev")
        (repo / "main.txt").write_text("main ahead\n", encoding="utf-8")
        _git(repo, "add", "main.txt")
        _git(repo, "commit", "-q", "-m", "main ahead")
        _git(repo, "update-ref", f"refs/remotes/origin/{default}", default)


def _eval_bash_base(repo: Path, default: str) -> str:
    """Weryfikacja logiki bash z git-start.md."""
    script = (
        f'DEFAULT="{default}"\n'
        "BASE=$(sed -n 's/^base:[[:space:]]*\\([^[:space:]]*\\).*/\\1/p' .ai/project.md 2>/dev/null | head -1)\n"
        'if [ -z "$BASE" ]; then\n'
        '  BASE=$DEFAULT\n'
        '  if git rev-parse -q --verify origin/dev >/dev/null \\\n'
        '     && ! { git merge-base --is-ancestor origin/dev "origin/$DEFAULT" \\\n'
        '            && [ "$(git rev-parse origin/dev)" != "$(git rev-parse "origin/$DEFAULT")" ]; }; then\n'
        '    BASE=dev\n'
        '  fi\n'
        'fi\n'
        'printf "%s" "$BASE"'
    )
    proc = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


class BaseBranchRuleTest(unittest.TestCase):
    def test_old_dev_if_exists_rule_is_gone(self):
        for name in FILES:
            text = (AGENTS / name).read_text(encoding="utf-8")
            for old in ("`dev` jeśli istnieje", "`dev` jeśli na remote", "`dev` jeśli `origin/dev`"):
                self.assertNotIn(old, text, name)

    def test_same_block_everywhere(self):
        blocks = {n: base_block((AGENTS / n).read_text(encoding="utf-8")) for n in FILES}
        first = blocks[FILES[0]]
        for name, block in blocks.items():
            self.assertEqual(block, first, name)
        for needle in ("^base:", "merge-base --is-ancestor origin/dev", "baseRefName"):
            self.assertIn(needle, first)

    def test_base_fallback_rule_exported_and_matches_hook(self):
        from guides.resolver import BASE_FALLBACK_RULE_PL

        hook_path = KIT_ROOT / "templates" / "claude" / "language-reminder.mjs"
        hook_text = hook_path.read_text(encoding="utf-8")
        self.assertIn("`dev`, jeśli origin/dev nie jest w tyle za default; inaczej default", hook_text)
        self.assertIn("dev", BASE_FALLBACK_RULE_PL)

    def test_base_regex_parity_between_python_and_hook(self):
        from guides import resolver

        hook_path = KIT_ROOT / "templates" / "claude" / "language-reminder.mjs"
        hook_text = hook_path.read_text(encoding="utf-8")
        self.assertIn("match(overlay, /^base:[ \\t]*(\\S+)[ \\t]*$/m", hook_text)
        self.assertEqual(resolver._BASE_LINE.pattern, r"(?m)^base:[ \t]*(\S+)[ \t]*$")

    def test_night_ctx_base_branch_parity_with_git_start_bash(self):
        from guides.night_ctx import base_branch

        scenarios = [
            ("overlay_forced", "custom-base", "same", "custom-base", "base: z project.md"),
            ("no_overlay_dev_same", None, "same", "dev", "dev aktywny"),
            ("no_overlay_dev_ahead", None, "ahead", "dev", "dev aktywny"),
            ("no_overlay_dev_behind", None, "behind", "main", "dev w tyle"),
            ("no_overlay_no_dev", None, None, "main", "brak dev"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            ai_dir = repo / ".ai"

            for name, overlay_base_val, dev_mode, expected_branch, expected_reason in scenarios:
                with self.subTest(name):
                    if repo.exists():
                        import shutil
                        shutil.rmtree(repo)
                    _init_repo(repo, dev=dev_mode, default="main")
                    ai_dir.mkdir(parents=True, exist_ok=True)
                    overlay_text = f"base: {overlay_base_val}\n" if overlay_base_val else "# Overlay\n"
                    (ai_dir / "project.md").write_text(overlay_text, encoding="utf-8")

                    branch, reason = base_branch(repo, overlay_text)
                    self.assertEqual(branch, expected_branch)
                    self.assertEqual(reason, expected_reason)

                    bash_branch = _eval_bash_base(repo, "main")
                    self.assertEqual(branch, bash_branch, f"Parzystość night_ctx i bash /git-start dla {name}")


if __name__ == "__main__":
    unittest.main()
