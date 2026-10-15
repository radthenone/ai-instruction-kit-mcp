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
  { id: "docker", kind: "deny", pattern: "^\\s*docker(?=\\s|$)", reason: "kontenery tylko w CI — na hoście działają cudze kontenery" },
  { id: "docker-compose", kind: "deny", pattern: "^\\s*docker\\s+compose(?=\\s|$)", reason: "kontenery tylko w CI — na hoście działają cudze kontenery" },
  { id: "docker-compose-bin", kind: "deny", pattern: "^\\s*docker-compose(?=\\s|$)", reason: "kontenery tylko w CI — na hoście działają cudze kontenery" },
  { id: "podman", kind: "deny", pattern: "^\\s*podman(?=\\s|$)", reason: "kontenery tylko w CI — na hoście działają cudze kontenery" },
  { id: "docker-ps", kind: "allow", pattern: "^\\s*docker\\s+(ps|images|inspect|version|info)(?=\\s|$)", reason: "odczyt stanu kontenerów" },
  { id: "docker-logs", kind: "allow", pattern: "^\\s*docker\\s+logs(?=\\s|$)(?!.*(?:-f|--follow)\\b)", reason: "odczyt logów bez follow" },
  { id: "docker-logs-follow", kind: "deny", pattern: "^\\s*docker\\s+logs(?=\\s|$).*?(?:-f|--follow)\\b", reason: "follow logów trzyma proces i strumień — użyj `docker logs` bez `-f`" },
  { id: "docker-compose-ps", kind: "deny", pattern: "^\\s*docker\\s+compose\\s+config(?=\\s|$)", reason: "kontenery tylko w CI — na hoście działają cudze kontenery" },
  { id: "docker-compose-ps-allow", kind: "allow", pattern: "^\\s*docker(?:\\s+|-)compose\\s+ps(?=\\s|$)", reason: "odczyt stanu kontenerów" },
  { id: "uv-sync", kind: "deny", pattern: "^\\s*uv\\s+(sync|add|remove|lock)(?=\\s|$)", reason: "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI" },
  { id: "uv-pip-install", kind: "deny", pattern: "^\\s*uv\\s+pip\\s+install(?=\\s|$)", reason: "instalacja kompiluje zależności natywne — lockfile zmienia się na PC albo w CI" },
  { id: "pip-install", kind: "deny", pattern: "^\\s*pip3?\\s+install(?=\\s|$)", reason: "instalacja kompiluje zależności natywne — zależności zmieniają się na PC albo w CI" },
  { id: "uv-run", kind: "deny", pattern: "^\\s*uv\\s+run(?=\\s|$)(?!.*--no-sync)", reason: "`uv run` bez `--no-sync` synchronizuje i kompiluje — użyj `uv run --no-sync` albo `UV_NO_SYNC=1`" },
  { id: "uv-run-no-sync", kind: "allow", pattern: "^\\s*uv\\s+run(?=\\s|$).*?--no-sync", reason: "uruchomienie bez synchronizacji" },
  { id: "uvx", kind: "allow", pattern: "^\\s*uvx(?=\\s|$)", reason: "jednorazowe narzędzia bez instalacji do projektu" },
  { id: "bun-pkg", kind: "deny", pattern: "^\\s*bun\\s+(install|add|remove)(?=\\s|$)", reason: "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI" },
  { id: "npm-pkg", kind: "deny", pattern: "^\\s*npm\\s+(install|i|ci)(?=\\s|$)", reason: "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI" },
  { id: "pnpm-pkg", kind: "deny", pattern: "^\\s*pnpm\\s+(install|i|add)(?=\\s|$)", reason: "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI" },
  { id: "yarn-pkg", kind: "deny", pattern: "^\\s*yarn\\s+(install|add)(?=\\s|$)", reason: "instalacja paczek na serwerze — zależności zmieniają się na PC albo w CI" },
  { id: "next-build", kind: "deny", pattern: "^\\s*next\\s+build(?=\\s|$)", reason: "build produkcyjny tylko w CI — na VPS `tsc --noEmit`" },
  { id: "expo-build", kind: "deny", pattern: "^\\s*expo\\s+(prebuild|export)(?=\\s|$)", reason: "build produkcyjny tylko w CI" },
  { id: "eas-build", kind: "deny", pattern: "^\\s*eas\\s+build(?=\\s|$)", reason: "build produkcyjny tylko w CI" },
  { id: "vite-build", kind: "deny", pattern: "^\\s*vite\\s+build(?=\\s|$)", reason: "build produkcyjny tylko w CI" },
  { id: "turbo-build", kind: "deny", pattern: "^\\s*turbo\\s+(run\\s+)?build(?=\\s|$)", reason: "build produkcyjny tylko w CI — na VPS `turbo run lint` / `typecheck`" },
  { id: "turbo-lint", kind: "allow", pattern: "^\\s*turbo\\s+run\\s+(lint|typecheck)(?=\\s|$)", reason: "lekkie bramki na VPS" },
  { id: "playwright", kind: "deny", pattern: "^\\s*(npx\\s+|bunx\\s+|yarn\\s+dlx\\s+|pnpm\\s+dlx\\s+)?playwright(?=\\s|$)", reason: "przeglądarka to setki MB na instancję — e2e tylko w CI" },
  { id: "cypress", kind: "deny", pattern: "^\\s*(npx\\s+|bunx\\s+)?cypress(?=\\s|$)", reason: "przeglądarka to setki MB na instancję — e2e tylko w CI" },
  { id: "maestro", kind: "deny", pattern: "^\\s*maestro(?=\\s|$)", reason: "testy mobilne tylko w CI" },
  { id: "pytest-xdist", kind: "deny", pattern: "^\\s*pytest(?=\\s|$).*?(?:-n\\b|--numprocesses\\b)", reason: "xdist mnoży procesy na słabym CPU — użyj `pytest` bez `-n`" },
];

const PLAYWRIGHT_TOOL = /^mcp__plugin_playwright_.*|^mcp__playwright__.*/;

const emit = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};
const deny = (reason) => emit("deny", `server-guard: ${reason}`);
const allow = () => emit("allow", "server-guard: brak reguły albo host nie-VPS");

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

const toolName = String(payload.tool_name || payload.tool || "");
const command = String(payload.command || (payload.tool_input || {}).command || "");

// --- Konfiguracja (JSON obok guarda) -----------------------------------------
let config = null;
try {
  config = JSON.parse(readFileSync(join(HERE, "server-guard.json"), "utf8"));
} catch {
  config = null;
}
const defaults = Array.isArray(config?.defaults) && config.defaults.length ? config.defaults : EMBEDDED_DEFAULTS;
const wrappers = Array.isArray(config?.wrappers) ? config.wrappers : [];
const rules = [...defaults];
for (const w of wrappers) {
  if (w && w.pattern) rules.push({ id: "wrapper", kind: "deny", pattern: w.pattern, reason: w.reason || "ciężki wrapper (Taskfile/package.json)", chain: w.chain, via: w.rule });
}
for (const item of config?.project_deny || []) {
  rules.push({ id: `project-deny:${item}`, kind: "deny", pattern: literalPattern(item), reason: `dodatkowy deny projektu (\`server.deny\`: ${item})` });
}
for (const item of config?.project_allow || []) {
  rules.push({ id: `project-allow:${item}`, kind: "allow", pattern: literalPattern(item), reason: `wyjątek projektu (\`server.allow\`: ${item})` });
}

function literalPattern(cmd) {
  return "^\\s*" + String(cmd).split(/\s+/).map(escapeRegExp).join("\\s+") + "(?=\\s|$)";
}
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// --- Aktywacja ----------------------------------------------------------------
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
    const text = readFileSync("/proc/meminfo", "utf8");
    let mem = null;
    let swap = null;
    for (const line of text.split("\n")) {
      const m = line.match(/^(MemTotal|SwapTotal):\s+(\d+)\s*kB/);
      if (m) {
        const bytes = Number(m[2]) * 1024;
        if (m[1] === "MemTotal") mem = bytes;
        else swap = bytes;
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
    const out = execFileSync("systemd-detect-virt", { encoding: "utf8", timeout: 5000 }).trim().toLowerCase();
    return out;
  } catch {
    return "";
  }
}

function isCI(env) {
  if (process.env.GUARD_IS_CI !== undefined) return process.env.GUARD_IS_CI === "1";
  if (String(env.CI || "").trim().toLowerCase() === "1") return true;
  if (["true", "yes"].includes(String(env.CI || "").trim().toLowerCase())) return true;
  return ["GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "BUILDKITE", "CIRCLECI", "TRAVIS", "TF_BUILD"]
    .some((v) => String(env[v] || "").trim() !== "");
}

function hasDesktop(env) {
  if (process.env.GUARD_HAS_DESKTOP !== undefined) return process.env.GUARD_HAS_DESKTOP === "1";
  return ["DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION"]
    .some((v) => String(env[v] || "").trim() !== "");
}

function isWSL(env) {
  if (process.env.GUARD_IS_WSL !== undefined) return process.env.GUARD_IS_WSL === "1";
  if (String(env.WSL_DISTRO_NAME || "").trim() || String(env.WSL_INTEROP || "").trim()) return true;
  try {
    const version = readFileSync("/proc/version", "utf8").toLowerCase();
    return version.includes("microsoft") || version.includes("wsl");
  } catch {
    return false;
  }
}

function isActive() {
  if (config?.guard === "off") return false;
  const override = normalizeOverride(process.env.KIT_HOST_PROFILE) || normalizeOverride(process.env.GUIDES_HOST_PROFILE);
  if (override) return override === "vps";

  const plat = process.env.GUARD_PLATFORM || osPlatform();
  if (!String(plat).startsWith("linux")) return false;
  if (isCI(process.env)) return false;
  if (isWSL(process.env)) return false;

  const cpu = process.env.GUARD_CPU_COUNT !== undefined ? Number(process.env.GUARD_CPU_COUNT) : cpus().length;
  const [mem, swap] = readMeminfo();
  if (!Number.isFinite(cpu) || mem === null || swap === null) return false;
  if (!(cpu <= 2 && mem <= 8 * 1024 ** 3 && swap === 0)) return false;

  const virt = detectVirt();
  const virtualized = Boolean(virt) && virt !== "none" && virt !== "unknown";
  if (virtualized || !hasDesktop(process.env)) return true;
  return false;
}

// --- Dopasowanie komendy -------------------------------------------------------
function splitSegments(cmd) {
  const parts = String(cmd).replace(/\r/g, " ").split(/&&|\|\||[;|&()\n]/).map((s) => s.trim()).filter(Boolean);
  const extra = [];
  const bashC = /(?:^|\s)(?:bash|sh)\s+-c\s+(?:"([^"]*)"|'([^']*)'|(\S+))/g;
  const subshell = /\$\(\s*(.*?)\s*\)/g;
  for (const seg of parts) {
    let m;
    bashC.lastIndex = 0;
    while ((m = bashC.exec(seg))) {
      const inner = m[1] ?? m[2] ?? m[3] ?? "";
      if (inner.trim()) extra.push(...splitSegments(inner));
    }
    subshell.lastIndex = 0;
    while ((m = subshell.exec(seg))) {
      if (m[1].trim()) extra.push(...splitSegments(m[1]));
    }
  }
  return [...parts, ...extra];
}

function stripPrefixes(segment) {
  let prev = null;
  let cur = segment;
  const patterns = [
    /^\s*sudo\b\s*(?:(?:-[ugpCDhrtU]\s+\S+|-\S+)\s+)*/,
    /^\s*(?:[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+)+/,
    /^\s*env\b\s*/,
    /^\s*(?:nice|ionice|nohup|time|command|exec|xargs)\b\s*(?:-\S+(?:\s+\d+)?\s+)*/,
    /^\s*timeout\b\s*(?:(?:-[^\s]+|[\d.]+[smhd]?)\s+)*/,
  ];
  while (prev !== cur) {
    prev = cur;
    for (const re of patterns) cur = cur.replace(re, "");
  }
  return cur;
}

function checkCommand(cmd) {
  const noSync = String(process.env.UV_NO_SYNC || "") === "1";
  for (const segment of splitSegments(cmd)) {
    const stripped = stripPrefixes(segment);
    let denyHit = null;
    let allowHit = null;
    for (const rule of rules) {
      if (noSync && rule.id === "uv-run" && /^\s*uv\s+run(?=\s|$)/.test(stripped)) continue;
      if (noSync && rule.via === "uv-run") continue;
      let matched = false;
      try {
        matched = new RegExp(rule.pattern).test(stripped);
      } catch {
        continue;
      }
      if (!matched) continue;
      if (rule.kind === "allow" && !allowHit) allowHit = rule;
      if (rule.kind === "deny" && !denyHit) denyHit = rule;
    }
    if (denyHit && !allowHit) return denyHit;
  }
  return null;
}

// --- Decyzja -------------------------------------------------------------------
if (!isActive()) allow();

if (PLAYWRIGHT_TOOL.test(toolName)) {
  deny("narzędzia Playwright MCP — przeglądarka to setki MB na instancję, e2e tylko w CI");
}

if (!command.trim()) allow();

const hit = checkCommand(command);
if (hit) {
  const chain = hit.chain ? ` (${hit.chain})` : "";
  deny(`${hit.reason}${chain} [${hit.id}]`);
}
allow();
