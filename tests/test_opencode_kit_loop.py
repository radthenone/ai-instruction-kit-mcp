"""Plugin opencode V2 /goal /loop: fake ctx w Node, symulacja promptów i zdarzeń sesji."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "templates/opencode/plugins/kit-loop.js"

SCRIPT = """
import { pathToFileURL } from "node:url"
import { readFileSync } from "node:fs"
import assert from "node:assert/strict"
const mod = await import(pathToFileURL(process.argv[1]).href)
assert.deepEqual(Object.keys(mod), ["default"], "opencode V2 ładuje default export { id, setup }")
assert.equal(mod.default.id, "kit-loop")

let reply = { type: "assistant", content: [{ type: "text", text: "krok" }] }
const prompts = []
let onPrompt
let ctxCalls = 0
const queue = []
let wake
const ctx = {
  session: {
    hook: async (name, fn) => { assert.equal(name, "prompt"); onPrompt = fn },
    // 2.0.18 zwraca gołą tablicę; wrapper HTTP — `{ data }`. Test na zmianę oba.
    context: async () => (ctxCalls++ % 2 ? [{ type: "user", content: [] }, reply] : { data: [{ type: "user", content: [] }, reply] }),
    prompt: async (req) => { assert.equal(req.sessionID, "s"); prompts.push(req.text) },
  },
  event: {
    subscribe: async function* ({ signal }) {
      while (!signal.aborted) {
        if (queue.length) yield queue.shift()
        else await new Promise((r) => (wake = r))
      }
    },
  },
}
const dispose = await mod.default.setup(ctx)
const tick = () => new Promise((r) => setTimeout(r, 5))
const say = async (text) => { await onPrompt({ sessionID: "s", prompt: { text } }); await tick() }
const run = (command, args) => say(`/${command} ${args}`)
const idle = async () => { queue.push({ type: "session.execution.succeeded", data: { sessionID: "s" } }); wake?.(); await tick() }

// goal: wznawia do limitu max=N, potem stop
await run("goal", "max=2 zielone testy")
await idle(); await idle(); await idle(); await idle()
assert.equal(prompts.length, 2)
assert.match(prompts[0], /\\[\\/goal tura 1\\/2\\] Kontynuuj: zielone testy/)

// `opencode run "/goal …"` — tekst w cudzysłowach też uzbraja pętlę
prompts.length = 0
await say('"/goal max=1 z run"')
await idle(); await idle()
assert.equal(prompts.length, 1)
assert.match(prompts[0], /Kontynuuj: z run/)

// zwykły prompt nie uzbraja pętli
prompts.length = 0
await say("napraw bug")
await idle()
assert.equal(prompts.length, 0)

// rozwinięty markdown komendy (tak opencode wysyła /goal) też uzbraja pętlę
const md = readFileSync(new URL("../command/goal.md", pathToFileURL(process.argv[1])), "utf8")
await say(md.replace("$ARGUMENTS", "max=1 z markdowna"))
await idle(); await idle()
assert.equal(prompts.length, 1)
assert.match(prompts[0], /\\[\\/goal tura 1\\/1\\] Kontynuuj: z markdowna/)

// puste argumenty w markdownie (samo /goal, /loop) = status, nie uzbraja pętli
prompts.length = 0
for (const name of ["goal", "loop"]) {
  const text = readFileSync(new URL(`../command/${name}.md`, pathToFileURL(process.argv[1])), "utf8")
  await say(text.replace("$ARGUMENTS", ""))
  await idle()
}
assert.equal(prompts.length, 0)

// /goal-setting to nie /goal
await say("/goal-setting ustaw coś")
await idle()
assert.equal(prompts.length, 0)

// DONE kończy pętlę
await run("goal", "cel")
reply = { type: "assistant", content: [{ type: "text", text: "ok\\n<promise>DONE</promise>" }] }
await idle(); await idle()
assert.equal(prompts.length, 0)

// DONE liczy się tylko jako ostatnia linia — wzmianka w treści nie kończy pętli
await run("goal", "cel")
reply = { type: "assistant", content: [{ type: "text", text: "nie wypisuję jeszcze <promise>DONE</promise>, testy czerwone" }] }
await idle()
assert.equal(prompts.length, 1)
reply = { type: "assistant", content: [{ type: "text", text: "ok\\n  <promise>DONE</promise>  \\n" }] }
await idle()
assert.equal(prompts.length, 1)
prompts.length = 0

// błąd na ostatniej wiadomości kończy pętlę
reply = { type: "assistant", error: { name: "MessageAbortedError" }, content: [] }
await run("loop", "zadanie")
await idle()
assert.equal(prompts.length, 0)

// Esc = session.execution.interrupted — pętla stoi, późniejszy succeeded nic nie wysyła
reply = { type: "assistant", content: [{ type: "text", text: "krok" }] }
await run("loop", "zadanie")
queue.push({ type: "session.execution.interrupted", data: { sessionID: "s", reason: "user" } }); wake?.(); await tick()
await idle()
assert.equal(prompts.length, 0)

// session.idle z V1 nie budzi pętli
await run("loop", "zadanie")
queue.push({ type: "session.idle", data: { sessionID: "s" } }); wake?.(); await tick()
assert.equal(prompts.length, 0)
await run("loop", "stop")

// /loop stop kończy pętlę; bez komendy idle nic nie robi
reply = { type: "assistant", content: [{ type: "text", text: "krok" }] }
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

// drugi idle w trakcie odliczania nie dubluje tury
await run("loop", "1s max=3 sprawdz CI")
await idle(); await idle()
await new Promise((r) => setTimeout(r, 1100))
assert.equal(prompts.length, 1)
await run("loop", "stop")

dispose()
wake?.()
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
