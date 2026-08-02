#!/usr/bin/env node
/**
 * Cross-platform Cursor hook invoker.
 * Windows: Git Bash with --noprofile --norc (no --login -i / leftover consoles).
 * Linux/macOS: system bash --noprofile --norc.
 * Usage: node .cursor/hooks/invoke-hook.js <hook-script.sh>
 */
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

function emitDeny(message) {
  const safe = String(message).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  process.stdout.write(
    `{"permission":"deny","user_message":"Hook: ${safe}","agent_message":"invoke-hook: ${safe}"}`
  );
  process.exit(1);
}

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

const scriptName = process.argv[2];
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

const bash = findBash();
const hookForBash = hookPath.replace(/\\/g, "/");
const result = spawnSync(bash, ["--noprofile", "--norc", hookForBash], {
  input: stdin,
  encoding: "utf8",
  windowsHide: true,
  shell: false,
});

if (result.error) {
  emitDeny(result.error.message || "nie można uruchomić bash");
}

const out = (result.stdout || "").trim();
if (!out) {
  const err = (result.stderr || "").trim().slice(0, 160) || "pusty stdout";
  emitDeny(err);
}

process.stdout.write(out);
process.exit(result.status == null ? 1 : result.status);
