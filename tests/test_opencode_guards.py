"""Plugin opencode V2 z guardami kita: fake ctx w Node, prawdziwe guardy i adapter."""

from __future__ import annotations

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

await denied("bash", { command: "git reset --hard" }, /git-guard/)
await denied("bash", { command: "git push origin master" }, /git-guard/)
await denied("read", { filePath: ".env" }, /sensitive-files-guard: \\.env/)
await denied("write", { filePath: "/repo/.env", content: "X=1" }, /sekret/)
await denied("edit", { filePath: "uv.lock", oldString: "a", newString: "b" }, /sensitive-files-guard/)

await run("bash", { command: "git status" })
await run("read", { filePath: "src/app.py" })
await run("glob", { pattern: "**/*.py" })
console.log("ok")
"""


@unittest.skipUnless(shutil.which("node"), "brak node")
class KitGuardsPluginTest(unittest.TestCase):
    def test_guards_block_dangerous_tools_and_pass_safe_ones(self) -> None:
        # Układ jak po bootstrapie: .opencode/plugins/ obok .opencode/hooks/.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".opencode"
            (root / "plugins").mkdir(parents=True)
            shutil.copytree(GUARDS, root / "hooks")
            plugin = root / "plugins" / PLUGIN.name
            shutil.copy(PLUGIN, plugin)
            result = subprocess.run(
                ["node", "--input-type=module", "-e", SCRIPT, str(plugin)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
