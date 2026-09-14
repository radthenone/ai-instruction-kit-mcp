#!/usr/bin/env node
/**
 * Guard: destrukcyjne komendy gita i shella (PreToolUse: Bash).
 *
 * Polityka zna tylko dwie odpowiedzi — allow albo deny. Nigdy `ask`: w auto mode
 * `ask` z hooka blokuje tak samo jak prompt, wiec bramka, ktora pyta, nie jest
 * automatyczna. Co nie jest na liscie deny, przechodzi. ADR 0006.
 *
 * Deny:
 *   - git reset --hard
 *   - git clean z flaga -f
 *   - force push na main/master/dev (--force, --force-with-lease, -f, +refspec)
 *   - git push (bez force) na main/master/dev — workflow to PR
 *   - git branch -D
 *   - git checkout .  /  git checkout -- <cokolwiek>
 *   - rekursywne rm na szerokiej sciezce (~, /, .., katalog domowy, goly dysk)
 *   - mutacja, sed -i albo redirect z celem w katalogu systemowym
 *     (~/.ssh, C:\Windows, Program Files, /etc, ~/.claude/settings*.json)
 *
 * Allow (swiadomie): git stash, git restore, git commit --no-verify, find -delete,
 * rm -rf wewnatrz repo, kazda inna mutacja poza repo — git odzyska to, co w repo,
 * a poza repo pilnujemy tylko katalogow systemowych i sekretow (sensitive-files-guard).
 *
 * Kontrakt: Claude Code (`hookSpecificOutput.permissionDecision`). Cursor dostaje
 * tlumaczenie z invoke-hook.js --to cursor. Wejscie: `.tool_input.command` albo `.command`.
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
  // Nieczytelny payload: nie wiemy, co bysmy przepuscili. Fail-closed.
  deny("nieczytelny payload hooka");
}

const command = String(payload.command || (payload.tool_input || {}).command || "");
if (!command.trim()) allow();

// Jedna spacja miedzy tokenami — wzorce nizej zakladaja `[ ]`, nie `\s+`.
const cmd = command.replace(/[\r\n\t]+/g, " ").replace(/ {2,}/g, " ").trim();
const has = (re) => new RegExp(re, "i").test(cmd);

// Granica tokenu komendy: poczatek, spacja albo separator shella. `rtk git push`
// tez lapie — prefiks rtk jest przed `git`, nie w srodku.
const B = "(^|[ ;&|(])";

// --- git push ----------------------------------------------------------------

function targetsProtectedRef() {
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
    // `dev` jako ostatni refspec tylko po origin/upstream albo URL — gole
    // `git push dev` to remote o nazwie dev, nie branch.
    "git[ ]+push([ ]+-[^ ]+)*[ ]+(origin|upstream)[ ]+\\+?dev[ ]*$",
    "git[ ]+push([ ]+-[^ ]+)*[ ]+[^ ]+[/:][^ ]*[ ]+\\+?dev[ ]*$",
  ];
  return checks.some(has);
}

const isPush = has(`${B}git[ ]+push([ ]|$)`);
const isForcePush =
  isPush &&
  (has("--force([ =]|$)|--force-with-lease") ||
    has("(^|[ ])-f([ ]|$)") ||
    // Plus-refspec musi byc osobnym tokenem — URL git+https:// nie jest force.
    has("(^|[ ])\\+[A-Za-z0-9_./:@-]+"));

if (isPush && targetsProtectedRef()) {
  deny(isForcePush ? "force push na main/master/dev" : "push na main/master/dev — otworz PR z feature brancha");
}

// --- git: nieodwracalne ---------------------------------------------------------

if (has(`${B}git[ ]+reset[ ]+--hard`)) deny("git reset --hard — nieodwracalne, uzyj git stash albo nowego brancha");
if (has(`${B}git[ ]+clean[ ].*-[a-zA-Z]*f`)) deny("git clean -f — kasuje nieśledzone pliki bez odzysku");
// Wielkosc litery ma znaczenie: -d kasuje tylko zmergowane, -D wszystko.
if (new RegExp(`${B}git[ ]+branch([ ]+[^ ]+)*[ ]+-D([ ]|$)`).test(cmd)) deny("git branch -D — uzyj -d (tylko zmergowane)");
if (has(`${B}git[ ]+checkout[ ]+([^ ]+[ ]+)*(\\.|--)([ ]|$)`)) {
  deny("git checkout . / checkout -- <sciezka> — kasuje niezacommitowane zmiany; uzyj git stash");
}

// --- rm rekursywne na szerokiej sciezce -------------------------------------------

function broadPath() {
  return (
    has("(\\.\\.|/home/|/Users/|[$]HOME|~/)") ||
    has("[A-Za-z]:[\\\\/]+(Users|Windows|Program)") ||
    has("[ ][A-Za-z]:[\\\\/]*[ ]*$") ||
    has("[ ]/[ ]*$")
  );
}
if (has(`${B}rm[ ]+-[a-zA-Z]*r`) && broadPath()) {
  deny("rekursywne kasowanie na szerokiej sciezce (katalog domowy, dysk, ..)");
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
    // Tylko tokeny wygladajace na sciezke — reszta to argumenty, nie cele.
    if (!/^["']?([~/]|[A-Za-z]:[\\/]|\$\{?HOME)/.test(tok)) continue;
    const t = norm(tok);
    if (protectedPrefixes.some((p) => t === p || t.startsWith(p + "/"))) {
      deny(`zmiana w katalogu systemowym: ${tok}`);
    }
  }
}

allow();
