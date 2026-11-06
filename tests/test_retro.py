"""``kit-ai retro scan`` — sygnały, normalizacja, maskowanie i fingerprint (#371, część (a) #338).

Fixtury to syntetyczne rekordy JSONL o kształcie transkryptu Claude Code. Żadna prawdziwa
wiadomość z sesji nie trafia do repo.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from guides import cli, retro

KIT_ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
SESSION = "11111111-2222-4333-8444-555555555555"
GUARD_DENY = (
    "PreToolUse:Bash hook error: git-guard: git checkout . / checkout -- <ścieżka> "
    "— kasuje niezacommitowane zmiany; użyj git stash"
)


def _assistant(msg_id: str, *blocks: dict, usage: dict | None = None) -> dict:
    message: dict = {"id": msg_id, "role": "assistant", "content": list(blocks)}
    if usage is not None:
        message["usage"] = usage
    return {"type": "assistant", "sessionId": SESSION, "message": message}


def _tool_use(tool_id: str, name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def _tool_result(tool_id: str, text: str, *, is_error: bool = False) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": is_error}
    return {"type": "user", "sessionId": SESSION, "message": {"role": "user", "content": [block]}}


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    return path


class MaskTests(unittest.TestCase):
    def test_masks_github_token(self) -> None:
        token = "gho_" + "a" * 36
        masked = retro.mask(f"auth with {token} failed")
        self.assertNotIn(token, masked)
        self.assertIn("<secret>", masked)

    def test_masks_key_value_secrets(self) -> None:
        masked = retro.mask("export API_KEY=abc123def456 and password: hunter2")
        self.assertNotIn("abc123def456", masked)
        self.assertNotIn("hunter2", masked)

    def test_masks_bearer_token_and_email(self) -> None:
        masked = retro.mask("Authorization: Bearer abcdefghijklmnop1234 mail krzyzak21@gmail.com")
        self.assertNotIn("abcdefghijklmnop1234", masked)
        self.assertNotIn("krzyzak21@gmail.com", masked)

    def test_replaces_home_directory_with_tilde(self) -> None:
        self.assertEqual(retro.mask("/home/alice/projects/x.py"), "~/projects/x.py")


class NormalizeTests(unittest.TestCase):
    def test_variable_parts_do_not_split_the_group(self) -> None:
        first = retro.normalize("File /home/alice/x/a.py line 12 (id 3f2504e0-4f89-11d3-9a0c-0305e82c3301)")
        second = retro.normalize("File /home/bob/x/a.py line 987 (id 9b2c1e7a-1d3e-4f5a-8b6c-7d8e9f0a1b2c)")
        self.assertEqual(first, second)

    def test_collapses_whitespace_and_caps_length(self) -> None:
        self.assertEqual(retro.normalize("a   b\n c"), "a b c")
        self.assertLessEqual(len(retro.normalize("x" * 1000)), retro.KEY_LIMIT)


class FingerprintTests(unittest.TestCase):
    def test_is_stable_and_short_hex(self) -> None:
        first = retro.fingerprint("guard_deny", "git-guard: checkout")
        self.assertEqual(first, retro.fingerprint("guard_deny", "git-guard: checkout"))
        self.assertRegex(first, r"^[0-9a-f]{16}$")

    def test_differs_by_kind_and_key(self) -> None:
        self.assertNotEqual(retro.fingerprint("guard_deny", "k"), retro.fingerprint("tool_error", "k"))
        self.assertNotEqual(retro.fingerprint("tool_error", "a"), retro.fingerprint("tool_error", "b"))


class SignalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _parse(self, *records: dict) -> retro.ParsedSession:
        path = _write_jsonl(self.root / f"{SESSION}.jsonl", list(records))
        return retro.parse_session([path], session_id=SESSION)

    @staticmethod
    def _kinds(parsed: retro.ParsedSession) -> list[str]:
        return sorted(signal.kind for signal in parsed.signals)

    def test_guard_deny_keeps_guard_and_replay_input(self) -> None:
        parsed = self._parse(
            _assistant("m1", _tool_use("t1", "Bash", {"command": "git checkout ."})),
            _tool_result("t1", GUARD_DENY, is_error=True),
        )
        [signal] = [s for s in parsed.signals if s.kind == "guard_deny"]
        self.assertEqual(signal.guard, "git-guard")
        self.assertEqual(signal.tool_name, "Bash")
        self.assertEqual(signal.tool_input, {"command": "git checkout ."})
        self.assertNotIn("tool_error", self._kinds(parsed))

    def test_plain_tool_error_is_not_a_guard_deny(self) -> None:
        parsed = self._parse(
            _assistant("m1", _tool_use("t1", "Read", {"file_path": "/x/y.py"})),
            _tool_result("t1", "File does not exist.", is_error=True),
        )
        self.assertEqual(self._kinds(parsed), ["tool_error"])

    def test_repeated_identical_tool_use_needs_three_occurrences(self) -> None:
        command = {"command": "uv run --no-sync python -m unittest"}
        twice = self._parse(*[_assistant(f"m{i}", _tool_use(f"t{i}", "Bash", command)) for i in range(2)])
        self.assertNotIn("repeated_tool_use", self._kinds(twice))
        thrice = self._parse(*[_assistant(f"m{i}", _tool_use(f"t{i}", "Bash", command)) for i in range(3)])
        [signal] = [s for s in thrice.signals if s.kind == "repeated_tool_use"]
        self.assertEqual(signal.count, 3)

    def test_streamed_duplicate_of_one_tool_use_is_not_a_repeat(self) -> None:
        block = _tool_use("t1", "Bash", {"command": "ls"})
        parsed = self._parse(_assistant("m1", block), _assistant("m1", block), _assistant("m1", block))
        self.assertNotIn("repeated_tool_use", self._kinds(parsed))

    def test_code_edit_without_overlay_is_mcp_compliance_signal(self) -> None:
        edit = _tool_use("t1", "Edit", {"file_path": "src/guides/x.py", "old_string": "a", "new_string": "b"})
        self.assertIn("mcp_compliance", self._kinds(self._parse(_assistant("m1", edit))))

    def test_overlay_read_before_edit_clears_mcp_compliance(self) -> None:
        parsed = self._parse(
            _assistant("m1", _tool_use("t0", "mcp__project-guides__get_overlay", {})),
            _assistant("m2", _tool_use("t1", "Edit", {"file_path": "src/guides/x.py"})),
        )
        self.assertNotIn("mcp_compliance", self._kinds(parsed))

    def test_edit_outside_kit_code_paths_is_not_flagged(self) -> None:
        parsed = self._parse(_assistant("m1", _tool_use("t1", "Edit", {"file_path": "docs/adr/0016.md"})))
        self.assertNotIn("mcp_compliance", self._kinds(parsed))

    def test_api_rate_limit_error_is_classified(self) -> None:
        record = {
            "type": "assistant",
            "sessionId": SESSION,
            "isApiErrorMessage": True,
            "message": {"role": "assistant", "content": [{"type": "text", "text": "API Error: 429 rate_limit_error"}]},
        }
        [signal] = [s for s in self._parse(record).signals if s.kind == "api_error"]
        self.assertEqual(signal.key, "api:rate_limit")

    def test_harness_block_only_at_start_of_result(self) -> None:
        blocked = self._parse(
            _assistant("m1", _tool_use("t1", "Bash", {"command": "sleep 600"})),
            _tool_result("t1", "Blocked: sleep 600 is not allowed in this environment"),
        )
        self.assertIn("harness_block", self._kinds(blocked))
        quoted = self._parse(_tool_result("t2", "docs say: Blocked: sleep is a harness rule"))
        self.assertNotIn("harness_block", self._kinds(quoted))

    def test_harness_block_error_is_not_also_a_tool_error(self) -> None:
        parsed = self._parse(_tool_result("t1", "Blocked: sleep 600 is not allowed", is_error=True))
        self.assertEqual(self._kinds(parsed), ["harness_block"])

    def test_bash_exit_code_errors_are_grouped_by_stderr(self) -> None:
        parsed = self._parse(
            _tool_result("t1", "Exit code 1\nfatal: not a git repository", is_error=True),
            _tool_result("t2", "Exit code 2\nls: cannot access 'x'", is_error=True),
        )
        keys = {s.key for s in parsed.signals if s.kind == "tool_error"}
        self.assertEqual(len(keys), 2)

    def test_guard_deny_on_mcp_tool_with_hyphen_is_recognized(self) -> None:
        deny = "PreToolUse:mcp__project-guides__get_bundle hook error: server-guard: zablokowane"
        parsed = self._parse(_tool_result("t1", deny, is_error=True))
        self.assertEqual(self._kinds(parsed), ["guard_deny"])

    def test_metrics_count_each_api_message_once(self) -> None:
        usage = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 50}
        streamed = _assistant("msg_1", {"type": "text", "text": "a"}, usage=usage)
        second = _assistant("msg_2", {"type": "text", "text": "b"}, usage={**usage, "cache_read_input_tokens": 3000})
        parsed = self._parse(streamed, dict(streamed), second)
        self.assertEqual(parsed.metrics.api_calls, 2)
        self.assertEqual(parsed.metrics.cache_read_sum, 4000)
        self.assertEqual(parsed.metrics.max_context, 3000 + 10 + 50)


class ReplayTests(unittest.TestCase):
    """Deny z transkryptu odtwarza się na aktualnych guardach; naprawiony odpada."""

    @staticmethod
    def _deny(command: str = "cat a.md 2>/dev/null") -> retro.Signal:
        return retro.Signal(
            "guard_deny",
            "git-guard: checkout",
            "checkout",
            guard="git-guard",
            tool_name="Bash",
            tool_input={"command": command},
        )

    def test_exhausted_replay_budget_returns_unknown_without_running_guard(self) -> None:
        replay = retro.budgeted_replay(kit_root=KIT_ROOT, cwd=KIT_ROOT, budget=0)
        with mock.patch.object(retro, "replay_guard") as guard:
            self.assertEqual(replay(self._deny()), "unknown")
        guard.assert_not_called()

    def test_fixed_deny_is_dropped(self) -> None:
        self.assertEqual(retro.build_findings([self._deny()], replay=lambda signal: "allow"), [])

    def test_reproduced_deny_is_kept_with_replay_status(self) -> None:
        [finding] = retro.build_findings([self._deny()], replay=lambda signal: "deny")
        self.assertEqual(finding.kind, "guard_deny")
        self.assertEqual(finding.guard, "git-guard")
        self.assertEqual(finding.replay, "deny")

    def test_unknown_replay_keeps_the_finding(self) -> None:
        [finding] = retro.build_findings([self._deny()], replay=lambda signal: "unknown")
        self.assertEqual(finding.replay, "unknown")

    def test_other_signals_are_not_replayed(self) -> None:
        calls: list[retro.Signal] = []
        tool_error = retro.Signal("tool_error", "x", "x")
        findings = retro.build_findings([tool_error], replay=lambda signal: calls.append(signal) or "allow")
        self.assertEqual(calls, [])
        self.assertEqual(len(findings), 1)

    def test_identical_denies_are_replayed_once_and_counted(self) -> None:
        calls: list[retro.Signal] = []
        findings = retro.build_findings(
            [self._deny(), self._deny(), self._deny()],
            replay=lambda signal: calls.append(signal) or "deny",
        )
        self.assertEqual(len(calls), 1)
        [finding] = findings
        self.assertEqual(finding.count, 3)

    def test_count_includes_only_reproduced_denies(self) -> None:
        still = self._deny("git checkout .")
        fixed = self._deny("cat a.md 2>/dev/null")
        verdicts = {"git checkout .": "deny", "cat a.md 2>/dev/null": "allow"}
        [finding] = retro.build_findings([still, fixed], replay=lambda signal: verdicts[signal.tool_input["command"]])
        self.assertEqual(finding.count, 1)


@unittest.skipUnless(NODE, "brak node")
class ReplayWithGuardsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fake_kit(self, name: str, body: str) -> Path:
        guards = self.root / "templates" / "shared" / "guards"
        guards.mkdir(parents=True, exist_ok=True)
        (guards / f"{name}.mjs").write_text(body, encoding="utf-8")
        return self.root

    def test_redirect_to_dev_null_is_allowed_by_current_git_guard(self) -> None:
        status = retro.replay_guard(
            "git-guard", "Bash", {"command": "cat README.md 2>/dev/null"}, kit_root=KIT_ROOT, cwd=KIT_ROOT
        )
        self.assertEqual(status, "allow")

    def test_checkout_dot_is_still_denied_by_current_git_guard(self) -> None:
        status = retro.replay_guard("git-guard", "Bash", {"command": "git checkout ."}, kit_root=KIT_ROOT, cwd=KIT_ROOT)
        self.assertEqual(status, "deny")

    def test_deny_decision_from_guard_output_is_deny(self) -> None:
        body = 'process.stdout.write(JSON.stringify({hookSpecificOutput:{permissionDecision:"deny"}}));\n'
        root = self._fake_kit("fake-deny", body)
        self.assertEqual(retro.replay_guard("fake-deny", "Bash", {"command": "x"}, kit_root=root, cwd=root), "deny")

    def test_silent_guard_has_no_opinion_so_it_is_allow(self) -> None:
        root = self._fake_kit("fake-silent", "")
        self.assertEqual(retro.replay_guard("fake-silent", "Bash", {"command": "x"}, kit_root=root, cwd=root), "allow")

    def test_crashing_guard_is_unknown_not_allow(self) -> None:
        root = self._fake_kit("fake-crash", "process.exit(1);\n")
        self.assertEqual(retro.replay_guard("fake-crash", "Bash", {"command": "x"}, kit_root=root, cwd=root), "unknown")

    def test_missing_guard_missing_input_or_unsafe_name_is_unknown(self) -> None:
        self.assertEqual(
            retro.replay_guard("no-such-guard", "Bash", {"command": "x"}, kit_root=KIT_ROOT, cwd=KIT_ROOT), "unknown"
        )
        self.assertEqual(
            retro.replay_guard("../git-guard", "Bash", {"command": "x"}, kit_root=KIT_ROOT, cwd=KIT_ROOT), "unknown"
        )
        self.assertEqual(retro.replay_guard("git-guard", "Bash", None, kit_root=KIT_ROOT, cwd=KIT_ROOT), "unknown")


SECRET = "ghp_" + "Q" * 36
OLD_SESSION = "22222222-2222-4333-8444-555555555555"


def _run_cli(*argv: str, env: dict[str, str]) -> tuple[int, str]:
    out = io.StringIO()
    with mock.patch.dict(os.environ, env, clear=False):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
    return code, out.getvalue()


class ScanTests(unittest.TestCase):
    NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.projects = self.root / "projects"
        self.cache = self.root / "cache"
        self.workspace = self.root / "work" / "my-repo"
        self.workspace.mkdir(parents=True)
        self.project_dir = self.projects / retro.project_dir_name(self.workspace)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_main(self, session_id: str = SESSION, records: list[dict] | None = None) -> Path:
        if records is None:
            records = [
                _assistant(
                    "m1",
                    _tool_use("t1", "Bash", {"command": "git checkout ."}),
                    usage={"input_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
                ),
                _tool_result("t1", GUARD_DENY, is_error=True),
                _assistant("m2", _tool_use("t2", "Read", {"file_path": "/home/alice/x/notes.md"})),
                _tool_result("t2", f"token={SECRET} at /home/alice/x/notes.md " + "y" * 400, is_error=True),
            ]
        return _write_jsonl(self.project_dir / f"{session_id}.jsonl", records)

    def _scan(self, runner=None) -> Path:
        return retro.scan_session(
            SESSION,
            workspace=self.workspace,
            projects_root=self.projects,
            cache_root=self.cache,
            kit_root=KIT_ROOT,
            runner=runner or (lambda signal: "deny"),
            now=self.NOW,
        )

    def test_writes_session_record_and_findings_to_repo_cache(self) -> None:
        self._write_main()
        out = self._scan()
        self.assertEqual(out, self.cache / "my-repo" / f"{SESSION}.jsonl")
        records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        head, findings = records[0], records[1:]
        self.assertEqual(head["type"], "session")
        self.assertEqual(head["session"], SESSION)
        self.assertEqual(head["files"], 1)
        self.assertEqual(head["findings"], len(findings))
        self.assertEqual(head["metrics"], {"api_calls": 1, "cache_read_sum": 100, "max_context": 105})
        deny = next(record for record in findings if record["kind"] == "guard_deny")
        self.assertEqual((deny["guard"], deny["tool"], deny["replay"]), ("git-guard", "Bash", "deny"))
        self.assertIn("tool_error", [record["kind"] for record in findings])

    def test_never_stores_raw_secrets_home_paths_or_long_messages(self) -> None:
        self._write_main()
        text = self._scan().read_text(encoding="utf-8")
        self.assertNotIn(SECRET, text)
        self.assertNotIn("/home/alice", text)
        self.assertNotIn("y" * 300, text)
        for line in text.splitlines():
            self.assertLessEqual(len(json.loads(line).get("evidence", "")), retro.EVIDENCE_LIMIT)

    def test_fixed_deny_is_not_written(self) -> None:
        self._write_main()
        text = self._scan(runner=lambda signal: "allow").read_text(encoding="utf-8")
        self.assertNotIn('"guard_deny"', text)
        self.assertIn('"tool_error"', text)

    def test_subagent_transcripts_are_part_of_the_session(self) -> None:
        self._write_main(records=[_assistant("m1", _tool_use("t1", "Read", {"file_path": "/x/a.md"}))])
        _write_jsonl(
            self.project_dir / SESSION / "subagents" / "agent-1.jsonl",
            [_assistant("s1", _tool_use("u1", "Edit", {"file_path": "src/guides/x.py"}))],
        )
        out = self._scan()
        self.assertEqual(json.loads(out.read_text(encoding="utf-8").splitlines()[0])["files"], 2)
        self.assertIn('"mcp_compliance"', out.read_text(encoding="utf-8"))

    def test_rescan_overwrites_instead_of_duplicating(self) -> None:
        self._write_main()
        first = self._scan().read_text(encoding="utf-8")
        self.assertEqual(self._scan().read_text(encoding="utf-8"), first)

    def test_unknown_session_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "nie znaleziono sesji"):
            self._scan()

    def test_unsafe_session_id_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "nieprawidłowy identyfikator sesji"):
            retro.find_session_files(self.projects, "../escape")

    def test_batch_scan_honours_since_by_file_mtime(self) -> None:
        self._write_main(session_id=SESSION)
        old = self._write_main(session_id=OLD_SESSION)
        os.utime(old, (0, 0))
        message = retro.scan_command(
            self.workspace,
            session=None,
            since="2020-01-01",
            projects_root=self.projects,
            cache_root=self.cache,
            kit_root=KIT_ROOT,
            runner=lambda signal: "deny",
            now=self.NOW,
        )
        self.assertIn("sesje: 1", message)
        self.assertTrue((self.cache / "my-repo" / f"{SESSION}.jsonl").is_file())
        self.assertFalse((self.cache / "my-repo" / f"{OLD_SESSION}.jsonl").exists())


class HelperTests(unittest.TestCase):
    def test_project_dir_name_replaces_non_alphanumerics(self) -> None:
        self.assertEqual(
            retro.project_dir_name(Path("/home/alice/projects/my.repo_x")),
            "-home-alice-projects-my-repo-x",
        )

    def test_since_accepts_days_and_iso_date(self) -> None:
        now = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(retro.parse_since("2d", now=now), (now - timedelta(days=2)).timestamp())
        self.assertEqual(retro.parse_since("2026-11-01", now=now), datetime(2026, 11, 1).timestamp())
        with self.assertRaisesRegex(ValueError, "--since"):
            retro.parse_since("last week", now=now)

    def test_kit_sha_is_unknown_without_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(retro.kit_sha(Path(tmp)), "unknown")

    def test_kit_sha_reads_commit_of_kit_root_from_mcp_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            kit.mkdir()
            git = ["git", "-C", str(kit), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run(["git", "init", "-q", str(kit)], check=True)
            (kit / "f.txt").write_text("x", encoding="utf-8")
            subprocess.run([*git, "add", "f.txt"], check=True)
            subprocess.run([*git, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"], check=True)
            expected = subprocess.run(
                ["git", "-C", str(kit), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            work = Path(tmp) / "repo"
            work.mkdir()
            config = {"mcpServers": {"project-guides": {"command": "uv", "args": ["run", "--kit-root", str(kit)]}}}
            (work / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(retro.kit_sha(work), expected)


    def test_kit_sha_prefers_ref_pinned_in_uvx_from(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = "git+https://github.com/o/ai-instruction-kit-mcp.git@v1.2.3"
            config = {"mcpServers": {"project-guides": {"command": "uvx", "args": ["--from", source, "guides-mcp"]}}}
            (Path(tmp) / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(retro.kit_sha(Path(tmp)), "v1.2.3")


class RetroCliTests(unittest.TestCase):
    def test_scan_session_writes_cache_and_reports_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, cache = Path(tmp) / "home", Path(tmp) / "cache"
            workspace = Path(tmp) / "my-repo"
            workspace.mkdir()
            project = home / ".claude" / "projects" / retro.project_dir_name(workspace)
            _write_jsonl(
                project / f"{SESSION}.jsonl",
                [
                    _assistant("m1", _tool_use("t1", "Bash", {"command": "git checkout ."})),
                    _tool_result("t1", GUARD_DENY, is_error=True),
                ],
            )
            code, out = _run_cli(
                "retro", "scan", "--session", SESSION, str(workspace),
                env={"HOME": str(home), "XDG_CACHE_HOME": str(cache)},
            )
            self.assertEqual(code, 0, out)
            target = cache / "kit-ai" / "retro" / "my-repo" / f"{SESSION}.jsonl"
            self.assertTrue(target.is_file())
            self.assertIn(str(target), out)
            self.assertIn("guard_deny", out)
            self.assertIn('"replay": "deny"', target.read_text(encoding="utf-8"))

    def test_unknown_session_exits_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _run_cli(
                "retro", "scan", "--session", SESSION, tmp,
                env={"HOME": tmp, "XDG_CACHE_HOME": tmp},
            )
            self.assertEqual(code, 1)
            self.assertIn("nie znaleziono sesji", out)


class HeadlessRunTests(unittest.TestCase):
    """Przebieg headless (``.ai/headless-runs/<run>/headless.log``) to osobna sesja (GLOSSARY: Sesja)."""

    RUN = "2026-11-05T00-02-27-147Z-antigravity"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.workspace = self.root / "my-repo"
        self.run_dir = self.workspace / ".ai" / "headless-runs" / self.RUN
        self.run_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _log(self, text: str) -> None:
        (self.run_dir / "headless.log").write_text(text, encoding="utf-8")

    def _signals(self) -> list[tuple[str, str]]:
        return [(signal.kind, signal.key) for signal in retro.parse_headless_run(self.run_dir).signals]

    def test_nonzero_exit_is_reported_with_its_code(self) -> None:
        self._log("[headless] ticket #365\n[headless] kod wyjścia: 1\n")
        [signal] = retro.parse_headless_run(self.run_dir).signals
        self.assertEqual((signal.kind, signal.key), ("headless_exit", "exit-nonzero"))
        self.assertIn("kod wyjścia: 1", signal.evidence)

    def test_zero_exit_with_clean_tree_is_reported_as_no_change(self) -> None:
        self._log(
            "[headless] kod wyjścia: 0\n[headless] raport końcowy\n## git status --short\n(czysto)\n"
            "## git log 472c5d3..HEAD --oneline\n(brak commitów)\n"
        )
        self.assertEqual(self._signals(), [("headless_no_change", "exit0-clean-tree")])

    def test_zero_exit_with_commits_is_not_reported(self) -> None:
        self._log(
            "[headless] kod wyjścia: 0\n## git status --short\n(czysto)\n"
            "## git log 472c5d3..HEAD --oneline\na1b2c3d feat: coś\n"
        )
        self.assertEqual(self._signals(), [])

    def test_zero_exit_with_changes_is_not_reported(self) -> None:
        self._log("[headless] kod wyjścia: 0\n[headless] raport końcowy\n## git status --short\n M src/x.py\n")
        self.assertEqual(self._signals(), [])

    def test_run_without_exit_line_is_reported(self) -> None:
        self._log("[headless] sygnał SIGTERM po 1837.7 s\n")
        self.assertEqual(self._signals(), [("headless_exit", "exit-missing")])

    def test_last_exit_line_decides(self) -> None:
        self._log(
            "[headless] kod wyjścia: 1\n[headless] claude → antigravity\n"
            "[headless] kod wyjścia: 0\n## git status --short\n(czysto)\n"
            "## git log 472c5d3..HEAD --oneline\n(brak commitów)\n"
        )
        self.assertEqual(self._signals(), [("headless_no_change", "exit0-clean-tree")])

    def test_batch_scan_writes_headless_runs_as_sessions(self) -> None:
        self._log("[headless] kod wyjścia: 2\n")
        message = retro.scan_command(
            self.workspace,
            session=None,
            since=None,
            projects_root=self.root / "no-claude-projects",
            cache_root=self.root / "cache",
            kit_root=KIT_ROOT,
            runner=lambda signal: "deny",
            now=datetime(2026, 11, 6, tzinfo=timezone.utc),
        )
        target = self.root / "cache" / "my-repo" / f"{self.RUN}.jsonl"
        self.assertTrue(target.is_file(), message)
        records = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[0]["source"], "headless")
        self.assertEqual([record["kind"] for record in records[1:]], ["headless_exit"])
        self.assertIn("przebiegi headless: 1", message)


if __name__ == "__main__":
    unittest.main()
