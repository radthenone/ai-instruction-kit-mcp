#!/usr/bin/env node
/**
 * Guard: ciężkie komendy zasobowe na hostach VPS (PreToolUse: Bash).
 *
 * Aktywny TYLKO na słabym hoście serwerowym — na PC i w CI przepuszcza wszystko.
 * Decyzja zapada w momencie wywołania (runtime), bo `.claude/settings.json` i Profil
 * są commitowane i wspólne dla PC i VPS. Kolejność:
 *
 *   1. `server.guard: off` w Profilu (JSON obok guarda) → allow.
 *   2. `KIT_HOST_PROFILE` / `GUIDES_HOST_PROFILE` = `vps` / `local` → wymuszenie
 *      (tylko gdy heurystyka się myli; normalnie nieustawiane).
 *   3. Heurystyka 1:1 z `src/guides/host_profile.py` (Linux, nie CI, nie WSL,
 *      CPU ≤ 2, RAM ≤ 8 GB, swap 0, wirtualizacja albo brak desktopu) → aktywny.
 *   4. W pozostałych przypadkach → allow.
 *
 * Polityka zna tylko allow/deny (ADR 0006). Dopasowanie po tokenach od początku
 * segmentu — `allow` wygrywa z `deny`. Szczegóły tabeli: README „Server guard (VPS)”.
 *
 * Domyślna lista deny jest WBUDOWANA (fallback bez JSON-a) i RENDEROWANA do
 * `server-guard.json` przez `kit-ai reload` (lista kita + rozwinięte wrappery
 * `task` / `bun|npm|pnpm|yarn run` + sekcja `server:` z Profilu). Guard nie parsuje
 * YAML-a. Po zmianie Taskfile / `package.json` trzeba `kit-ai reload` — bez reloadu
 * guard działa na starej liście wrapperów.
 *
 * Testy determinują heurystykę przez env (parzystość z `detect_host_profile`):
 * `GUARD_PLATFORM`, `GUARD_CPU_COUNT`, `GUARD_MEM_BYTES`, `GUARD_SWAP_BYTES`,
 * `GUARD_VIRT`, `GUARD_HAS_DESKTOP` (1/0), `GUARD_IS_CI` (1/0), `GUARD_IS_WSL` (1/0).
 *
 * Kontrakt: Claude Code (`hookSpecificOutput.permissionDecision`). Cursor/OpenCode
 * przez `invoke-hook.js --to cursor|opencode`. Narzędzia Playwright MCP
 * (`mcp__plugin_playwright_*`, `mcp__playwright_*`) → deny, gdy guard aktywny.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { homedir, cpus, totalmem, platform as osPlatform } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

// Kopia `DEFAULTS` z `src/guides/server_guard.py` — fallback, gdy brak JSON-a.
// Wzorce: `^\s*…(?=\s|$)`, spacje `\s+`. Zmiana tutaj = zmiana tam (test parzystości).
const EMBEDDED_DEFAULTS = [
  {"id": "docker", "kind": "deny", "pattern": "^\\s*docker(?=\\s|$)", "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
  {"id": "docker-compose", "kind": "deny", "pattern": "^\\s*docker\\s+compose(?=\\s|$)", "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
  {"id": "docker-compose-bin", "kind": "deny", "pattern": "^\\s*docker-compose(?=\\s|$)", "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
  {"id": "podman", "kind": "deny", "pattern": "^\\s*podman(?=\\s|$)", "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
  {"id": "docker-ps", "kind": "allow", "pattern": "^\\s*(?:docker|podman)\\s+(?:ps|images|inspect|version|info)(?=\\s|$)", "reason": "odczyt stanu kontenerów"},
  {"id": "docker-logs", "kind": "allow", "pattern": "^\\s*(?:docker|podman)\\s+logs(?=\\s|$)(?!.*\\s(?:-[a-zA-Z]*f[a-zA-Z]*|--follow)(?=\\s|$))", "reason": "odczyt logów bez follow"},
  {"id": "docker-logs-follow", "kind": "deny", "pattern": "^\\s*(?:docker|podman)\\s+logs(?=\\s|$).*\\s(?:-[a-zA-Z]*f[a-zA-Z]*|--follow)(?=\\s|$)", "reason": "follow logów trzyma proces i strumień — użyj `docker logs` bez `-f`"},
  {"id": "docker-compose-config", "kind": "deny", "pattern": "^\\s*docker\\s+compose\\s+config(?=\\s|$)", "reason": "kontenery tylko w CI — na hoście działają cudze kontenery"},
  {"id": "docker-compose-ps", "kind": "allow", "pattern": "^\\s*(?:docker|podman)(?:\\s+|-)compose\\s+ps(?=\\s|$)", "reason": "odczyt stanu kontenerów"},
  {"id": "uv-sync", "kind": "deny", "pattern": "^\\s*uv\\s+(sync|add|remove|lock)(?=\\s|$)", "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
  {"id": "uv-pip-install", "kind": "deny", "pattern": "^\\s*uv\\s+pip\\s+install(?=\\s|$)", "reason": "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI"},
  {"id": "pip-install", "kind": "deny", "pattern": "^\\s*pip3?\\s+install(?=\\s|$)", "reason": "instalacja kompiluje zależności natywne — zależności zmieniają się na PC albo w CI"},
  {"id": "uv-run", "kind": "deny", "pattern": "^\\s*uv\\s+run(?=\\s|$)(?!.*--no-sync)", "reason": "`uv run` bez `--no-sync` synchronizuje i kompiluje — użyj `uv run --no-sync` albo `UV_NO_SYNC=1`"},
  {"id": "uv-run-no-sync", "kind": "allow", "pattern": "^\\s*uv\\s+run(?=\\s|$).*?--no-sync", "reason": "uruchomienie bez synchronizacji"},
  {"id": "uvx", "kind": "allow", "pattern": "^\\s*uvx(?=\\s|$)", "reason": "jednorazowe narzędzia bez instalacji do projektu"},
  {"id": "bun-pkg", "kind": "deny", "pattern": "^\\s*bun\\s+(install|add|remove)(?=\\s|$)", "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
  {"id": "npm-pkg", "kind": "deny", "pattern": "^\\s*npm\\s+(install|i|ci)(?=\\s|$)", "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
  {"id": "pnpm-pkg", "kind": "deny", "pattern": "^\\s*pnpm\\s+(install|i|add)(?=\\s|$)", "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
  {"id": "yarn-pkg", "kind": "deny", "pattern": "^\\s*yarn\\s+(install|add)(?=\\s|$)", "reason": "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI"},
  {"id": "next-build", "kind": "deny", "pattern": "^\\s*next\\s+build(?=\\s|$)", "reason": "build produkcyjny tylko w CI — na VPS `tsc --noEmit`"},
  {"id": "expo-build", "kind": "deny", "pattern": "^\\s*expo\\s+(prebuild|export)(?=\\s|$)", "reason": "build produkcyjny tylko w CI"},
  {"id": "eas-build", "kind": "deny", "pattern": "^\\s*eas\\s+build(?=\\s|$)", "reason": "build produkcyjny tylko w CI"},
  {"id": "vite-build", "kind": "deny", "pattern": "^\\s*vite\\s+build(?=\\s|$)", "reason": "build produkcyjny tylko w CI"},
  {"id": "turbo-build", "kind": "deny", "pattern": "^\\s*turbo(?:\\s+run)?(?:\\s+[^-\\s]\\S*)*?\\s+build(?=\\s|$)", "reason": "build produkcyjny tylko w CI — na VPS `turbo run lint` / `typecheck`"},
  {"id": "turbo-lint", "kind": "allow", "pattern": "^\\s*turbo\\s+run(?:\\s+(?:lint|typecheck))+(?:\\s+-\\S+(?:\\s+[^-\\s]\\S*)?)*\\s*$", "reason": "lekkie bramki na VPS"},
  {"id": "playwright", "kind": "deny", "pattern": "^\\s*(npx\\s+|bunx\\s+|yarn\\s+dlx\\s+|pnpm\\s+dlx\\s+)?playwright(?=\\s|$)", "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
  {"id": "cypress", "kind": "deny", "pattern": "^\\s*(npx\\s+|bunx\\s+)?cypress(?=\\s|$)", "reason": "przeglądarka to setki MB na instancję — e2e tylko w CI"},
  {"id": "maestro", "kind": "deny", "pattern": "^\\s*maestro(?=\\s|$)", "reason": "testy mobilne tylko w CI"},
  {"id": "pytest-xdist", "kind": "deny", "pattern": "^\\s*pytest(?=\\s|$).*\\s(?:-n|--numprocesses)(?=[\\s=\\d]|$)", "reason": "xdist mnoży procesy na słabym CPU — użyj `pytest` bez `-n`"},
];

// `mcp__plugin_playwright_…`/`mcp__playwright__…` (Claude) i `mcp_playwright_…` (VS Code).
const PLAYWRIGHT_TOOL = /^mcp_+(plugin_)?playwright/;

// Test parzystości porównuje wbudowaną kopię z `DEFAULTS` w Pythonie.
if (process.env.SERVER_GUARD_DUMP_DEFAULTS === "1") {
  process.stdout.write(JSON.stringify(EMBEDDED_DEFAULTS) + "\n");
  process.exit(0);
}

const emit = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};
const deny = (reason) => emit("deny", `server-guard: ${reason}`);

// --- Konfiguracja (JSON obok guarda) -----------------------------------------
let config = null;
try {
  config = JSON.parse(readFileSync(join(HERE, "server-guard.json"), "utf8"));
} catch {
  config = null;
}

function literalPattern(cmd) {
  return "^\\s*" + String(cmd).trim().split(/\s+/).map(escapeRegExp).join("\\s+") + "(?=\\s|$)";
}
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Kolejność jak w renderze: wrappery (z łańcuchem) przed regułami kita.
const defaults = Array.isArray(config?.defaults) && config.defaults.length ? config.defaults : EMBEDDED_DEFAULTS;
const rules = [];
for (const w of Array.isArray(config?.wrappers) ? config.wrappers : []) {
  if (w && w.pattern) rules.push({ id: "wrapper", kind: "deny", pattern: w.pattern, reason: w.reason || "ciężki wrapper (Taskfile/package.json)", chain: w.chain, rule: w.rule });
}
rules.push(...defaults);
for (const item of config?.project_deny || []) {
  rules.push({ id: `project-deny:${item}`, kind: "deny", pattern: literalPattern(item), reason: `dodatkowy deny projektu (\`server.deny\`: ${item})` });
}
for (const item of config?.project_allow || []) {
  rules.push({ id: `project-allow:${item}`, kind: "allow", pattern: literalPattern(item), reason: `wyjątek projektu (\`server.allow\`: ${item})` });
}

// --- Aktywacja (1:1 z `src/guides/host_profile.py`) ----------------------------
function normalizeOverride(value) {
  const key = String(value || "").trim().toLowerCase();
  return key === "vps" || key === "local" ? key : null;
}

function readMeminfo() {
  if (process.env.GUARD_MEM_BYTES !== undefined || process.env.GUARD_SWAP_BYTES !== undefined) {
    const mem = process.env.GUARD_MEM_BYTES === "" ? null : Number(process.env.GUARD_MEM_BYTES);
    const swap = process.env.GUARD_SWAP_BYTES === "" ? null : Number(process.env.GUARD_SWAP_BYTES);
    return [Number.isFinite(mem) ? mem : null, Number.isFinite(swap) ? swap : null];
  }
  try {
    let mem = null;
    let swap = null;
    for (const line of readFileSync("/proc/meminfo", "utf8").split("\n")) {
      const m = line.match(/^(MemTotal|SwapTotal):\s+(\d+)/);
      if (m) {
        if (m[1] === "MemTotal") mem = Number(m[2]) * 1024;
        else swap = Number(m[2]) * 1024;
      }
    }
    return [mem, swap];
  } catch {
    return [null, null];
  }
}

function detectVirt() {
  if (process.env.GUARD_VIRT !== undefined) return String(process.env.GUARD_VIRT).trim().toLowerCase();
  try {
    return execFileSync("systemd-detect-virt", { encoding: "utf8", timeout: 5000 }).trim().toLowerCase();
  } catch (err) {
    // Na bare metal komenda wypisuje `none` z kodem ≠ 0.
    return String(err?.stdout || "").trim().toLowerCase();
  }
}

const filled = (env, names) => names.some((v) => String(env[v] || "").trim() !== "");

function isCI(env) {
  if (process.env.GUARD_IS_CI !== undefined) return process.env.GUARD_IS_CI === "1";
  if (["1", "true", "yes"].includes(String(env.CI || "").trim().toLowerCase())) return true;
  return filled(env, ["GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "BUILDKITE", "CIRCLECI", "TRAVIS", "TF_BUILD"]);
}

function isWSL(env) {
  if (process.env.GUARD_IS_WSL !== undefined) return process.env.GUARD_IS_WSL === "1";
  if (filled(env, ["WSL_DISTRO_NAME", "WSL_INTEROP"])) return true;
  try {
    const version = readFileSync("/proc/version", "utf8").toLowerCase();
    return version.includes("microsoft") || version.includes("wsl");
  } catch {
    return false;
  }
}

function isActive() {
  if (config?.guard === "off") return false;
  const env = process.env;
  const override = normalizeOverride(env.KIT_HOST_PROFILE) || normalizeOverride(env.GUIDES_HOST_PROFILE);
  if (override) return override === "vps";

  const plat = env.GUARD_PLATFORM || osPlatform();
  if (!String(plat).startsWith("linux")) return false;
  if (isCI(env) || isWSL(env)) return false;
  // Codespaces / devcontainer: mały kontener bez desktopu, ale to stacja deweloperska.
  if (filled(env, ["CODESPACES", "REMOTE_CONTAINERS"])) return false;

  const cpu = env.GUARD_CPU_COUNT !== undefined ? Number(env.GUARD_CPU_COUNT) : cpus().length;
  const [mem, swap] = readMeminfo();
  if (!Number.isFinite(cpu) || mem === null || swap === null) return false;
  if (!(cpu <= 2 && mem <= 8 * 1024 ** 3 && swap === 0)) return false;

  const virt = detectVirt();
  const virtualized = Boolean(virt) && virt !== "none" && virt !== "unknown";
  const desktop = env.GUARD_HAS_DESKTOP !== undefined
    ? env.GUARD_HAS_DESKTOP === "1"
    : filled(env, ["DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION"]);
  return virtualized || !desktop;
}

// --- Dopasowanie komendy (lustro `src/guides/server_guard.py`) -------------------
const HEREDOC = /<<(?!<)(-?)\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\2/y;
const SHELL_C = /(?:^|\s)(?:\S*\/)?(?:bash|sh|zsh|dash)\s+(?:-[a-zA-Z]+\s+)*-[a-zA-Z]*c[a-zA-Z]*\s+(?:"([^"]*)"|'([^']*)'|(\S+))/g;
const SUBSHELL = /\$\(\s*(.*?)\s*\)/g;
const BACKTICK = /`([^`]*)`/g;
const ASSIGN = /^\s*([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|'[^']*'|\S*)\s+/;
const LOOKUP_FLAG = /^\s*(?:\S*\/)?command\s+-[a-zA-Z]*[vV]/;
const PREFIXES = [
  [/^\s*(?:\S*\/)?sudo\b\s*(?:(?:-[ugpCDhrtU]\s+\S+|-\S+)\s+)*/, ""],
  [/^\s*(?:\S*\/)?env(?:\s+(?:-[uC]\s+\S+|-\S+))*\s+/, ""],
  [/^\s*(?:\S*\/)?(?:nice|ionice|nohup|time|command|exec|xargs|eval)\b\s*(?:-\S+(?:\s+\d+)?\s+)*/, ""],
  [/^\s*(?:\S*\/)?timeout(?:\s+(?:-[sk]\s+\S+|-\S+))*\s+[\d.]+[smhd]?\s+/, ""],
  [/^\s*["']+/, ""],
  [/^(\s*)(?:[^\s/'"]*\/)+(?=\S)/, "$1"],
];
const UV_GLOBAL_ARG = new Set(["--directory", "--project", "--config-file", "--cache-dir", "--python", "-p"]);
const UV_RUN_ARG = new Set(["--with", "--with-requirements", "--python", "-p", "--package", "--env-file", "--group", "--extra", "--directory", "--project", "--index", "--index-url"]);
const JS_PM_ARG = new Set(["--filter", "-F", "--cwd", "-C", "--workspace", "--prefix", "--dir"]);
const NPX_ARG = new Set(["-p", "--package"]);
const PYTHON = /^python(?:\d+(?:\.\d+)?)?$/;

function skipHeredocs(cmd, i, pending) {
  for (const [stripTabs, delim] of pending) {
    while (i < cmd.length) {
      const end = cmd.indexOf("\n", i);
      const line = end < 0 ? cmd.slice(i) : cmd.slice(i, end);
      i = end < 0 ? cmd.length : end + 1;
      if ((stripTabs ? line.replace(/^\t+/, "") : line).trim() === delim) break;
    }
  }
  return i;
}

// Treść pojedynczych apostrofów to dane — bash nie wykonuje w nich podstawień
// backticków ani `$( … )` (#206). Zamieniamy ją na spacje tej samej długości, żeby
// dopasowania liczone na zamaskowanym tekście wskazywały oryginał.
function maskSingleQuotes(text) {
  let out = "";
  let quote = "";
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (quote === "'" || quote === "$'") {
      // W `$'…'` backslash escapuje także apostrof (`$'it\'s'`).
      if (quote === "$'" && c === "\\" && i + 1 < text.length) {
        out += "  ";
        i += 2;
        continue;
      }
      out += " ";
      if (c === "'") quote = "";
      i += 1;
      continue;
    }
    if (quote === '"') {
      out += c;
      if (c === "\\" && i + 1 < text.length) {
        out += text[i + 1];
        i += 2;
        continue;
      }
      if (c === '"') quote = "";
      i += 1;
      continue;
    }
    if (c === "$" && text[i + 1] === "'") {
      quote = "$'";
      out += "  ";
      i += 2;
      continue;
    }
    if (c === "'") {
      quote = "'";
      out += " ";
      i += 1;
      continue;
    }
    if (c === '"') {
      quote = '"';
      out += c;
      i += 1;
      continue;
    }
    if (c === "\\" && i + 1 < text.length) {
      out += text.slice(i, i + 2);
      i += 2;
      continue;
    }
    out += c;
    i += 1;
  }
  return out;
}

function splitSegments(cmd) {
  cmd = String(cmd);
  const segments = [];
  let buf = "";
  let pending = [];
  let quote = "";
  const flush = () => {
    if (buf.trim()) segments.push(buf);
    buf = "";
  };
  let i = 0;
  while (i < cmd.length) {
    const c = cmd[i];
    if (quote) {
      buf += c;
      if (c === "\\" && quote === '"' && i + 1 < cmd.length) {
        buf += cmd[i + 1];
        i += 1;
      } else if (c === quote) quote = "";
      i += 1;
      continue;
    }
    if (c === '"' || c === "'") {
      quote = c;
      buf += c;
      i += 1;
      continue;
    }
    if (c === "\\" && i + 1 < cmd.length) {
      buf += cmd[i + 1] === "\n" ? " " : cmd.slice(i, i + 2);
      i += 2;
      continue;
    }
    HEREDOC.lastIndex = i;
    const heredoc = HEREDOC.exec(cmd);
    if (heredoc) {
      pending.push([heredoc[1] === "-", heredoc[3]]);
      buf += heredoc[0];
      i = HEREDOC.lastIndex;
      continue;
    }
    if (c === "\n") {
      flush();
      i = skipHeredocs(cmd, i + 1, pending);
      pending = [];
      continue;
    }
    if (cmd.startsWith("&&", i) || cmd.startsWith("||", i)) {
      flush();
      i += 2;
      continue;
    }
    if (";|&()\r".includes(c)) {
      flush();
      i += 1;
      continue;
    }
    buf += c;
    i += 1;
  }
  flush();

  const extra = [];
  for (const seg of segments) {
    for (const m of seg.matchAll(SHELL_C)) {
      const inner = m[1] || m[2] || m[3] || "";
      if (inner.trim()) extra.push(...splitSegments(inner));
    }
    // Maskowanie tylko dla podstawień: `bash -c '…'` dalej czyta surowy segment,
    // bo pojedyncze apostrofy `-c` to skrypt wykonywany przez powłokę.
    const code = maskSingleQuotes(seg);
    for (const regex of [SUBSHELL, BACKTICK]) {
      for (const m of code.matchAll(regex)) {
        if (m[1].trim()) extra.push(...splitSegments(m[1]));
      }
    }
  }
  return [...segments, ...extra];
}

function stripPrefixes(segment) {
  const assigns = {};
  let prev = null;
  let cur = segment;
  while (prev !== cur) {
    prev = cur;
    if (LOOKUP_FLAG.test(cur)) return ["", assigns];
    const m = cur.match(ASSIGN);
    if (m) {
      assigns[m[1]] = m[2].replace(/^['"]+|['"]+$/g, "");
      cur = cur.slice(m[0].length);
      continue;
    }
    for (const [re, sub] of PREFIXES) cur = cur.replace(re, sub);
  }
  return [cur, assigns];
}

function skipFlags(toks, i, withArg) {
  while (i < toks.length && toks[i].startsWith("-")) i += withArg.has(toks[i]) ? 2 : 1;
  return i;
}

function commandForms(segment) {
  const [command, assigns] = stripPrefixes(segment);
  let toks = command.split(/\s+/).filter(Boolean);
  if (!toks.length) return [[], assigns];
  const head = toks[0];
  let forms = [command];
  let rest = [];
  if (head === "uv") {
    toks = ["uv", ...toks.slice(skipFlags(toks, 1, UV_GLOBAL_ARG))];
    forms = [toks.join(" ")];
    if (toks[1] === "run") rest = toks.slice(skipFlags(toks, 2, UV_RUN_ARG));
  } else if (head === "npx" || head === "bunx") {
    rest = toks.slice(skipFlags(toks, 1, NPX_ARG));
  } else if (["bun", "npm", "pnpm", "yarn"].includes(head)) {
    const i = skipFlags(toks, 1, JS_PM_ARG);
    const sub = toks[i];
    toks = sub === "run" || sub === "run-script"
      ? [head, sub, ...toks.slice(skipFlags(toks, i + 1, JS_PM_ARG))]
      : [head, ...toks.slice(i)];
    forms = [toks.join(" ")];
    if (["dlx", "exec", "x"].includes(toks[1])) rest = toks.slice(skipFlags(toks, 2, NPX_ARG));
  } else if (PYTHON.test(head) && toks.length > 2 && toks[1] === "-m") {
    rest = toks.slice(2);
  }
  if (rest.length) {
    const [inner, innerAssigns] = commandForms(rest.join(" "));
    forms.push(...inner);
    Object.assign(assigns, innerAssigns);
  }
  return [forms, assigns];
}

const ruleOrigin = (rule) => rule.rule || rule.id;

function checkCommand(cmd) {
  const envNoSync = String(process.env.UV_NO_SYNC || "") === "1";
  let fallback = null;
  for (const segment of splitSegments(cmd)) {
    const [forms, assigns] = commandForms(segment);
    const noSync = envNoSync || assigns.UV_NO_SYNC === "1";
    for (const form of forms) {
      let denyHit = null;
      let allowHit = null;
      for (const rule of rules) {
        if (noSync && ruleOrigin(rule) === "uv-run") continue;
        let matched = false;
        try {
          matched = new RegExp(rule.pattern).test(form);
        } catch {
          continue;
        }
        if (!matched) continue;
        if (rule.kind === "allow") allowHit = allowHit || rule;
        else if (!denyHit) denyHit = rule;
      }
      if (!denyHit || allowHit) continue;
      if (ruleOrigin(denyHit) !== "uv-run") return denyHit;
      fallback = fallback || denyHit;
    }
  }
  return fallback;
}

// --- Decyzja -------------------------------------------------------------------
let raw = "";
try {
  raw = readFileSync(0, "utf8");
} catch {
  raw = "";
}
if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);

// Poza VPS guard nie wtrąca się w ogóle — także w nieczytelny payload.
if (!isActive()) abstainOrAllow("");

let payload;
try {
  payload = JSON.parse(raw || "{}");
} catch {
  deny("nieczytelny payload hooka");
}

const toolName = String(payload.tool_name || payload.tool || "");
const command = String(payload.command || (payload.tool_input || {}).command || "");

if (PLAYWRIGHT_TOOL.test(toolName)) {
  deny("narzędzia Playwright MCP — przeglądarka to setki MB na instancję, e2e tylko w CI");
}

const hit = command.trim() ? checkCommand(command) : null;
if (hit) {
  const chain = hit.chain ? ` (${hit.chain})` : "";
  deny(`${hit.reason}${chain} [${hit.id === "wrapper" ? `wrapper:${hit.rule}` : hit.id}]`);
}
abstainOrAllow(toolName);

// Bash: jawne allow jak pozostałe guardy kita (ADR 0006; adapter Cursor/OpenCode
// wymaga decyzji). Inne narzędzia (Playwright MCP w Claude): bez decyzji — jawne
// `allow` zatwierdzałoby narzędzie z pominięciem pytania o zgodę.
function abstainOrAllow(name) {
  let tool = name;
  if (!tool) {
    try {
      tool = String(JSON.parse(raw || "{}").tool_name || "");
    } catch {
      tool = "";
    }
  }
  if (tool.startsWith("mcp__")) process.exit(0);
  emit("allow", "server-guard: brak reguły albo host nie-VPS");
}
