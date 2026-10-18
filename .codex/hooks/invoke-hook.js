#!/usr/bin/env node
/**
 * Adapter kontraktu hooka dla Cursora, OpenCode i Codexa.
 *
 * Guardy w templates/shared/guards/*.mjs mówią jednym dialektem — kontraktem
 * Claude Code (`hookSpecificOutput.permissionDecision`). Claude Code woła je
 * wprost (`node .claude/hooks/git-guard.mjs`). Ten plik jest jedynym miejscem,
 * które wie, że Cursor ma własny kształt wejścia i wyjścia:
 *
 *   node .cursor/hooks/invoke-hook.js git-guard.mjs --to cursor
 *   node .cursor/hooks/invoke-hook.js sensitive-files-guard.mjs --to cursor --tool Read
 *
 * Wejście: Cursor `beforeShellExecution` daje `.command`, `beforeReadFile` daje
 * `.file_path` + `.content` bez nazwy narzędzia — `--tool` dopisuje `tool_name`,
 * żeby Guard odróżnił odczyt od zapisu. `preToolUse` już niesie `tool_name`.
 *
 * OpenCode (`--to opencode`, woła go plugin `.opencode/plugins/kit-guards.js`):
 * wejście `{ tool, input }` z `tool.execute.before` (`input.command`, `input.filePath`),
 * wyjście `{ decision, reason }` — plugin przy deny rzuca błąd z powodem dla modelu.
 *
 * Codex (`--to codex`, `.codex/hooks.json` PreToolUse): wyjście jak Claude Code.
 * Wejście: narzędzie powłoki (`shell` / `local_shell` / `exec_command` / `Bash`) niesie
 * `command` jako string albo argv — sklejamy do stringa jako `Bash`. `apply_patch` nie ma
 * `file_path`: ścieżki z nagłówków `*** Add|Update|Delete File:` / `*** Move to:` idą
 * przez guard po kolei (pierwszy deny wygrywa); patch bez ścieżek = deny.
 *
 * Copilot (`--to copilot`, `.github/hooks/kit-guards.json` PreToolUse): plik hooków używa
 * PascalCase `PreToolUse` (ten sam kształt czyta VS Code Local i Copilot CLI), więc payload
 * przychodzi jak w Claude Code (`tool_name` + `tool_input`). Różnice: nazwa narzędzia bywa
 * runtime'owa (`bash` / `powershell` / `view` / `create` / `edit` / `grep` / `glob`), a
 * `tool_input` potrafi przyjść jako string JSON oraz ze ścieżką w `filePath`/`path`.
 * Adapter sprowadza to do kształtu, który rozumieją guardy — inaczej guard nie zobaczyłby
 * `command`/`file_path` i przepuściłby komendę (fail-open). Wyjście zostaje w kontrakcie
 * Claude Code: przy PascalCase `PreToolUse` obie powierzchnie czytają
 * `hookSpecificOutput.permissionDecision`, a `deny` blokuje wywołanie.
 *
 * Wyjście Cursora: `{ permission, user_message, agent_message }`. Po wypisaniu JSON zawsze
 * exit 0 — przy failClosed: true niezerowy kod ukrywa payload (Cursor traktuje to
 * jak awarię hooka). Awaria adaptera = deny (fail-closed).
 */
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const CLAUDE = "claude";
const CURSOR = "cursor";
const OPENCODE = "opencode";
const CODEX = "codex";
const COPILOT = "copilot";

// Copilot: nazwa runtime → nazwa Claude, którą operują guardy. Tabela z GitHub
// Copilot hooks reference (bash|powershell → Bash, view → Read, create → Write,
// edit|str_replace_editor|apply_patch → Edit, grep|rg → Grep, glob → Glob).
const COPILOT_TOOLS = {
  bash: "Bash",
  powershell: "Bash",
  shell: "Bash",
  view: "Read",
  read: "Read",
  create: "Write",
  write: "Write",
  edit: "Edit",
  str_replace_editor: "Edit",
  apply_patch: "Edit",
  grep: "Grep",
  rg: "Grep",
  glob: "Glob",
  // VS Code agent mode (wbudowane narzędzia, `filePath` w tool_input).
  run_in_terminal: "Bash",
  read_file: "Read",
  create_file: "Write",
  replace_string_in_file: "Edit",
  multi_replace_string_in_file: "Edit",
  insert_edit_into_file: "Edit",
  edit_notebook_file: "Edit",
};

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
  if (target === OPENCODE) {
    return JSON.stringify({ decision, reason });
  }
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

// OpenCode: `{ tool, input }` → kształt Claude Code. Nazwę narzędzia Claude podaje plugin
// w `--tool`; pole ścieżki to `path` (opencode 2.x) albo `filePath` (starsze). Brak pola,
// którego Guard potrzebuje, = deny — zmiana schematu narzędzi nie może przepuścić komendy.
if (target === OPENCODE) {
  let payload;
  try {
    payload = JSON.parse(stdin || "{}");
  } catch {
    emitDeny("nieczytelny payload opencode");
  }
  const input = payload.input || {};
  const name = toolName || String(payload.tool || "");
  // Narzędzia MCP (np. Playwright → server-guard) idą z wejściem bez zmian — guard
  // decyduje po samej nazwie narzędzia.
  const mcp = name.startsWith("mcp__");
  const toolInput = name === "Bash"
    ? { command: input.command }
    : mcp ? input : { file_path: input.path ?? input.filePath };
  if (!mcp && !Object.values(toolInput)[0]) {
    emitDeny(`brak ${name === "Bash" ? "command" : "path/filePath"} w wejściu narzędzia ${payload.tool || "?"}`);
  }
  stdin = JSON.stringify({ tool_name: name, tool_input: toolInput });
  toolName = "";
}

const runGuard = (input) => spawnSync(process.execPath, [hookPath, ...scriptArgs], {
  input,
  encoding: "utf8",
  windowsHide: true,
  shell: false,
});

// Codex: powłoka → `Bash` z komendą-stringiem; `apply_patch` → guard na każdej ścieżce.
if (target === CODEX) {
  let payload;
  try {
    payload = JSON.parse(stdin || "{}");
  } catch {
    emitDeny("nieczytelny payload codex");
  }
  const name = String(payload.tool_name || "");
  const input = payload.tool_input || {};
  if (["Bash", "shell", "local_shell", "exec_command"].includes(name)) {
    const raw = input.command ?? input.cmd;
    const command = Array.isArray(raw) ? raw.join(" ") : String(raw || "");
    if (!command) emitDeny(`brak command w wejściu narzędzia ${name}`);
    stdin = JSON.stringify({ ...payload, tool_name: "Bash", tool_input: { command } });
  } else if (name === "apply_patch") {
    const text = Object.values(input).filter((v) => typeof v === "string").join("\n")
      || (typeof payload.tool_input === "string" ? payload.tool_input : "");
    const paths = [...text.matchAll(/^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$/gm)]
      .map((m) => m[1].trim());
    if (!paths.length) emitDeny("apply_patch bez ścieżek plików w patchu");
    for (const file of paths) {
      const r = runGuard(JSON.stringify({ tool_name: "Write", tool_input: { file_path: file } }));
      let d;
      try {
        d = JSON.parse((r.stdout || "").trim()).hookSpecificOutput;
      } catch {
        emitDeny(`niepoprawne wyjście guarda dla ${file}`);
      }
      if (!d || d.permissionDecision !== "allow") {
        emitAndExit(d?.permissionDecision || "deny", d?.permissionDecisionReason || `brak decyzji dla ${file}`);
      }
    }
    emitAndExit("allow", `apply_patch: ${paths.length} plik(ów) bez zastrzeżeń`);
  }
}

// Copilot: nazwa runtime → Claude, `tool_input` string-JSON → obiekt, ścieżka `filePath`/
// `path` → `file_path`, `cmd`/`argv` → `command`. PascalCase `PreToolUse` daje snake_case
// `tool_name`/`tool_input`, camelCase `preToolUse` daje `toolName`/`toolArgs` — bierzemy oba.
if (target === COPILOT) {
  let payload;
  try {
    payload = JSON.parse(stdin || "{}");
  } catch {
    emitDeny("nieczytelny payload copilot");
  }
  let input = payload.tool_input ?? payload.toolArgs ?? {};
  if (typeof input === "string") {
    try {
      input = JSON.parse(input);
    } catch {
      // Nie-JSON (np. goła komenda/ścieżka) — guard ma z czego wybrać.
      input = { command: input, file_path: input };
    }
  }
  if (!input || typeof input !== "object") input = {};
  const sourceName = String(payload.tool_name || payload.toolName || "");
  const name = COPILOT_TOOLS[sourceName.toLowerCase()] || sourceName;
  const normalized = { ...input };
  if (name === "Bash" && normalized.command === undefined) {
    const raw = input.cmd ?? input.argv;
    if (raw !== undefined) normalized.command = Array.isArray(raw) ? raw.join(" ") : String(raw);
  }
  if (["Read", "Write", "Edit"].includes(name) && normalized.file_path === undefined) {
    const p = input.filePath ?? input.path ?? input.file;
    if (p !== undefined) normalized.file_path = p;
  }
  stdin = JSON.stringify({ ...payload, tool_name: name, tool_input: normalized });
}

// `--tool` uzupełnia payload Cursora o to, co Claude Code daje z natury.
if (toolName) {
  try {
    const payload = JSON.parse(stdin || "{}");
    if (!payload.tool_name) payload.tool_name = toolName;
    stdin = JSON.stringify(payload);
  } catch {
    // Nieczytelny payload przekazujemy dalej — Guard sam odpowie deny.
  }
}

const result = runGuard(stdin);

if (result.error) {
  emitDeny(result.error.message || "nie można uruchomić node");
}

const out = (result.stdout || "").trim();
let calledTool = "";
try {
  calledTool = String(JSON.parse(stdin || "{}").tool_name || "");
} catch {
  calledTool = "";
}
// Guard bez decyzji dla narzędzia MCP (np. server-guard poza VPS) = nie wtrąca się.
if (!out && calledTool.startsWith("mcp__") && target !== CURSOR && target !== OPENCODE) {
  process.exit(0);
}
if (!out && calledTool.startsWith("mcp__")) {
  emitAndExit("allow", "guard bez decyzji dla narzędzia MCP");
}
if (!out) {
  const err = (result.stderr || "").trim().slice(0, 160) || "pusty stdout";
  emitDeny(err);
}

if (target !== CURSOR && target !== OPENCODE) {
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
