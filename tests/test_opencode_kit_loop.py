"""Plugin opencode /goal /loop: fake client w Node, symulacja zdarzeń sesji."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "templates/opencode/plugins/kit-loop.js"

SCRIPT = """
import { pathToFileURL } from "node:url"
import assert from "node:assert/strict"
const mod = await import(pathToFileURL(process.argv[1]).href)
assert.deepEqual(Object.keys(mod), ["KitLoop"], "każdy eksport opencode ładuje jako plugin")

let reply = { info: { role: "assistant" }, parts: [{ type: "text", text: "krok" }] }
const prompts = []
const client = {
  tui: { showToast: async () => {} },
  session: {
    messages: async () => ({ data: [reply] }),
    prompt: async (req) => { prompts.push(req.body.parts[0].text) },
  },
}
const hooks = await mod.KitLoop({ client })
const run = (command, args) => hooks["command.execute.before"]({ command, sessionID: "s", arguments: args }, { parts: [] })
const idle = () => hooks.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })

// goal: wznawia do limitu max=N, potem stop
await run("goal", "max=2 zielone testy")
await idle(); await idle(); await idle(); await idle()
assert.equal(prompts.length, 2)
assert.match(prompts[0], /\\[\\/goal tura 1\\/2\\] Kontynuuj: zielone testy/)

// DONE kończy pętlę
prompts.length = 0
await run("goal", "cel")
reply = { info: { role: "assistant" }, parts: [{ type: "text", text: "ok\\n<promise>DONE</promise>" }] }
await idle(); await idle()
assert.equal(prompts.length, 0)

// DONE liczy się tylko jako ostatnia linia — wzmianka w treści nie kończy pętli
await run("goal", "cel")
reply = { info: { role: "assistant" }, parts: [{ type: "text", text: "nie wypisuję jeszcze <promise>DONE</promise>, testy czerwone" }] }
await idle()
assert.equal(prompts.length, 1)
reply = { info: { role: "assistant" }, parts: [{ type: "text", text: "ok\\n  <promise>DONE</promise>  \\n" }] }
await idle()
assert.equal(prompts.length, 1)
prompts.length = 0

// Esc (abort) kończy pętlę
reply = { info: { role: "assistant", error: { name: "MessageAbortedError" } }, parts: [] }
await run("loop", "zadanie")
await idle()
assert.equal(prompts.length, 0)

// /loop stop kończy pętlę; bez komendy idle nic nie robi
reply = { info: { role: "assistant" }, parts: [{ type: "text", text: "krok" }] }
await run("loop", "zadanie")
await run("loop", "stop")
await idle()
assert.equal(prompts.length, 0)

// interwał: prompt dopiero po timerze, stop w trakcie czekania go kasuje
await run("loop", "1s max=3 sprawdz CI")
await idle()
assert.equal(prompts.length, 0)
await run("loop", "stop")
await new Promise((r) => setTimeout(r, 1100))
assert.equal(prompts.length, 0)
console.log("ok")
"""


@unittest.skipUnless(shutil.which("node"), "brak node")
class KitLoopPluginTest(unittest.TestCase):
    def test_loop_lifecycle(self) -> None:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", SCRIPT, str(PLUGIN)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


class LoopCommandTest(unittest.TestCase):
    def test_loop_never_waits_for_user(self) -> None:
        # Plugin uzbraja pętlę dla każdego /loop poza stop — pytanie i czekanie
        # na odpowiedź przegrywa z kolejną turą „Kontynuuj”.
        text = (PLUGIN.parents[1] / "command/loop.md").read_text(encoding="utf-8")
        self.assertNotIn("czekaj", text)


if __name__ == "__main__":
    unittest.main()
