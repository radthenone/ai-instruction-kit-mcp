#!/usr/bin/env node
/**
 * Guard: na Windows agent używa Git Basha, nie PowerShella (PreToolUse: Bash).
 *
 * Deny, gdy komenda z narzędzia Bash odpala `pwsh`, `powershell`, `powershell.exe`,
 * `cmd`, `cmd.exe` — jako pierwszy token albo po separatorze (`;`, `&&`, `||`, `|`).
 * Bez wyjątku na `-File`: skrypt .ps1 też ma iść przez Git Basha albo wcale.
 *
 * Tylko win32. Na innych platformach zawsze allow — tam pwsh to świadomy wybór,
 * nie domyślna powłoka, i nie ma czego pilnować.
 *
 * Narzędzie `PowerShell` (osobne od Bash) NIE jest blokowane — decyzja z #60.
 * Model po odmowie może sięgnąć po nie wprost; użytkownik to akceptuje.
 *
 * Kontrakt: Claude Code. Wejście: `.tool_input.command` albo `.command`.
 * Testy podają GUARD_PLATFORM, żeby sprawdzić politykę na każdym OS.
 */
import { readFileSync } from "node:fs";

const emit = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};

const platform = process.env.GUARD_PLATFORM || process.platform;
if (platform !== "win32") emit("allow", "bash-guard: nie Windows");

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
  emit("deny", "bash-guard: nieczytelny payload hooka");
}

const command = String(payload.command || (payload.tool_input || {}).command || "");
const cmd = command.replace(/[\r\n\t]+/g, " ").trim();

// Token komendy: na początku albo po separatorze shella, opcjonalnie ze ścieżką
// (`/c/Program Files/PowerShell/7/pwsh.exe`) i z rozszerzeniem .exe.
const SHELLS = /(^|[;&|(]\s*|\s(?:&&|\|\||;|\|)\s*)(?:"[^"]*[\\/])?(?:(?:[^\s"]|\\ )*[\\/])?(pwsh|powershell|cmd)(\.exe)?"?(\s|$)/i;

if (SHELLS.test(cmd)) {
  emit("deny", "bash-guard: na Windows używaj Git Basha — pwsh/powershell/cmd z narzędzia Bash są zablokowane");
}

emit("allow", "bash-guard: ok");
