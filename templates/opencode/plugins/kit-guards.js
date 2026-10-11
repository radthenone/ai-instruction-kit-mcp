// Guardy kita w opencode V2 — odpowiednik hooków PreToolUse z Claude Code.
// Przed narzędziem woła `node .opencode/hooks/invoke-hook.js <guard> --to opencode --tool <X>`;
// deny = rzucony błąd, który opencode oddaje modelowi jako wynik narzędzia. Działa
// niezależnie od `permission` w opencode.json, także przy `allow` na bash i edycje.
//
// Nazwy narzędzi sprawdzone na opencode 2.0.24 (`shell`, `read`/`write`/`edit` z `path`,
// `patch` z `patchText`); `bash`, `multiedit` i `filePath` to starsze nazwy z dokumentacji.
// Awaria guarda albo adaptera = deny (fail-closed).

// Bez importu @opencode/plugin — patrz kit-loop.js.
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const ADAPTER = fileURLToPath(new URL("../hooks/invoke-hook.js", import.meta.url))
const GIT = ["git-guard.mjs", "Bash"]
const FILES = "sensitive-files-guard.mjs"
// narzędzie opencode → [guard, nazwa narzędzia Claude, którą rozumie guard]
const GUARDS = {
  shell: GIT,
  bash: GIT,
  read: [FILES, "Read"],
  edit: [FILES, "Edit"],
  multiedit: [FILES, "Edit"],
  write: [FILES, "Write"],
  patch: [FILES, "Write"],
}

function check(tool, input) {
  const [guard, claudeTool] = GUARDS[tool]
  // `node`, nie process.execPath — opencode działa na Bunie, guardy to skrypty Node.
  const result = spawnSync("node", [ADAPTER, guard, "--to", "opencode", "--tool", claudeTool], {
    input: JSON.stringify({ tool, input }),
    encoding: "utf8",
    timeout: 10000,
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

// Patch dotyka wielu plików — każdy (także cel `Move to`) idzie przez guard osobno.
const patchPaths = (text) =>
  [...String(text || "").matchAll(/^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/gm)].map((m) => m[1].trim())

export default {
  id: "kit-guards",
  async setup(ctx) {
    await ctx.tool.hook("execute.before", async (event) => {
      const input = event.input || {}
      if (!GUARDS[event.tool]) return
      if (event.tool !== "patch") return check(event.tool, input)
      for (const path of patchPaths(input.patchText)) check("patch", { path })
    })
  },
}
