"""Plugin opencode V2 z guardami kita: fake ctx w Node, prawdziwe guardy i adapter."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = KIT_ROOT / "templates/opencode/plugins/kit-guards.js"
GUARDS = KIT_ROOT / "templates/shared/guards"

SCRIPT = """
import { pathToFileURL } from "node:url"
import assert from "node:assert/strict"
const mod = await import(pathToFileURL(process.argv[1]).href)
assert.deepEqual(Object.keys(mod), ["default"], "opencode V2 ładuje default export { id, setup }")
assert.equal(mod.default.id, "kit-guards")

let before
await mod.default.setup({
  tool: { hook: async (name, fn) => { assert.equal(name, "execute.before"); before = fn } },
})
const run = (tool, input) => before({ tool, sessionID: "s", callID: "c", input })
const denied = async (tool, input, pattern) => {
  await assert.rejects(run(tool, input), pattern, `${tool} ${JSON.stringify(input)} powinno być deny`)
}

// Nazwy i pola z opencode 2.0.24: `shell`, `read`/`write`/`edit` z `path`, `patch` z `patchText`.
await denied("shell", { command: "git reset --hard" }, /git-guard/)
await denied("shell", { command: "git push origin master" }, /git-guard/)
// Bash/RTK omijał Read — guard widzi formę oryginalną i przepisaną (#231).
await denied("shell", { command: "cat .env" }, /sensitive-files-guard/)
await denied("shell", { command: "rtk read .env --max-lines 5" }, /sensitive-files-guard/)
await denied("bash", { command: "rtk grep KEY .env" }, /sensitive-files-guard/)
await denied("read", { path: ".env" }, /sensitive-files-guard: \\.env/)
await denied("write", { path: "/repo/.env", content: "X=1" }, /sekret/)
await denied("edit", { path: "uv.lock", oldString: "a", newString: "b" }, /sensitive-files-guard/)
await denied("patch", { patchText: "*** Begin Patch\\n*** Add File: src/ok.py\\n+x\\n*** Update File: .env\\n@@\\n-a\\n+b\\n*** End Patch" }, /\\.env/)
await denied("patch", { patchText: "*** Begin Patch\\n*** Update File: a.py\\n*** Move to: .env\\n*** End Patch" }, /\\.env/)
// starsze nazwy (V1 / dokumentacja): `bash`, `filePath`
await denied("bash", { command: "git reset --hard" }, /git-guard/)
await denied("read", { filePath: ".env" }, /sensitive-files-guard/)
// brak oczekiwanego pola = deny, nie cichy allow
await denied("shell", {}, /brak/)

await run("shell", { command: "git status" })
await run("shell", { command: "cat README.md" })
await run("read", { path: "src/app.py" })
await run("patch", { patchText: "*** Begin Patch\\n*** Add File: src/ok.py\\n+x\\n*** End Patch" })
await run("glob", { pattern: "**/*.py" })
// Narzędzia Playwright MCP na PC przechodzą (server-guard nieaktywny).
await run("playwright_browser_navigate", { url: "http://x" })
console.log("ok")
"""

VPS_SCRIPT = SCRIPT.split("// Nazwy i pola")[0] + """
await denied("shell", { command: "docker compose up" }, /server-guard/)
await denied("bash", { command: "sudo uv sync" }, /server-guard/)
await denied("shell", { command: "rtk bun install" }, /server-guard/)
await denied("shell", { command: "rtk proxy -- bun install" }, /server-guard/)
await denied("shell", { command: "rtk test 'bun install'" }, /server-guard/)
await denied("shell", { command: "rtk ".repeat(8000) + "bun install" }, /server-guard/)
await denied("shell", { command: "rtk next dev" }, /server-guard/)
await denied("shell", { command: "rtk proxy 'bun install'" }, /server-guard/)
await denied("playwright_browser_navigate", { url: "http://x" }, /server-guard/)
await run("shell", { command: "git status" })
await run("shell", { command: "uv run --no-sync ruff check ." })
console.log("ok")
"""


@unittest.skipUnless(shutil.which("node"), "brak node")
class KitGuardsPluginTest(unittest.TestCase):
    def test_guards_block_dangerous_tools_and_pass_safe_ones(self) -> None:
        self._run(SCRIPT, {"KIT_HOST_PROFILE": "local"})

    def test_server_guard_on_vps(self) -> None:
        self._run(VPS_SCRIPT, {"KIT_HOST_PROFILE": "vps", "UV_NO_SYNC": ""})

    def _run(self, script: str, env: dict[str, str]) -> None:
        # Układ jak po bootstrapie: .opencode/plugins/ obok .opencode/hooks/.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".opencode"
            (root / "plugins").mkdir(parents=True)
            shutil.copytree(GUARDS, root / "hooks")
            plugin = root / "plugins" / PLUGIN.name
            shutil.copy(PLUGIN, plugin)
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(plugin)],
                capture_output=True,
                env={**os.environ, **env},
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
