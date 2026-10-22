#!/usr/bin/env node
/**
 * Guard: sekrety i pliki generowane (PreToolUse: Read|Edit|Write|MultiEdit|NotebookEdit|Bash).
 *
 * Sekrety — deny na odczyt i zapis (agent nie wciąga ich do kontekstu i nie nadpisuje):
 *   .env, .env.* (poza .env.example / .env.sample / .env.template)
 *   *.pem *.key *.p12 *.pfx
 *   id_rsa* id_ed25519* id_ecdsa*
 *   .netrc  credentials.json
 *   .git/objects/  .git/refs/  .git/hooks/   (HEAD i config zostają czytelne)
 *
 * Bash — deny tylko oczywisty odczyt: komenda czytająca + argument będący ścieżką
 * sekretu (cat, head, tail, less, more, bat, grep, rg, sed, awk, xxd, base64,
 * strings, source/. oraz `rtk read` / `rtk grep`). Segmenty dzielimy po `;`, `&&`,
 * `||`, `|` i podstawieniach `$(...)`, zdejmujemy prefiksy sudo/env/rtk (z `-u x`,
 * `proxy`, `VAR=1`; oraz powłoki bash/sh/zsh z `-c`), bo RTK przepisuje `cat .env`
 * na `rtk read .env`. Pierwszy argument grep/rg/sed/awk to wzorzec, nie plik; cel
 * przekierowania (`> .env`) to zapis, nie odczyt. Każda inna komenda ze ścieżką
 * sekretu przechodzi: `cp .env.example .env`, `ls -la .env`, `rm .env`,
 * `git check-ignore .env`.
 *
 * ponytail: parser jest tekstowy i celowo płaski — nie złapie `python -c
 * "open('.env')"`, `grep -r KEY .` ani zapisu przez Bash (`echo X > .env`,
 * `tee .env`), wrapperów time/command/exec/nice ani globów. To granica, nie bug:
 * guard blokuje oczywiste odczyty, nie udaje piaskownicy. Upgrade, gdy pojawi się realny omijak: wspólny
 * parser shella z server-guard.mjs (AST zamiast split/regex), nie doklejanie
 * kolejnych wzorców.
 *
 * Lockfile — deny tylko na zapis; odczyt wolny, a `npm install` / `uv sync` przez
 * Bash regenerują je legalnie:
 *   package-lock.json pnpm-lock.yaml yarn.lock bun.lockb bun.lock
 *   uv.lock poetry.lock Pipfile.lock Cargo.lock
 *
 * Zero `ask` — ADR 0006. Reszta plików przechodzi; zapisy poza repo pilnuje
 * natywna permission klienta (cwd + additionalDirectories), nie ten Guard.
 *
 * Kontrakt: Claude Code (`tool_name`, `tool_input.file_path|notebook_path`,
 * `tool_input.command`). Cursor przez invoke-hook.js --to cursor --tool Read|Write:
 * adapter dopisuje `tool_name`, bo `beforeReadFile` podaje tylko `file_path` +
 * `content`, a `beforeShellExecution` tylko `command`.
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
if (!payload || typeof payload !== "object") payload = {};

const toolInput = payload.tool_input || {};
const command = String(toolInput.command || payload.command || "");
const file = String(toolInput.file_path || toolInput.notebook_path || payload.file_path || "");

const ENV_ALLOWED = new Set([".env.example", ".env.sample", ".env.template"]);
const SECRET_NAMES = new Set([".netrc", "credentials.json"]);
const SECRET_EXT = /\.(pem|key|p12|pfx)$/i;
const SSH_KEY = /^id_(rsa|ed25519|ecdsa)/i;
const GIT_INTERNAL = /(^|\/)\.git\/(objects|refs|hooks)(\/|$)/;

const isSecretPath = (path) => {
  const posix = String(path).replace(/\\/g, "/");
  const lower = basename(posix).toLowerCase();
  return (
    (lower === ".env" || (lower.startsWith(".env.") && !ENV_ALLOWED.has(lower))) ||
    SECRET_NAMES.has(lower) ||
    SECRET_EXT.test(lower) ||
    SSH_KEY.test(lower) ||
    GIT_INTERNAL.test(posix)
  );
};

// Bash: komenda czytająca + argument-sekret. Lista krótka i świadomie tekstowa —
// patrz granica w nagłówku.
const READ_COMMANDS = new Set([
  "cat", "head", "tail", "less", "more", "bat", "grep", "rg", "sed", "awk",
  "xxd", "base64", "strings", "source", ".",
]);
// Pierwszy argument pozycyjny to wzorzec / skrypt, nie plik (chyba że podano -e / -f).
const PATTERN_FIRST = new Set(["grep", "rg", "sed", "awk"]);
// Powłoka z `-c` (`bash -lc "cat .env"`) to też prefiks, nie komenda czytająca.
const SHELL_PREFIXES = new Set(["sudo", "env", "rtk", "bash", "sh", "zsh"]);
// Opcje sudo/env z wartością w osobnym tokenie (`sudo -u root cat .env`).
const PREFIX_VALUE_OPTS = new Set(["-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-T", "-U", "-R", "-S"]);
// `rtk proxy cat .env` uruchamia komendę bez filtra — to też prefiks.
const RTK_WRAPPERS = new Set(["proxy", "err", "test", "summary"]);
const REDIRECT = /^\d*>>?$|^&>>?$/;

// Zdejmij cudzysłowy i domknięcia podstawień: `"certs/server.pem"`.
const clean = (token) => token.replace(/^[("'`]+|[)"'`,]+$/g, "");

function shellSecretRead(command) {
  // Podstawienia `$(...)` / `` `...` `` / `(...)` to osobne segmenty; `>` odklejamy od tokenu.
  const flat = command.replace(/\$\(|[`()]/g, ";").replace(/>/g, " > ");
  for (const segment of flat.split(/&&|\|\||[;|\n]/)) {
    const tokens = segment.trim().split(/\s+/).filter(Boolean);
    let i = 0;
    let rtk = false;
    // Prefiksy (`sudo cat`, `env cat`, `rtk read`) plus ich opcje i `VAR=x`.
    while (i < tokens.length) {
      const token = clean(tokens[i]);
      if (SHELL_PREFIXES.has(token)) {
        if (token === "rtk") rtk = true;
        i += 1;
        continue;
      }
      if (i > 0 && SHELL_PREFIXES.has(clean(tokens[i - 1])) && PREFIX_VALUE_OPTS.has(token)) {
        i += 2;
        continue;
      }
      if (
        (i > 0 && token.startsWith("-")) ||
        /^[A-Za-z_][A-Za-z0-9_]*=/.test(token) ||
        (rtk && i > 0 && clean(tokens[i - 1]) === "rtk" && RTK_WRAPPERS.has(token))
      ) {
        i += 1;
        continue;
      }
      break;
    }
    const name = clean(tokens[i] || "");
    // `rtk read` / `rtk grep` to forma po przepisaniu — `read` liczy się tylko z rtk.
    if (!READ_COMMANDS.has(name) && !(rtk && name === "read")) continue;
    let needPattern = PATTERN_FIRST.has(name);
    const args = tokens.slice(i + 1);
    for (let j = 0; j < args.length; j += 1) {
      const token = args[j];
      if (REDIRECT.test(token)) {
        j += 1; // cel zapisu (`> .env`), nie odczyt
        continue;
      }
      if (token.startsWith("-")) {
        if (token === "-e" || token === "--regexp") j += 1; // wartość = wzorzec
        if (/^(-[ef]|--regexp|--file)$/.test(token)) needPattern = false;
        continue;
      }
      if (needPattern) {
        needPattern = false;
        continue;
      }
      const path = clean(token);
      if (isSecretPath(path)) return path;
    }
  }
  return "";
}

// Cursor `beforeShellExecution` nie ma tool_name — sam `command` wystarcza. Brak trafienia
// nie kończy sprawy: adapter Copilota daje string jako `command` i `file_path` naraz.
if (command.trim()) {
  const hit = shellSecretRead(command);
  if (hit) {
    emit("deny", `sensitive-files-guard: ${hit} to sekret — nie czytaj go przez Bash; poproś użytkownika`);
  }
}

if (!file) emit("allow", "sensitive-files-guard: brak ścieżki");

// Read = odczyt. Cursor `beforeReadFile` nie ma tool_name, ale niesie `content`.
const toolName = String(payload.tool_name || "");
const isRead = toolName === "Read" || (!toolName && "content" in payload);

const name = basename(file.replace(/\\/g, "/"));

if (isSecretPath(file)) {
  emit("deny", `sensitive-files-guard: ${name} to sekret — ani odczyt, ani zapis; poproś użytkownika`);
}

const LOCKFILES = new Set([
  "package-lock.json",
  "pnpm-lock.yaml",
  "yarn.lock",
  "bun.lockb",
  "bun.lock",
  "uv.lock",
  "poetry.lock",
  "pipfile.lock",
  "cargo.lock",
]);

if (!isRead && LOCKFILES.has(name.toLowerCase())) {
  emit("deny", `sensitive-files-guard: ${name} jest generowany — nie edytuj ręcznie, uruchom menedżer pakietów`);
}

emit("allow", "sensitive-files-guard: ok");
