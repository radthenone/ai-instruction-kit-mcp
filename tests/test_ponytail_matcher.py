"""Testy wyrenderowanego PONYTAIL_SUBAGENT_MATCHER (#316).

Matcher skompilowany jako JS-owy RegExp z flagą i (tak jak robi ponytail):
- nie pasuje do żadnego agenta „procedura” kita,
- pasuje do subagent-backend, subagent-frontend, general-purpose, Explore i caveman:cavecrew-builder.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from claude_settings import build_ponytail_matcher, get_procedure_agent_names

SHARED_AGENTS = ROOT / "templates" / "shared" / "agents"


class PonytailMatcherTest(unittest.TestCase):
    def test_matcher_excludes_all_procedure_agents_and_matches_code_and_plugins_in_js(self) -> None:
        matcher = build_ponytail_matcher(SHARED_AGENTS)
        procedures = get_procedure_agent_names(SHARED_AGENTS)

        self.assertGreater(len(procedures), 10, "Powinno być co najmniej kilkunastu agentów procedur")

        expected_matches = [
            "subagent-backend",
            "subagent-frontend",
            "general-purpose",
            "Explore",
            "caveman:cavecrew-builder",
            "custom-plugin:worker",
        ]

        js_script = """
        const matcher = process.argv[1];
        const re = new RegExp(matcher, "i");
        const procedures = JSON.parse(process.argv[2]);
        const shouldMatch = JSON.parse(process.argv[3]);

        const failedProcedures = [];
        for (const p of procedures) {
            if (re.test(p)) {
                failedProcedures.push(p);
            }
        }

        const failedShouldMatch = [];
        for (const m of shouldMatch) {
            if (!re.test(m)) {
                failedShouldMatch.push(m);
            }
        }

        console.log(JSON.stringify({ failedProcedures, failedShouldMatch }));
        """

        result = subprocess.run(
            ["node", "-e", js_script, matcher, json.dumps(procedures), json.dumps(expected_matches)],
            capture_output=True,
            text=True,
            check=True,
        )

        outcome = json.loads(result.stdout)
        self.assertEqual(
            outcome["failedProcedures"],
            [],
            f"Matcher nie powinien pasować do agentów procedur: {outcome['failedProcedures']}",
        )
        self.assertEqual(
            outcome["failedShouldMatch"],
            [],
            f"Matcher powinien pasować do agentów kodu i pluginów: {outcome['failedShouldMatch']}",
        )


if __name__ == "__main__":
    unittest.main()
