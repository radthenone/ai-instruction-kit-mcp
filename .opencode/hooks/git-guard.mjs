#!/usr/bin/env node
/**
 * Guard: destrukcyjne komendy gita i shella (PreToolUse: Bash).
 *
 * Polityka zna tylko dwie odpowiedzi — allow albo deny. Nigdy `ask`: w auto mode
 * `ask` z hooka blokuje tak samo jak prompt, więc bramka, która pyta, nie jest
 * automatyczna. Co nie jest na liście deny, przechodzi. ADR 0006.
 *
 * Deny:
 *   - git reset --hard
 *   - git clean z flagą -f
 *   - force push na main/master/dev (--force, --force-with-lease, -f, +refspec)
 *   - git push (bez force) na main/master/dev — workflow to PR
 *   - git branch -D
 *   - git checkout .  /  git checkout -- <cokolwiek>
 *   - rekursywne rm na szerokiej ścieżce (~, /, .., katalog domowy, goły dysk)
 *   - mutacja, sed -i albo redirect z celem w katalogu systemowym
 *     (~/.ssh, C:\Windows, Program Files, /etc, ~/.claude/settings*.json)
 *
 * Allow (świadomie): git stash, git restore, git commit --no-verify, find -delete,
 * rm -rf wewnątrz repo, każda inna mutacja poza repo — git odzyska to, co w repo,
 * a poza repo pilnujemy tylko katalogów systemowych i sekretów (sensitive-files-guard).
 *
 * Kontrakt: Claude Code (`hookSpecificOutput.permissionDecision`). Cursor dostaje
 * tłumaczenie z invoke-hook.js --to cursor. Wejście: `.tool_input.command` albo `.command`.
 */
import { readFileSync } from "node:fs";
import { homedir } from "node:os";

const emit = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};
const deny = (reason) => emit("deny", `git-guard: ${reason}`);
const allow = () => emit("allow", "git-guard: brak wzorca destrukcyjnego");

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
  // Nieczytelny payload: nie wiemy, co byśmy przepuścili. Fail-closed.
  deny("nieczytelny payload hooka");
}

const command = String(payload.command || (payload.tool_input || {}).command || "");
if (!command.trim()) allow();

// Jedna spacja między tokenami — wzorce niżej zakładają `[ ]`, nie `\s+`.
const collapse = (text) => text.replace(/[\r\n\t]+/g, " ").replace(/ {2,}/g, " ").trim();
// Powłoka czytająca heredoc wykonuje jego treść, nawet przy `<<'EOF'`.
const SHELL_WORD = /(^|[\s;&|(])(bash|sh|zsh|dash|ksh|ssh|eval)(\s|$)/;

// Treść, której bash nie wykonuje, to dane (#206): ciało heredoca z cytowanym
// ogranicznikiem i pojedyncze apostrofy. Dlatego wzorce komend gita liczymy na `code`.
// `cmd` (bez ciała heredoca) zostaje dla celów mutacji: ścieżka w apostrofach to dalej
// ścieżka. Skrypty `bash -c '…'` / `eval '…'` są wykonywane — dokładamy je do `code`.
const commandNoHeredoc = stripHeredocs(command);
const code = collapse([commandNoHeredoc, ...shellScripts(commandNoHeredoc)].map(stripSingleQuotes).join(" ; "));
const cmd = collapse(commandNoHeredoc);
const has = (re) => new RegExp(re, "i").test(cmd);

// Granica tokenu komendy: początek, spacja albo separator shella. `rtk git push`
// też łapie — prefiks rtk jest przed `git`, nie w środku.
const B = "(^|[ ;&|(])";

// Usuń ciało heredoca z cytowanym ogranicznikiem (`<<'EOF'`, `<<"EOF"`, `<<-'EOF'`),
// gdy nie czyta go powłoka — bash nie wykonuje go jako komend (#206). Ciało bez
// cytatu zostaje, bo bash wykonuje w nim `$( … )` i backticki; apostrofy w nim to
// zwykłe znaki, więc je gasimy. `<<` liczymy tylko poza cudzysłowami.
function stripHeredocs(text) {
  const HEREDOC = /^<<(-?)[ \t]*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\2/;
  let out = "";
  let quote = "";
  let lineStart = 0;
  let pending = [];
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (quote) {
      out += c;
      if (c === "\\" && quote !== "'" && i + 1 < text.length) {
        out += text[i + 1];
        i += 2;
        continue;
      }
      if (c === quote.slice(-1)) quote = "";
      i += 1;
      continue;
    }
    if (c === "\\" && i + 1 < text.length) {
      out += text.slice(i, i + 2);
      i += 2;
      continue;
    }
    if (c === "$" && text[i + 1] === "'") {
      quote = "$'";
      out += "$'";
      i += 2;
      continue;
    }
    if (c === "'" || c === '"') {
      quote = c;
      out += c;
      i += 1;
      continue;
    }
    const h = text.startsWith("<<", i) && text[i + 2] !== "<" ? HEREDOC.exec(text.slice(i)) : null;
    if (h) {
      const lineEnd = text.indexOf("\n", i);
      const line = text.slice(lineStart, lineEnd < 0 ? text.length : lineEnd);
      pending.push({ tabs: h[1] === "-", delim: h[3], quoted: h[2] !== "", shell: SHELL_WORD.test(line) });
      out += h[0];
      i += h[0].length;
      continue;
    }
    out += c;
    i += 1;
    if (c !== "\n") continue;
    for (const p of pending) {
      while (i < text.length) {
        const end = text.indexOf("\n", i);
        const next = end < 0 ? text.length : end + 1;
        const line = text.slice(i, next);
        if (p.shell) out += line;
        else if (!p.quoted) out += line.replace(/['"]/g, " ");
        i = next;
        const bare = line.replace(/\r?\n$/, "");
        if ((p.tabs ? bare.replace(/^\t+/, "") : bare) === p.delim) break;
      }
    }
    pending = [];
    lineStart = i;
  }
  return out;
}

// Skrypty przekazane powłoce w apostrofach albo cudzysłowach (`bash -c '…'`,
// `eval "…"`) — wykonywane, więc sprawdzamy je jak zwykłą komendę.
function shellScripts(text) {
  const re = /(?:^|[\s;&|(])(?:(?:ba|z|da|k)?sh(?:\s+-[A-Za-z]+)*\s+-[A-Za-z]*c[A-Za-z]*|eval)\s+(?:'([^']*)'|"((?:[^"\\]|\\.)*)")/g;
  return [...text.matchAll(re)].map((m) => m[1] ?? m[2]);
}

// Zamień treść pojedynczych apostrofów (także `$'…'`) na spację — bash nie wykonuje
// w nich komend ani podstawień, więc zawarty tam tekst nie jest komendą (#206).
// Wyjątek: pojedyncze słowo (`'master'`) to zwykły argument — zostaje bez apostrofów,
// żeby `git push origin 'master'` dalej był pushem na master.
// Podwójne cudzysłowy zostają: bash wykonuje w nich `$( … )` i backticki.
function stripSingleQuotes(text) {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '"') {
      let j = i + 1;
      while (j < text.length && text[j] !== '"') j += text[j] === "\\" ? 2 : 1;
      out += text.slice(i, j + 1);
      i = j + 1;
      continue;
    }
    if (c === "$" && text[i + 1] === "'") {
      let j = i + 2;
      while (j < text.length && text[j] !== "'") j += text[j] === "\\" ? 2 : 1;
      out += " ";
      i = j + 1;
      continue;
    }
    if (c === "'") {
      let j = text.indexOf("'", i + 1);
      if (j < 0) j = text.length;
      const inner = text.slice(i + 1, j);
      out += /^[A-Za-z0-9_.\/:@+=,-]*$/.test(inner) ? inner : " ";
      i = j + 1;
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

// --- git push ----------------------------------------------------------------

// Reguły push sprawdzamy per segment komendy — `git log origin/master` albo
// `rm -f` obok pusha na feature branch to nie push na master ani force.
const segments = code.split(/&&|\|\||[;&|()]/).map((s) => s.trim());

function targetsProtectedRef(has) {
  const checks = [
    "origin[ ]+\\+?(main|master|dev)([ ]|$|:)",
    "origin/\\+?(main|master|dev)([ ]|$|:)",
    "upstream[ ]+\\+?(main|master|dev)([ ]|$|:)",
    "(^|[ ])\\+(main|master|dev)([ ]|$|:)",
    "(^|[ ])\\+refs/heads/(main|master|dev)([ ]|$|:)",
    "HEAD:\\+?(main|master|dev)([ ]|$)",
    "\\+[^ ]+:(main|master|dev)([ ]|$)",
    "refs/heads/\\+?(main|master|dev)([ ]|$|:)",
    "[^/+]:(main|master|dev)([ ]|$)",
    // `git push main` / `git push <remote-or-url> main` — ostatni refspec.
    "git[ ]+push([ ]+-[^ ]+)*[ ]+\\+?(main|master)[ ]*$",
    "git[ ]+push([ ]+-[^ ]+)*[ ]+[^ ]+[ ]+\\+?(main|master)[ ]*$",
    // `dev` jako ostatni refspec tylko po origin/upstream albo URL — gołe
    // `git push dev` to remote o nazwie dev, nie branch.
    "git[ ]+push([ ]+-[^ ]+)*[ ]+(origin|upstream)[ ]+\\+?dev[ ]*$",
    "git[ ]+push([ ]+-[^ ]+)*[ ]+[^ ]+[/:][^ ]*[ ]+\\+?dev[ ]*$",
  ];
  return checks.some(has);
}

for (const seg of segments) {
  const hasIn = (re) => new RegExp(re, "i").test(seg);
  if (!hasIn(`${B}git[ ]+push([ ]|$)`) || !targetsProtectedRef(hasIn)) continue;
  const isForcePush =
    hasIn("--force([ =]|$)|--force-with-lease") ||
    hasIn("(^|[ ])-f([ ]|$)") ||
    // Plus-refspec musi być osobnym tokenem — URL git+https:// nie jest force.
    hasIn("(^|[ ])\\+[A-Za-z0-9_./:@-]+");
  deny(isForcePush ? "force push na main/master/dev" : "push na main/master/dev — otwórz PR z feature brancha");
}

// --- git: nieodwracalne ---------------------------------------------------------

const hasCode = (re) => new RegExp(re, "i").test(code);
if (hasCode(`${B}git[ ]+reset[ ]+--hard`)) deny("git reset --hard — nieodwracalne, użyj git stash albo nowego brancha");
if (hasCode(`${B}git[ ]+clean[ ].*-[a-zA-Z]*f`)) deny("git clean -f — kasuje nieśledzone pliki bez odzysku");
// Wielkość litery ma znaczenie: -d kasuje tylko zmergowane, -D wszystko.
if (new RegExp(`${B}git[ ]+branch([ ]+[^ ]+)*[ ]+-D([ ]|$)`).test(code)) deny("git branch -D — użyj -d (tylko zmergowane)");
if (hasCode(`${B}git[ ]+checkout[ ]+([^ ]+[ ]+)*(\\.|--)([ ]|$)`)) {
  deny("git checkout . / checkout -- <ścieżka> — kasuje niezacommitowane zmiany; użyj git stash");
}

// --- rm rekursywne na szerokiej ścieżce -------------------------------------------

function broadPath() {
  return (
    has("(\\.\\.|/home/|/Users/|[$]HOME|~/)") ||
    has("[A-Za-z]:[\\\\/]+(Users|Windows|Program)") ||
    has("[ ][A-Za-z]:[\\\\/]*[ ]*$") ||
    has("[ ]/[ ]*$")
  );
}
if (has(`${B}rm[ ]+-[a-zA-Z]*r`) && broadPath()) {
  deny("rekursywne kasowanie na szerokiej ścieżce (katalog domowy, dysk, ..)");
}

// --- mutacje w katalogach systemowych -----------------------------------------------

const MUTATING = `${B}(rm|mv|cp|install|ln|dd|shred|truncate|touch|mkdir|rmdir|chmod|chown|chgrp|tee|unlink)([ ]|$)`;
const mutates = has(MUTATING) || has(`${B}sed[ ]+(-[a-zA-Z]*i|--in-place)`) || has(">[ ]*[~/A-Za-z]");

if (mutates) {
  const home = (process.env.HOME || process.env.USERPROFILE || homedir() || "").replace(/\\/g, "/");
  const fold = (p) => (process.platform === "win32" ? p.toLowerCase() : p);
  const norm = (p) => {
    let s = p.replace(/^["']|["']$/g, "").replace(/\\/g, "/");
    if (s.startsWith("~")) s = home + s.slice(1);
    s = s.replace(/^\$HOME/, home).replace(/^\$\{HOME\}/, home);
    return fold(s.replace(/\/+$/, ""));
  };
  const winRoot = (process.env.SystemDrive || "C:").replace(/\\/g, "/");
  const protectedPrefixes = [
    `${home}/.ssh`,
    `${home}/.claude/settings.json`,
    `${home}/.claude/settings.local.json`,
    "/etc",
    `${winRoot}/windows`,
    `${winRoot}/program files`,
    `${winRoot}/program files (x86)`,
    (process.env.ProgramFiles || "").replace(/\\/g, "/"),
    (process.env["ProgramFiles(x86)"] || "").replace(/\\/g, "/"),
    (process.env.SystemRoot || "").replace(/\\/g, "/"),
  ]
    .filter(Boolean)
    .map(fold);

  for (const tok of cmd.split(" ")) {
    if (tok.startsWith("-")) continue;
    // Tylko tokeny wyglądające na ścieżkę — reszta to argumenty, nie cele.
    if (!/^["']?([~/]|[A-Za-z]:[\\/]|\$\{?HOME)/.test(tok)) continue;
    const t = norm(tok);
    if (protectedPrefixes.some((p) => t === p || t.startsWith(p + "/"))) {
      deny(`zmiana w katalogu systemowym: ${tok}`);
    }
  }
}

allow();
