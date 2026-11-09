"""Wiersze wywołań headless trafiają do bufora nocy i do NIGHT-RUN REPORT (#407, #396).

Szablony są źródłem prawdy; testy pilnują, że procedura /night-run podaje wrapperowi
katalog CTX, składa HEADLESS REPORT, zbiera zaległe bufory i niesie wiersz wywołania
w komentarzu needs-human.
"""

from __future__ import annotations

import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
AGENTS = KIT_ROOT / "templates" / "shared" / "agents"


def _read(name: str) -> str:
    return (AGENTS / name).read_text(encoding="utf-8")


def _assert_has(test: unittest.TestCase, text: str, needle: str) -> None:
    test.assertTrue(needle in text, f"brak w szablonie: {needle!r}")


class NightRunHeadlessRowsTemplateTest(unittest.TestCase):
    def test_night_run_passes_ctx_dir_to_headless_wrapper(self) -> None:
        text = _read("night-run.md")
        _assert_has(self, text, "--ctx <CTX_DIR>")

    def test_night_run_builds_headless_report_before_final_report(self) -> None:
        text = _read("night-run.md")
        _assert_has(self, text, 'node .ai/headless.mjs --report --ctx "$CTX_DIR"')
        _assert_has(self, text, "## HEADLESS REPORT")

    def test_night_run_collects_stale_buffers_from_previous_nights(self) -> None:
        text = _read("night-run.md")
        _assert_has(self, text, "zaległe wywołania")
        _assert_has(self, text, "headless-rows.jsonl")

    def test_needs_human_comment_carries_call_row(self) -> None:
        text = _read("night-run.md")
        _assert_has(self, text, "Wywołanie headless:")

    def test_headless_md_documents_ctx_flag_and_row_buffer(self) -> None:
        text = _read("headless.md")
        _assert_has(self, text, "[--ctx <katalog>]")
        _assert_has(self, text, "headless-rows.jsonl")


if __name__ == "__main__":
    unittest.main()
