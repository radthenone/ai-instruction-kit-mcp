#!/usr/bin/env node
/**
 * Launcher + adapter kontraktu hooka.
 *
 * Skrypty polityki w templates/shared/guards/ mowia jednym dialektem — kontraktem
 * Claude Code (`hookSpecificOutput.permissionDecision`). Ten plik jest jedynym
 * miejscem, ktore wie, ze inny klient ma wlasny ksztalt wyjscia.
 *
 *   Claude: node .claude/hooks/invoke-hook.js gate-destructive.sh
 *   Cursor: node .cursor/hooks/invoke-hook.js gate-destructive.sh --to cursor
 *
 * Polityka to zwykly skrypt POSIX sh/bash — na Linuksie i macOS wolamy `bash`
 * z PATH. Windows nie ma go w PATH, wiec tam (i tylko tam) szukamy Git Basha.
 * `--noprofile --norc` zamiast `--login -i`: bez ladowania ~/.bashrc uzytkownika
 * i bez zostawionych okien konsoli.
 *
 * Po wypisaniu JSON zawsze konczymy exit 0 — przy failClosed: true niezerowy kod
 * ukrywa payload (Cursor traktuje to jak awarie hooka).
 */
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const CLAUDE = "claude";
const CURSOR = "cursor";

const argv = process.argv.slice(2);
const scriptName = argv.shift();

// --to <format> jest dla adaptera; reszta argumentow leci do skryptu polityki.
let target = CLAUDE;
const scriptArgs = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--to") {
    target = String(argv[++i] || CLAUDE).toLowerCase();
  } else if (argv[i].startsWith("--to=")) {
    target = argv[i].slice("--to=".length).toLowerCase();
  } else {
    scriptArgs.push(argv[i]);
  }
}

function render(decision, reason) {
  if (target === CURSOR) {
    if (decision === "allow") {
      return '{ "permission": "allow" }';
    }
    const label = decision === "deny" ? "Zablokowano" : "Potwierdz";
    return JSON.stringify({
      permission: decision,
      user_message: `${label}: ${reason}`,
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

// Awaria samego adaptera (brak pliku polityki, brak basha) — fail-closed.
const emitDeny = (message) => emitAndExit("deny", `invoke-hook: ${String(message)}`);

function findBash() {
  if (process.platform !== "win32") {
    return "bash";
  }
  const candidates = [
    path.join(process.env["ProgramFiles"] || "C:\\Program Files", "Git", "bin", "bash.exe"),
    path.join(process.env["ProgramFiles"] || "C:\\Program Files", "Git", "usr", "bin", "bash.exe"),
    path.join(process.env["LocalAppData"] || "", "Programs", "Git", "bin", "bash.exe"),
  ];
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "bash";
}

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

// Payload jest juz tutaj sparsowany, wiec podajemy gotowa komende w GUARD_COMMAND.
// Bez tego kazdy skrypt polityki musialby sam wystartowac interpreter, zeby dobrac
// sie do JSON-a — na Windowsie z shimem pyenv to kilka sekund na wywolanie.
let guardCommand = "";
try {
  const payload = JSON.parse(stdin || "{}");
  guardCommand = payload.command || (payload.tool_input || {}).command || "";
} catch {
  guardCommand = "";
}

const bash = findBash();
const hookForBash = hookPath.replace(/\\/g, "/");
const result = spawnSync(bash, ["--noprofile", "--norc", hookForBash, ...scriptArgs], {
  input: stdin,
  encoding: "utf8",
  windowsHide: true,
  shell: false,
  env: { ...process.env, GUARD_COMMAND: guardCommand },
});

if (result.error) {
  emitDeny(result.error.message || "nie mozna uruchomic bash");
}

const out = (result.stdout || "").trim();
if (!out) {
  const err = (result.stderr || "").trim().slice(0, 160) || "pusty stdout";
  emitDeny(err);
}

// Klient o kontrakcie Claude dostaje wyjscie polityki bez zmian.
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
