#!/usr/bin/env node
/**
 * Guard: czy rtk jest skonfigurowane (SessionStart: startup|resume, tylko Claude Code).
 *
 * Sprawdza dwie rzeczy: `rtk --version` w PATH i wpis `rtk hook claude` w
 * ~/.claude/settings.json. Brak ktorejkolwiek → wypisuje modelowi instrukcje
 * dla uzytkownika. Nic wiecej: kit NIE pisze do ~/.claude i NIE odpala `rtk init`
 * — globalna instalacja to decyzja uzytkownika, rtk ma na to wlasny instalator.
 *
 * Wszystko ok → cisza (brak outputu, brak kontekstu).
 * Testy podaja GUARD_HOME (katalog domowy) i GUARD_RTK_BIN (nazwa binarki).
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const home = process.env.GUARD_HOME || process.env.HOME || process.env.USERPROFILE || homedir();
const rtk = process.env.GUARD_RTK_BIN || "rtk";

let hasBinary = false;
try {
  execFileSync(rtk, ["--version"], {
    stdio: "ignore",
    timeout: 5000,
    windowsHide: true,
    shell: process.platform === "win32",
  });
  hasBinary = true;
} catch {
  hasBinary = false;
}

let hasHook = false;
const settings = join(home, ".claude", "settings.json");
if (existsSync(settings)) {
  try {
    hasHook = readFileSync(settings, "utf8").includes("rtk hook claude");
  } catch {
    hasHook = false;
  }
}

if (hasBinary && hasHook) process.exit(0);

const missing = [];
if (!hasBinary) missing.push("binarka `rtk` nie jest w PATH (instalacja: https://github.com/rtk-ai/rtk)");
if (!hasHook) missing.push("brak hooka `rtk hook claude` w ~/.claude/settings.json");

const context =
  "rtk-check: rtk nie jest skonfigurowane — " +
  missing.join("; ") +
  ". Popros uzytkownika, zeby uruchomil `rtk init -g --auto-patch` (kit tego nie robi sam).";

process.stdout.write(
  JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: context } }) + "\n"
);
