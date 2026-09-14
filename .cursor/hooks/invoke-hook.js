#!/usr/bin/env node
/**
 * Adapter kontraktu hooka dla Cursora.
 *
 * Guardy w templates/shared/guards/*.mjs mowia jednym dialektem — kontraktem
 * Claude Code (`hookSpecificOutput.permissionDecision`). Claude Code wola je
 * wprost (`node .claude/hooks/git-guard.mjs`). Ten plik jest jedynym miejscem,
 * ktore wie, ze Cursor ma wlasny ksztalt wejscia i wyjscia:
 *
 *   node .cursor/hooks/invoke-hook.js git-guard.mjs --to cursor
 *   node .cursor/hooks/invoke-hook.js sensitive-files-guard.mjs --to cursor --tool Read
 *
 * Wejscie: Cursor `beforeShellExecution` daje `.command`, `beforeReadFile` daje
 * `.file_path` + `.content` bez nazwy narzedzia — `--tool` dopisuje `tool_name`,
 * zeby Guard odroznil odczyt od zapisu. `preToolUse` juz niesie `tool_name`.
 *
 * Wyjscie: `{ permission, user_message, agent_message }`. Po wypisaniu JSON zawsze
 * exit 0 — przy failClosed: true niezerowy kod ukrywa payload (Cursor traktuje to
 * jak awarie hooka). Awaria adaptera = deny (fail-closed).
 */
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const CLAUDE = "claude";
const CURSOR = "cursor";

const argv = process.argv.slice(2);
const scriptName = argv.shift();

let target = CLAUDE;
let toolName = "";
const scriptArgs = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--to") {
    target = String(argv[++i] || CLAUDE).toLowerCase();
  } else if (argv[i].startsWith("--to=")) {
    target = argv[i].slice("--to=".length).toLowerCase();
  } else if (argv[i] === "--tool") {
    toolName = String(argv[++i] || "");
  } else if (argv[i].startsWith("--tool=")) {
    toolName = argv[i].slice("--tool=".length);
  } else {
    scriptArgs.push(argv[i]);
  }
}

function render(decision, reason) {
  if (target === CURSOR) {
    if (decision === "allow") {
      return '{ "permission": "allow" }';
    }
    return JSON.stringify({
      permission: decision,
      user_message: `Zablokowano: ${reason}`,
      agent_message: `Hook ${scriptName || "invoke-hook"}: ${decision.toUpperCase()} — ${reason}`,
    });
  }
  return JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: decision,
      permissionDecisionReason: reason,
    },
  });
}

function emitAndExit(decision, reason) {
  process.stdout.write(render(decision, reason));
  process.exit(0);
}

const emitDeny = (message) => emitAndExit("deny", `invoke-hook: ${String(message)}`);

if (!scriptName) {
  emitDeny("brak nazwy skryptu hooka");
}

const hookPath = path.join(__dirname, scriptName);
if (!fs.existsSync(hookPath)) {
  emitDeny(`brak pliku ${scriptName}`);
}

let stdin = "";
try {
  stdin = fs.readFileSync(0, "utf8");
} catch {
  stdin = "";
}
if (stdin.charCodeAt(0) === 0xfeff) {
  stdin = stdin.slice(1);
}

// `--tool` uzupelnia payload Cursora o to, co Claude Code daje z natury.
if (toolName) {
  try {
    const payload = JSON.parse(stdin || "{}");
    if (!payload.tool_name) payload.tool_name = toolName;
    stdin = JSON.stringify(payload);
  } catch {
    // Nieczytelny payload przekazujemy dalej — Guard sam odpowie deny.
  }
}

const result = spawnSync(process.execPath, [hookPath, ...scriptArgs], {
  input: stdin,
  encoding: "utf8",
  windowsHide: true,
  shell: false,
});

if (result.error) {
  emitDeny(result.error.message || "nie mozna uruchomic node");
}

const out = (result.stdout || "").trim();
if (!out) {
  const err = (result.stderr || "").trim().slice(0, 160) || "pusty stdout";
  emitDeny(err);
}

if (target !== CURSOR) {
  process.stdout.write(out);
  process.exit(0);
}

let decision;
try {
  decision = JSON.parse(out).hookSpecificOutput;
} catch {
  emitDeny(`niepoprawny JSON polityki: ${out.slice(0, 160)}`);
}
if (!decision || !decision.permissionDecision) {
  emitDeny(`brak permissionDecision w wyjsciu polityki: ${out.slice(0, 160)}`);
}

emitAndExit(decision.permissionDecision, decision.permissionDecisionReason || "bez powodu");
