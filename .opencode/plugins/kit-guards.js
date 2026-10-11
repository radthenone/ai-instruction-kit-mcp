// Guardy kita w opencode V2 — odpowiednik hooków PreToolUse z Claude Code.
// Przed każdym narzędziem woła `node .opencode/hooks/invoke-hook.js <guard> --to opencode`;
// deny = rzucony błąd, który opencode oddaje modelowi jako wynik narzędzia. Działa
// niezależnie od `permission` w opencode.json, także przy `allow` na bash i edycje.
//
// bash → git-guard, read/edit/write/multiedit → sensitive-files-guard (jak matchery
// w .claude/settings.json). Awaria guarda albo adaptera = deny (fail-closed).

// Bez importu @opencode/plugin — patrz kit-loop.js.
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const ADAPTER = fileURLToPath(new URL("../hooks/invoke-hook.js", import.meta.url))
const GUARDS = {
  bash: "git-guard.mjs",
  read: "sensitive-files-guard.mjs",
  edit: "sensitive-files-guard.mjs",
  write: "sensitive-files-guard.mjs",
  multiedit: "sensitive-files-guard.mjs",
}

function check(tool, input) {
  const guard = GUARDS[tool]
  if (!guard) return
  // `node`, nie process.execPath — opencode działa na Bunie, guardy to skrypty Node.
  const result = spawnSync("node", [ADAPTER, guard, "--to", "opencode"], {
    input: JSON.stringify({ tool, input }),
    encoding: "utf8",
    windowsHide: true,
  })
  let verdict
  try {
    verdict = JSON.parse(result.stdout || "")
  } catch {
    verdict = { decision: "deny", reason: `${guard}: brak odpowiedzi (${result.error?.message || result.stderr || "pusty stdout"})` }
  }
  if (verdict.decision !== "allow") {
    throw new Error(`Zablokowane przez guard kita — ${verdict.reason || guard}`)
  }
}

export default {
  id: "kit-guards",
  async setup(ctx) {
    await ctx.tool.hook("execute.before", async (event) => check(event.tool, event.input || {}))
  },
}
