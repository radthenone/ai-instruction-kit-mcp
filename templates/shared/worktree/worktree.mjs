#!/usr/bin/env node
/**
 * Zarządzanie worktree w projekcie z instruction-kit (#299).
 *
 * Komendy:
 *   add [<ścieżka>] <branch> [--plain]
 *   add [<ścieżka>] --detach <ref> [--plain]
 *   sync [<ścieżka>]
 *   remove <ścieżka> [--force]
 *   prune [--base <ref>]
 *
 * Format wyjścia: linie `[worktree] key: value`.
 * Kody wyjścia: 0 = OK, 1 = błąd setup: (worktree zostaje), 2 = błędne wywołanie.
 */

import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const DEFAULT_MACHINE_FILES = [
  ".mcp.json",
  ".cursor/mcp.json",
  ".vscode/mcp.json",
  ".codex/config.toml",
  ".kiro/settings/mcp.json",
  ".kilocode/mcp.json",
  ".agents/mcp_config.json",
  "opencode.json",
  ".ai/.kit-bootstrap.json",
  ".ai/.kit-doctor.json",
  ".env",
  ".claude/settings.local.json",
];

const LOCKFILES = [
  "uv.lock",
  "bun.lock",
  "bun.lockb",
  "package.json",
  "pnpm-lock.yaml",
  "yarn.lock",
  "poetry.lock",
  "Pipfile.lock",
];

const GUARD_LOCATIONS = [
  ".cursor/hooks/server-guard.mjs",
  ".claude/hooks/server-guard.mjs",
  ".vscode/.github/hooks/server-guard.mjs",
  ".github/hooks/server-guard.mjs",
  ".agents/hooks/server-guard.mjs",
  ".codex/hooks/server-guard.mjs",
];

// Argumenty idą jako tablica do execFileSync, bez powłoki (brak wstrzyknięcia).
function git(args, cwd = process.cwd()) {
  return execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

function gitTry(args, cwd = process.cwd()) {
  try {
    return git(args, cwd);
  } catch {
    return null;
  }
}

function real(p) {
  try {
    return fs.realpathSync(p);
  } catch {
    return path.resolve(p);
  }
}

function lexists(p) {
  try {
    fs.lstatSync(p);
    return true;
  } catch {
    return false;
  }
}

// Względna ścieżka `p` wewnątrz `root`, albo null gdy poza `root` (lub absolutna).
function relInside(root, p) {
  const rel = path.relative(root, p);
  if (rel === ".." || rel.startsWith(".." + path.sep) || path.isAbsolute(rel)) return null;
  return rel;
}

function isInside(root, p) {
  const rel = relInside(root, p);
  return rel !== null && rel !== "";
}

function getMainRepoRoot(cwd = process.cwd()) {
  const common = git(["rev-parse", "--git-common-dir"], cwd);
  const resolved = path.isAbsolute(common) ? common : path.resolve(cwd, common);
  return path.resolve(resolved, "..");
}

function listWorktrees(mainRoot) {
  const raw = git(["worktree", "list", "--porcelain"], mainRoot);
  const out = [];
  for (const block of raw.split("\n\n")) {
    let wtPath = null;
    let branch = null;
    for (const l of block.split("\n")) {
      if (l.startsWith("worktree ")) wtPath = l.slice(9).trim();
      if (l.startsWith("branch ")) branch = l.slice(7).trim().replace(/^refs\/heads\//, "");
    }
    if (wtPath) out.push({ path: wtPath, branch });
  }
  return out;
}

function loadConfig(mainRoot) {
  const configPath = path.join(mainRoot, ".ai", "worktree.json");
  if (fs.existsSync(configPath)) {
    try {
      return JSON.parse(fs.readFileSync(configPath, "utf8"));
    } catch {
      // fallback
    }
  }
  const defaultCopy = DEFAULT_MACHINE_FILES.filter((f) => fs.existsSync(path.join(mainRoot, f)));
  return {
    copy: defaultCopy,
    link: [],
    setup: [],
    venv: "auto",
  };
}

function ensureGitignoreWorktrees(mainRoot) {
  const giPath = path.join(mainRoot, ".gitignore");
  if (!fs.existsSync(giPath)) return;
  const content = fs.readFileSync(giPath, "utf8");
  if (!content.includes(".worktrees")) {
    fs.appendFileSync(giPath, (content.endsWith("\n") ? "" : "\n") + ".worktrees/\n", "utf8");
  }
}

function sanitizeBranchSlug(branch) {
  return branch.replace(/[\/\\]/g, "-").replace(/[^a-zA-Z0-9._-]+/g, "-");
}

function askServerGuard(mainRoot, command) {
  for (const rel of GUARD_LOCATIONS) {
    const full = path.join(mainRoot, rel);
    if (fs.existsSync(full)) {
      try {
        const payload = JSON.stringify({
          tool_name: "Bash",
          tool_input: { command },
        });
        const res = spawnSync(process.execPath, [full], {
          input: payload,
          encoding: "utf8",
          stdio: ["pipe", "pipe", "pipe"],
          env: process.env,
        });
        if (res.stdout) {
          try {
            const data = JSON.parse(res.stdout);
            const decision = data?.hookSpecificOutput?.permissionDecision ?? data?.permissionDecision;
            const reason = data?.hookSpecificOutput?.permissionDecisionReason ?? data?.reason ?? data?.permissionDecisionReason;
            if (decision === "deny") {
              return { allowed: false, reason: reason || "zablokowane przez server-guard" };
            }
            return { allowed: true };
          } catch {
            // nie JSON
          }
        }
      } catch {
        // błąd guarda
      }
    }
  }
  return { allowed: true };
}

function performCopy(mainRoot, wtPath, copyList, warnings) {
  const copied = [];
  for (const item of copyList || []) {
    const src = path.resolve(mainRoot, item);
    const dest = path.resolve(wtPath, item);
    if (!isInside(mainRoot, src) || !isInside(wtPath, dest)) {
      warnings.push(`pominięto copy poza repo: ${item}`);
      continue;
    }
    if (!fs.existsSync(src)) continue;
    if (lexists(dest)) continue;
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const stat = fs.statSync(src);
    if (stat.isDirectory()) {
      fs.cpSync(src, dest, { recursive: true });
    } else {
      fs.copyFileSync(src, dest);
    }
    copied.push(item);
  }
  return copied;
}

function performLink(mainRoot, wtPath, linkList, warnings) {
  const linked = [];
  const isWin = process.platform === "win32";
  for (const item of linkList || []) {
    const src = path.resolve(mainRoot, item);
    const dest = path.resolve(wtPath, item);
    if (!isInside(mainRoot, src) || !isInside(wtPath, dest)) {
      warnings.push(`pominięto link poza repo: ${item}`);
      continue;
    }
    if (!fs.existsSync(src)) continue;
    if (lexists(dest)) {
      if (!fs.existsSync(dest)) warnings.push(`zerwany symlink w worktree, pomijam: ${item}`);
      continue;
    }
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const stat = fs.statSync(src);
    if (isWin) {
      if (stat.isDirectory()) {
        fs.symlinkSync(src, dest, "junction");
        linked.push(item);
      } else {
        fs.copyFileSync(src, dest);
        warnings.push(`link pliku na Windows skopiowany zamiast symlinka: ${item}`);
        linked.push(item);
      }
    } else {
      fs.symlinkSync(src, dest);
      linked.push(item);
    }
  }

  if (linkList && linkList.some((it) => it.includes("node_modules"))) {
    warnings.push("link do node_modules: pakiety workspace (bun/pnpm/yarn) wskazują główne drzewo");
    warnings.push(
      "Zależności z link i overlay są wspólne z głównym checkoutem, więc traktuj je jako tylko do odczytu (postinstall, ensurepip i cache zmieniają środowisko główne)"
    );
  }
  return linked;
}

function performSetup(wtPath, mainRoot, setupCommands) {
  const lines = [];
  let failed = false;
  for (const cmd of setupCommands || []) {
    const guardRes = askServerGuard(mainRoot, cmd);
    if (!guardRes.allowed) {
      lines.push(`setup skipped: ${cmd} — ${guardRes.reason}`);
      continue;
    }
    const res = spawnSync(cmd, { shell: true, cwd: wtPath, stdio: "inherit" });
    if (res.status !== 0) {
      lines.push(`setup failed: ${cmd}`);
      failed = true;
    } else {
      lines.push(`setup ran: ${cmd}`);
    }
  }
  return { lines, failed };
}

function findSitePackages(venvPath) {
  if (process.platform === "win32") {
    const p = path.join(venvPath, "Lib", "site-packages");
    return fs.existsSync(p) ? p : null;
  }
  const lib = path.join(venvPath, "lib");
  if (!fs.existsSync(lib)) return null;
  const entries = fs.readdirSync(lib);
  for (const entry of entries) {
    if (entry.startsWith("python")) {
      const sp = path.join(lib, entry, "site-packages");
      if (fs.existsSync(sp)) return sp;
    }
  }
  return null;
}

function setupVenvOverlay(mainRoot, wtPath, venvMode, warnings) {
  const mainVenv = path.join(mainRoot, ".venv");
  const wtVenv = path.join(wtPath, ".venv");

  if (venvMode === "none") return "none";
  if (real(wtPath) === real(mainRoot)) {
    warnings.push("overlay venv pominięty: ścieżka to główny checkout");
    return "none";
  }
  const shouldCreate = venvMode === "overlay" || (venvMode === "auto" && fs.existsSync(mainVenv) && !fs.existsSync(wtVenv));
  if (!shouldCreate) {
    return fs.existsSync(wtVenv) ? "full" : "none";
  }

  if (!fs.existsSync(mainVenv)) return "none";

  const isWin = process.platform === "win32";
  const pyExe = isWin ? path.join(mainVenv, "Scripts", "python.exe") : path.join(mainVenv, "bin", "python");
  if (!fs.existsSync(pyExe)) return "none";

  try {
    execFileSync(pyExe, ["-m", "venv", "--without-pip", wtVenv], { stdio: "ignore" });
  } catch {
    return "none";
  }

  const mainSp = findSitePackages(mainVenv);
  const wtSp = findSitePackages(wtVenv);
  if (!mainSp || !wtSp) return "overlay";

  const rewrittenPaths = [];
  const pthFiles = fs.readdirSync(mainSp).filter((f) => f.endsWith(".pth"));
  for (const pth of pthFiles) {
    const fullPth = path.join(mainSp, pth);
    const content = fs.readFileSync(fullPth, "utf8");
    if (content.includes("import __editable___")) {
      warnings.push(`editable przez import hook: ${pth} — not redirected`);
      continue;
    }
    const lines = content.split(/\r?\n/);
    for (const l of lines) {
      const trimmed = l.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      if (!path.isAbsolute(trimmed)) continue;
      const rel = relInside(mainRoot, trimmed);
      if (rel !== null) {
        rewrittenPaths.push(path.join(wtPath, rel));
      }
    }
  }

  const pthContent = [...rewrittenPaths, mainSp].join("\n") + "\n";
  fs.writeFileSync(path.join(wtSp, "_kit_worktree.pth"), pthContent, "utf8");

  warnings.push("Overlay nie ma console scripts w bin/, więc testy uruchamia się przez python -m …");
  return "overlay";
}

function checkLockfileDrift(mainRoot, wtPath, warnings) {
  for (const lf of LOCKFILES) {
    const mainLf = path.join(mainRoot, lf);
    const wtLf = path.join(wtPath, lf);
    if (fs.existsSync(mainLf) && fs.existsSync(wtLf)) {
      try {
        const b1 = fs.readFileSync(mainLf);
        const b2 = fs.readFileSync(wtLf);
        if (!b1.equals(b2)) {
          warnings.push("deps differ from main checkout — VPS tests unreliable, verify in CI");
          break;
        }
      } catch {
        // ignore
      }
    }
  }
}

function cmdAdd(args) {
  const plain = args.includes("--plain");
  const filtered = args.filter((a) => a !== "--plain");
  let detach = false;
  let targetRef = null;
  let targetPath = null;

  for (let i = 0; i < filtered.length; i++) {
    if (filtered[i] === "--detach") {
      detach = true;
      if (i + 1 < filtered.length) {
        targetRef = filtered[i + 1];
        i++;
      }
    } else if (!targetPath && filtered[i]) {
      // Jeśli to ostatni argument i nie ma jeszcze refa ani path
      if (!targetRef && i === filtered.length - 1 && !detach) {
        targetRef = filtered[i];
      } else {
        targetPath = filtered[i];
      }
    } else if (!targetRef && filtered[i]) {
      targetRef = filtered[i];
    }
  }

  if (!targetRef) {
    console.error("Użycie: worktree.mjs add [<ścieżka>] <branch|--detach ref> [--plain]");
    process.exit(2);
  }

  const mainRoot = getMainRepoRoot();
  if (!targetPath) {
    ensureGitignoreWorktrees(mainRoot);
    const slug = detach ? `detached-${sanitizeBranchSlug(targetRef)}` : sanitizeBranchSlug(targetRef);
    targetPath = path.join(mainRoot, ".worktrees", slug);
  } else {
    targetPath = path.resolve(process.cwd(), targetPath);
    if (targetPath.startsWith(path.join(mainRoot, ".worktrees"))) {
      ensureGitignoreWorktrees(mainRoot);
    }
  }

  // Wykonanie git worktree add
  if (detach) {
    git(["worktree", "add", "--detach", targetPath, targetRef], mainRoot);
  } else {
    const hasLocal = gitTry(["show-ref", "--verify", "--quiet", `refs/heads/${targetRef}`], mainRoot) !== null;
    const hasRemote = gitTry(["show-ref", "--verify", "--quiet", `refs/remotes/origin/${targetRef}`], mainRoot) !== null;
    if (hasLocal || hasRemote) {
      // DWIM: lokalny branch albo tracking origin/<branch>, bez -b
      git(["worktree", "add", targetPath, targetRef], mainRoot);
    } else {
      git(["worktree", "add", "-b", targetRef, targetPath], mainRoot);
    }
  }

  const branchDisplay = detach ? `detached ${targetRef}` : targetRef;
  console.log(`[worktree] path: ${targetPath}`);
  console.log(`[worktree] branch: ${branchDisplay}`);

  if (plain) {
    process.exit(0);
  }

  const config = loadConfig(mainRoot);
  const warnings = [];

  const copied = performCopy(mainRoot, targetPath, config.copy, warnings);
  console.log(`[worktree] copied: ${copied.join(", ")}`);

  const linked = performLink(mainRoot, targetPath, config.link, warnings);
  console.log(`[worktree] linked: ${linked.join(", ")}`);

  const setupRes = performSetup(targetPath, mainRoot, config.setup);
  for (const line of setupRes.lines) {
    console.log(`[worktree] ${line}`);
  }

  const venvType = setupVenvOverlay(mainRoot, targetPath, config.venv, warnings);
  console.log(`[worktree] venv: ${venvType}`);

  checkLockfileDrift(mainRoot, targetPath, warnings);

  for (const w of warnings) {
    console.log(`[worktree] ${w}`);
  }

  const testCmd = venvType === "overlay" ? "uv run --no-sync python -m …" : "python -m …";
  console.log(`[worktree] test with: ${testCmd}`);

  if (setupRes.failed) {
    process.exit(1);
  }
  process.exit(0);
}

function cmdSync(args) {
  const targetPath = path.resolve(process.cwd(), args[0] || ".");
  const mainRoot = getMainRepoRoot(targetPath);
  if (real(targetPath) === real(mainRoot)) {
    console.error("odmowa: to główny checkout, sync działa tylko na worktree");
    process.exit(2);
  }
  if (!listWorktrees(mainRoot).some((w) => real(w.path) === real(targetPath))) {
    console.error(`odmowa: ścieżka nie jest worktree tego repo: ${targetPath}`);
    process.exit(2);
  }
  const config = loadConfig(mainRoot);
  const warnings = [];

  const branch = gitTry(["branch", "--show-current"], targetPath) || "detached";
  console.log(`[worktree] path: ${targetPath}`);
  console.log(`[worktree] branch: ${branch}`);

  const copied = performCopy(mainRoot, targetPath, config.copy, warnings);
  console.log(`[worktree] copied: ${copied.join(", ")}`);

  const linked = performLink(mainRoot, targetPath, config.link, warnings);
  console.log(`[worktree] linked: ${linked.join(", ")}`);

  const venvType = setupVenvOverlay(mainRoot, targetPath, config.venv, warnings);
  console.log(`[worktree] venv: ${venvType}`);

  checkLockfileDrift(mainRoot, targetPath, warnings);

  for (const w of warnings) {
    console.log(`[worktree] ${w}`);
  }
  console.log(`[worktree] test with: uv run --no-sync python -m …`);
  process.exit(0);
}

function cmdRemove(args) {
  const force = args.includes("--force");
  const filtered = args.filter((a) => a !== "--force");
  if (!filtered[0]) {
    console.error("Użycie: worktree.mjs remove <ścieżka> [--force]");
    process.exit(2);
  }
  const targetPath = path.resolve(process.cwd(), filtered[0]);
  if (!fs.existsSync(targetPath)) {
    console.error(`Ścieżka nie istnieje: ${targetPath}`);
    process.exit(2);
  }

  const mainRoot = getMainRepoRoot(targetPath);
  if (real(targetPath) === real(mainRoot)) {
    console.error("odmowa: to główny checkout, nie worktree");
    process.exit(2);
  }
  if (!listWorktrees(mainRoot).some((w) => real(w.path) === real(targetPath))) {
    console.error(`odmowa: ścieżka nie jest worktree tego repo: ${targetPath}`);
    process.exit(2);
  }

  const status = gitTry(["status", "--porcelain"], targetPath);
  if (status && status.length > 0 && !force) {
    console.error("drzewo robocze jest brudne, użyj --force aby usunąć");
    process.exit(2);
  }

  // Dopiero po sprawdzeniu, że to worktree; git worktree remove usuwa też overlay .venv.
  git(["worktree", "remove", ...(force ? ["--force"] : []), targetPath], mainRoot);
  gitTry(["worktree", "prune"], mainRoot);
  console.log(`[worktree] removed: ${targetPath}`);
  process.exit(0);
}

function cmdPrune(args) {
  const mainRoot = getMainRepoRoot();
  const baseIdx = args.indexOf("--base");
  let base = baseIdx >= 0 ? args[baseIdx + 1] : null;
  if (!base) base = gitTry(["branch", "--show-current"], mainRoot);
  if (!base) {
    console.error("prune: brak bazy (detached HEAD) — podaj --base <ref>");
    process.exit(2);
  }

  gitTry(["worktree", "prune"], mainRoot);
  const kitDir = real(path.join(mainRoot, ".worktrees"));
  for (const wt of listWorktrees(mainRoot)) {
    if (!isInside(kitDir, real(wt.path))) {
      console.log(`[worktree] skipped: ${wt.path} — nie jest worktree kita`);
      continue;
    }
    if (!wt.branch) {
      console.log(`[worktree] skipped: ${wt.path} — detached`);
      continue;
    }
    const dirty = gitTry(["status", "--porcelain"], wt.path);
    if (dirty && dirty.length > 0) {
      console.log(`[worktree] skipped: ${wt.path} — niezacommitowane zmiany`);
      continue;
    }
    const merged = gitTry(["merge-base", "--is-ancestor", `refs/heads/${wt.branch}`, base], mainRoot) !== null;
    if (!merged) {
      console.log(`[worktree] skipped: ${wt.path} — branch nie jest zmergowany do ${base}`);
      continue;
    }
    // Branch bez własnych commitów (tylko utworzony) zostaje.
    const reflog = gitTry(["reflog", "show", "--format=%gs", `refs/heads/${wt.branch}`], mainRoot) || "";
    if (!reflog.split("\n").some((l) => l.startsWith("commit"))) {
      console.log(`[worktree] skipped: ${wt.path} — branch bez własnych commitów`);
      continue;
    }
    if (gitTry(["worktree", "remove", wt.path], mainRoot) !== null) {
      console.log(`[worktree] removed: ${wt.path}`);
    } else {
      console.log(`[worktree] skipped: ${wt.path} — git worktree remove odmówił`);
    }
  }
  console.log("[worktree] pruned");
  process.exit(0);
}

const [cmd, ...rest] = process.argv.slice(2);
switch (cmd) {
  case "add":
    cmdAdd(rest);
    break;
  case "sync":
    cmdSync(rest);
    break;
  case "remove":
    cmdRemove(rest);
    break;
  case "prune":
    cmdPrune(rest);
    break;
  default:
    console.error("Nieznana komenda. Dozwolone: add, sync, remove, prune");
    process.exit(2);
}
