#!/usr/bin/env node
/**
 * Guard: sekrety i pliki generowane (PreToolUse: Read|Edit|Write|MultiEdit|NotebookEdit).
 *
 * Sekrety — deny na odczyt i zapis (agent nie wciaga ich do kontekstu i nie nadpisuje):
 *   .env, .env.* (poza .env.example / .env.sample / .env.template)
 *   *.pem *.key *.p12 *.pfx
 *   id_rsa* id_ed25519* id_ecdsa*
 *   .netrc  credentials.json
 *   .git/objects/  .git/refs/  .git/hooks/   (HEAD i config zostaja czytelne)
 *
 * Lockfile — deny tylko na zapis; odczyt wolny, a `npm install` / `uv sync` przez
 * Bash regeneruja je legalnie:
 *   package-lock.json pnpm-lock.yaml yarn.lock bun.lockb
 *   uv.lock poetry.lock Pipfile.lock Cargo.lock
 *
 * Zero `ask` — ADR 0006. Reszta plikow przechodzi; zapisy poza repo pilnuje
 * natywna permission klienta (cwd + additionalDirectories), nie ten Guard.
 *
 * Kontrakt: Claude Code (`tool_name`, `tool_input.file_path|notebook_path`).
 * Cursor przez invoke-hook.js --to cursor --tool Read|Write: adapter dopisuje
 * `tool_name`, bo `beforeReadFile` podaje tylko `file_path` + `content`.
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";

const emit = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};

let raw = "";
try {
  raw = readFileSync(0, "utf8");
} catch {
  raw = "";
}
if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);

let payload;
try {
  payload = JSON.parse(raw || "{}");
} catch {
  emit("deny", "sensitive-files-guard: nieczytelny payload hooka");
}

const toolInput = payload.tool_input || {};
const file = String(toolInput.file_path || toolInput.notebook_path || payload.file_path || "");
if (!file) emit("allow", "sensitive-files-guard: brak sciezki");

// Read = odczyt. Cursor `beforeReadFile` nie ma tool_name, ale niesie `content`.
const toolName = String(payload.tool_name || "");
const isRead = toolName === "Read" || (!toolName && "content" in payload);

const posix = file.replace(/\\/g, "/");
const name = basename(posix);
const lower = name.toLowerCase();

const ENV_ALLOWED = new Set([".env.example", ".env.sample", ".env.template"]);
const SECRET_NAMES = new Set([".netrc", "credentials.json"]);
const SECRET_EXT = /\.(pem|key|p12|pfx)$/i;
const SSH_KEY = /^id_(rsa|ed25519|ecdsa)/i;
const GIT_INTERNAL = /(^|\/)\.git\/(objects|refs|hooks)(\/|$)/;

const isSecret =
  (lower === ".env" || (lower.startsWith(".env.") && !ENV_ALLOWED.has(lower))) ||
  SECRET_NAMES.has(lower) ||
  SECRET_EXT.test(lower) ||
  SSH_KEY.test(lower) ||
  GIT_INTERNAL.test(posix);

if (isSecret) {
  emit("deny", `sensitive-files-guard: ${name} to sekret — ani odczyt, ani zapis; popros uzytkownika`);
}

const LOCKFILES = new Set([
  "package-lock.json",
  "pnpm-lock.yaml",
  "yarn.lock",
  "bun.lockb",
  "uv.lock",
  "poetry.lock",
  "pipfile.lock",
  "cargo.lock",
]);

if (!isRead && LOCKFILES.has(lower)) {
  emit("deny", `sensitive-files-guard: ${name} jest generowany — nie edytuj recznie, uruchom menedzer pakietow`);
}

emit("allow", "sensitive-files-guard: ok");
