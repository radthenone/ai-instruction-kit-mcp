#!/usr/bin/env node
/**
 * Guard: na Windows agent uzywa Git Basha, nie PowerShella (PreToolUse: Bash).
 *
 * Deny, gdy komenda z narzedzia Bash odpala `pwsh`, `powershell`, `powershell.exe`,
 * `cmd`, `cmd.exe` — jako pierwszy token albo po separatorze (`;`, `&&`, `||`, `|`).
 * Bez wyjatku na `-File`: skrypt .ps1 tez ma isc przez Git Basha albo wcale.
 *
 * Tylko win32. Na innych platformach zawsze allow — tam pwsh to swiadomy wybor,
 * nie domyslna powloka, i nie ma czego pilnowac.
 *
 * Narzedzie `PowerShell` (osobne od Bash) NIE jest blokowane — decyzja z #60.
 * Model po odmowie moze siegnac po nie wprost; uzytkownik to akceptuje.
 *
 * Kontrakt: Claude Code. Wejscie: `.tool_input.command` albo `.command`.
 * Testy podaja GUARD_PLATFORM, zeby sprawdzic polityke na kazdym OS.
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

// Token komendy: na poczatku albo po separatorze shella, opcjonalnie ze sciezka
// (`/c/Program Files/PowerShell/7/pwsh.exe`) i z rozszerzeniem .exe.
const SHELLS = /(^|[;&|(]\s*|\s(?:&&|\|\||;|\|)\s*)(?:"[^"]*[\\/])?(?:(?:[^\s"]|\\ )*[\\/])?(pwsh|powershell|cmd)(\.exe)?"?(\s|$)/i;

if (SHELLS.test(cmd)) {
  emit("deny", "bash-guard: na Windows uzywaj Git Basha — pwsh/powershell/cmd z narzedzia Bash sa zablokowane");
}

emit("allow", "bash-guard: ok");
