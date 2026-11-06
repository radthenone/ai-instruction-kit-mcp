#!/usr/bin/env node
/**
 * Guard: subagent nie woła narzędzi zdalnej sesji (PreToolUse: mcp__claude-code-remote__*).
 *
 * Noc `/night-run` stanęła na `confirm_repository_trust`: dialog do człowieka bez limitu
 * czasu, mimo jawnego zakazu w prompcie (#403). Sesje `remote-control` dopuszczają bez
 * pytania tylko narzędzia odczytu, więc reszta tej przestrzeni kończy się dialogiem,
 * a `archive_session` niszczy sesję. Subagent kita nie potrzebuje żadnego z nich.
 * Model szukał tam `SubagentHandback` (`mcp__claude-code-remote__SubagentHandback`),
 * więc powód odmowy wskazuje właściwe narzędzie.
 *
 * Subagenta poznajemy po `agent_id`. `agent_type` nie wystarcza: ma go też sesja główna
 * uruchomiona z `--agent`. Sesja główna (orkiestrator) zachowuje te narzędzia.
 * Działa na każdym Hoście, bo problem nie zależy od zasobów maszyny.
 *
 * Polityka zna tylko deny albo brak decyzji (ADR 0006). Bez jawnego `allow`, które
 * zatwierdzałoby narzędzie z pominięciem pytania o zgodę.
 *
 * Kontrakt: Claude Code. Inni klienci nie mają tej przestrzeni narzędzi.
 */
import { readFileSync } from "node:fs";

const REMOTE_TOOL = /^mcp__claude-code-remote__/;

const deny = (reason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: `subagent-remote-guard: ${reason}`,
      },
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
  deny("nieczytelny payload hooka");
}

if (payload.agent_id && REMOTE_TOOL.test(String(payload.tool_name || ""))) {
  deny("narzędzia zdalnej sesji są niedostępne dla subagenta — raport końcowy oddaj narzędziem `SubagentHandback`, bez prefiksu `mcp__`");
}
