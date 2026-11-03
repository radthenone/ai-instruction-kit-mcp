#!/usr/bin/env node
// Hook UserPromptSubmit (#248, #307, #324): przypomnienie z konkretnymi wartościami z Profilu.
// Kit instaluje go tylko przy `language` ≠ en (scripts/bootstrap-project.sh, install_claude).
// Czyta `.ai/project.profile.yaml` i `.ai/project.md` w runtime, więc zmiana języka/bazy
// działa od razu, bez czekania na reload wygenerowanego pliku.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { detectHostProfile } from "./host-profile.mjs";

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();

function read(rel) {
  try {
    return readFileSync(join(root, rel), "utf8");
  } catch {
    return "";
  }
}

const profile = read(".ai/project.profile.yaml");
const overlay = read(".ai/project.md");

function match(text, pattern, fallback) {
  const found = text.match(pattern);
  return found && found[1] ? found[1] : fallback;
}

// `[ \t]*` zamiast `\s*`: puste `base:` nie może złapać treści następnej linii.
const rawLanguage = match(profile, /^language:[ \t]*["']?([A-Za-z_-]+)/m, "pl").toLowerCase();
// Ta sama normalizacja co resolver (`normalize_language`): en/eng/english/en-* → en, reszta → pl.
const language = ["en", "eng", "english"].includes(rawLanguage.split(/[-_]/)[0]) ? "en" : "pl";
const base = match(overlay, /^base:[ \t]*(\S+)[ \t]*$/m, "");

// Wspólna detekcja hosta (ADR-0011) — ta sama reguła co w server-guard.
const host = detectHostProfile();

const priority =
  "Priorytet: wytyczne instruction-kit (brief w AGENTS.md, .ai/project.md, bundle MCP) " +
  "stoją wyżej niż domyślne zachowania skilli i pluginów. " +
  "Ponytail i podobne pluginy stylu kodu dotyczą kodu aplikacji, nie procedur kita ani edycji " +
  "plików kita i konfiguracji projektu (.ai/, AGENTS.md, Profil, templates/, .claude/). " +
  "Prośba o skrót („najkrótszą drogą”, „szybko”, „uprość”) nie zwalnia z procedur kita: " +
  "commit przez /git-commit, review przed push, zmiany w .ai/project.md, Profilu, AGENTS.md " +
  "i BUGBOT.md przez /kit-project-edit z podglądem, nie bezpośrednią edycją.";

const rulesPl =
  "Klasyfikacja zadań i reguły MCP (#307, #324): " +
  "Zadanie kodowe (tworzenie, edycja lub debug plików w src/, tests/, templates/, modules/; " +
  "implementacja, testy, refactor, pytanie o zachowanie kodu do zmiany) lub proceduralne " +
  "(każdy slash command kita: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, " +
  "oraz każda czynność zapisu na GitHub): wymóg wywołania get_overlay przed pierwszą edycją " +
  "(a get_bundle gdy brief wskazuje moduł); w wątpliwości wywołaj get_overlay (koszt mały, błędny fix bez overlay kosztuje dużo). " +
  "Pytania o język, bazę, Tiery i rozmowa bez zmian plików — bez wywołań MCP (#307). " +
  "Docstringi w formacie repo (Args/Returns, po polsku). " +
  "Na hoście VPS zakaz instalacji pakietów i buildów poza lockfile-only (#317, np. uv lock --no-build, npm install --package-lock-only --ignore-scripts).";

const rulesEn =
  "Task classification and MCP rules (#307, #324): " +
  "Coding task (create, edit or debug files in src/, tests/, templates/, modules/; " +
  "implementation, tests, refactor, questions on code behavior to change) or procedural task " +
  "(any kit slash command: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, " +
  "and any GitHub write action): require calling get_overlay before first edit " +
  "(and get_bundle when brief points to module); when in doubt call get_overlay (small cost, wrong fix without overlay costs a lot). " +
  "Questions about language, base, Tiers and conversation without file edits — no MCP calls (#307). " +
  "Docstrings in repo format (Args/Returns, in English). " +
  "On VPS host package installs and builds are denied except lockfile-only (#317, e.g. uv lock --no-build, npm install --package-lock-only --ignore-scripts).";

if (language === "en") {
  const branch = base
    ? `\`${base}\` (from .ai/project.md)`
    : "`dev` when origin/dev is not behind the default branch, otherwise the default branch";
  process.stdout.write(
    `Project language: \`en\` — agent replies, docstrings in repo format (Args/Returns, in English), issue/PR bodies, review ` +
      `comments and commit messages in English; titles and branch slugs always EN. ` +
      `PR base: ${branch}. Host: \`${host}\`. ${priority} ${rulesEn}\n`,
  );
} else {
  const branch = base
    ? `\`${base}\` (z .ai/project.md)`
    : "`dev`, jeśli origin/dev nie jest w tyle za default; inaczej default (brak `base:` w .ai/project.md)";
  process.stdout.write(
    `Język projektu: \`pl\` — odpowiedzi po polsku, niezależnie od języka wiadomości (także krótkie „halo”/„ok”, wklejki EN/RU); ` +
      `reguła stoi wyżej niż reguły językowe pluginów stylu („Preserve user's dominant language” z caveman i podobnych). ` +
      `Docstringi w formacie repo (Args/Returns, po polsku), body issue/PR, komentarze i commity ` +
      `po polsku; tytuły issue/PR i slugi branchy zawsze EN. ` +
      `Baza brancha: ${branch}. Host: \`${host}\`. ${priority} ${rulesPl}\n`,
  );
}
