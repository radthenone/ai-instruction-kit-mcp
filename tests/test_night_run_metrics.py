"""Pomiar kosztu w night-run.md (#75, #409) — jedno źródło: ``kit-ai retro scan``.

Snippet żyje w treści agenta; test pilnuje, że nie wraca ręczne liczenie kosztu
obok ``kit-ai retro scan`` (drugie źródło kosztu Sesji).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from guides.manifest import find_kit_root

AGENT = find_kit_root(Path(__file__)) / "templates" / "shared" / "agents" / "night-run.md"


class NightRunMetricsSource(unittest.TestCase):
    def test_cost_measurement_uses_retro_scan_only(self) -> None:
        text = AGENT.read_text(encoding="utf-8")
        self.assertIn("kit-ai retro scan --session <sesja>", text)
        self.assertNotIn("python3 -c '", text)


if __name__ == "__main__":
    unittest.main()
