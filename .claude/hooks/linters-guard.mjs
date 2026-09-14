#!/usr/bin/env node
/**
 * Guard: format + lint edytowanego pliku (PostToolUse: Edit|Write|MultiEdit|NotebookEdit).
 *
 * Najpierw format (naprawia, co sie da automatycznie), potem lint (zglasza reszte).
 * Wynik lintu wraca do modelu jako `additionalContext`, wiec kolejny krok agenta
 * widzi bledy i sam je naprawia. To feedback, nie bramka: PostToolUse nie cofnie
 * zapisu, wiec exit zawsze 0 i nigdy nie blokujemy narzedzia.
 *
 * Opt-in per repo: narzedzie odpala sie tylko, gdy w repo jest jego config
 * i binarka jest dostepna. Bez configu — cisza. Tylko edytowany plik.
 *
 *   .py                          ruff format  → ruff check     ruff.toml / .ruff.toml / [tool.ruff]
 *   .ts .tsx .js .jsx .mjs .cjs  prettier     → eslint         .prettierrc* / prettier.config.* ; eslint.config.* / .eslintrc*
 *   .css .scss .html .json .md   prettier                      .prettierrc* / prettier.config.*
 *   .yaml .yml                   prettier     → yamllint       (yamllint tylko gdy .yamllint*)
 *   .toml                        prettier                      tylko gdy config prettiera wspomina toml
 *   .sh .bash                                 → shellcheck     .shellcheckrc
 *   Dockerfile*                               → hadolint       .hadolint.yaml / .hadolint.yml
 *   .ipynb                       pomijamy
 *
 * Binarka: node_modules/.bin → .venv/Scripts | .venv/bin → PATH. Brak → pomin cicho.
 * Stdout skrocony do `plik:linia: komunikat`, max 30 linii. Timeout 20 s lacznie.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, dirname, extname, join, relative, resolve, sep } from "node:path";

const MAX_LINES = 30;
const TIMEOUT_MS = 20000;
const started = Date.now();

const read = (p) => {
  try {
    return readFileSync(p, "utf8");
  } catch {
    return "";
  }
};

function repoRoot(from) {
  let dir = from;
  for (;;) {
    if (existsSync(join(dir, ".git"))) return dir;
    const up = dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
}

const anyExists = (root, names) => names.some((n) => existsSync(join(root, n)));
const anyGlob = (root, prefix) => {
  try {
    return readdirSync(root).some((n) => n.startsWith(prefix));
  } catch {
    return false;
  }
};

const PRETTIER_CFG = [".prettierrc", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.yml", ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.mjs", ".prettierrc.toml", "prettier.config.js", "prettier.config.cjs", "prettier.config.mjs"];
const ESLINT_CFG = ["eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml"];

function hasPrettier(root) {
  return anyExists(root, PRETTIER_CFG) || /"prettier"\s*:/.test(read(join(root, "package.json")));
}
function hasRuff(root) {
  return anyExists(root, ["ruff.toml", ".ruff.toml"]) || read(join(root, "pyproject.toml")).includes("[tool.ruff");
}

// Binarka: lokalna z repo przed globalna z PATH. Zwraca [cmd, prefixArgs] albo null.
function bin(root, name) {
  const win = process.platform === "win32";
  const candidates = [
    join(root, "node_modules", ".bin", win ? `${name}.cmd` : name),
    join(root, ".venv", "Scripts", `${name}.exe`),
    join(root, ".venv", "bin", name),
  ];
  for (const c of candidates) if (existsSync(c)) return [c, []];
  if (name === "ruff" && existsSync(join(root, "uv.lock"))) return ["uv", ["run", "--quiet", "ruff"]];
  return [name, []];
}

function run(root, name, args) {
  const left = TIMEOUT_MS - (Date.now() - started);
  if (left <= 0) return null;
  const [cmd, pre] = bin(root, name);
  try {
    return execFileSync(cmd, [...pre, ...args], {
      cwd: root,
      encoding: "utf8",
      timeout: left,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
      shell: process.platform === "win32",
    });
  } catch (err) {
    // ENOENT = brak binarki → pomin. Kod != 0 = lint znalazl problemy → wyjscie jest wynikiem.
    if (err && err.code === "ENOENT") return null;
    if (err && (err.stdout || err.stderr)) return `${err.stdout || ""}${err.stderr || ""}`;
    return null;
  }
}

// `plik:linia: komunikat` — tylko linie z lokalizacja, zeby model dostal to, co da sie naprawic.
function condense(text, file) {
  const rel = relative(process.cwd(), file) || basename(file);
  const out = [];
  for (const line of (text || "").split(/\r?\n/)) {
    const m = line.match(/^(.*?):(\d+)(?::(\d+))?[:\s-]+(.*)$/);
    if (m && m[4]) out.push(`${rel}:${m[2]}: ${m[4].trim()}`);
    else if (/^\s*\d+:\d+\s+(error|warning)/.test(line)) out.push(`${rel}:${line.trim()}`);
    else if (/^(In|Line) .*line \d+/.test(line)) out.push(`${rel}: ${line.trim()}`);
  }
  return out;
}

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  try {
    const raw = JSON.parse(input || "{}")?.tool_input;
    const target = raw?.file_path || raw?.notebook_path;
    if (!target || !existsSync(target)) return;
    const file = resolve(target);
    const root = repoRoot(dirname(file));
    if (!root || !file.startsWith(root + sep)) return;

    const ext = extname(file).toLowerCase();
    const name = basename(file);
    const problems = [];
    const ran = [];

    if (ext === ".ipynb") return;

    if (ext === ".py" && hasRuff(root)) {
      run(root, "ruff", ["format", "--quiet", file]);
      ran.push("ruff format");
      const out = run(root, "ruff", ["check", "--output-format", "concise", "--no-fix", file]);
      ran.push("ruff check");
      problems.push(...condense(out, file));
    }

    const web = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];
    const prettierOnly = [".css", ".scss", ".html", ".json", ".md", ".yaml", ".yml"];
    const wantsPrettier = web.includes(ext) || prettierOnly.includes(ext) || (ext === ".toml" && /toml/i.test(PRETTIER_CFG.map((f) => read(join(root, f))).join("")));

    if (wantsPrettier && hasPrettier(root)) {
      run(root, "prettier", ["--write", "--log-level", "warn", file]);
      ran.push("prettier");
    }
    if (web.includes(ext) && anyExists(root, ESLINT_CFG)) {
      const out = run(root, "eslint", ["--format", "unix", "--no-fix", file]);
      ran.push("eslint");
      problems.push(...condense(out, file));
    }
    if ((ext === ".yaml" || ext === ".yml") && anyGlob(root, ".yamllint")) {
      const out = run(root, "yamllint", ["-f", "parsable", file]);
      ran.push("yamllint");
      problems.push(...condense(out, file));
    }
    if ((ext === ".sh" || ext === ".bash") && existsSync(join(root, ".shellcheckrc"))) {
      const out = run(root, "shellcheck", ["-f", "gcc", file]);
      ran.push("shellcheck");
      problems.push(...condense(out, file));
    }
    if (/^Dockerfile/i.test(name) && anyExists(root, [".hadolint.yaml", ".hadolint.yml"])) {
      const out = run(root, "hadolint", ["--no-color", file]);
      ran.push("hadolint");
      problems.push(...condense(out, file));
    }

    if (!ran.length || !problems.length) return;

    const shown = problems.slice(0, MAX_LINES);
    const more = problems.length > shown.length ? `\n… i ${problems.length - shown.length} wiecej` : "";
    const context = `linters-guard: ${problems.length} problem(ow) w ${relative(root, file)} (${ran.join(", ")}):\n${shown.join("\n")}${more}`;
    process.stdout.write(
      JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: context } }) + "\n"
    );
  } catch {
    // Feedback jest best-effort — awaria hooka nie moze przerwac sesji.
  }
});
