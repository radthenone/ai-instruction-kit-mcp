#!/usr/bin/env node
/**
 * Hook SessionEnd (#371): skaner sesji `kit-ai retro scan --session <id>`.
 *
 * Po zakończeniu sesji Claude uruchamia skaner retro na jej transkrypcie razem z
 * subagentami i zapisuje wpisy do ~/.cache/kit-ai/retro/<repo>/. Hook nie blokuje
 * zamknięcia sesji: brak `kit-ai`, zły identyfikator albo błąd skanera kończą się
 * cichym wyjściem 0. Katalog repo: `cwd` z wejścia hooka, potem `CLAUDE_PROJECT_DIR`.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SESSION_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

let input = {};
try {
  input = JSON.parse(readFileSync(0, "utf8") || "{}");
} catch {
  input = {};
}

const sessionId = typeof input.session_id === "string" ? input.session_id : "";
if (!SESSION_ID.test(sessionId)) process.exit(0);

const cwd = (typeof input.cwd === "string" && input.cwd) || process.env.CLAUDE_PROJECT_DIR || process.cwd();

spawnSync("kit-ai", ["retro", "scan", "--session", sessionId, cwd], {
  stdio: "ignore",
  timeout: 120000,
  windowsHide: true,
});
process.exit(0);
