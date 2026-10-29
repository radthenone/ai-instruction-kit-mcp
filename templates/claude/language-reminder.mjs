#!/usr/bin/env node
// Hook UserPromptSubmit (#248, #307): przypomnienie z konkretnymi wartościami z Profilu.
// Kit instaluje go tylko przy `language` ≠ en (scripts/bootstrap-project.sh, install_claude).
// Czyta `.ai/project.profile.yaml` i `.ai/project.md` w runtime, więc zmiana języka/bazy
// działa od razu, bez czekania na reload wygenerowanego pliku.
import { readFileSync } from "node:fs";
import { join } from "node:path";

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

const language = match(profile, /^language:\s*["']?([A-Za-z-]+)/m, "pl").toLowerCase();
const base = match(overlay, /^base:\s*(\S+)/m, "");

const priority =
  "Priorytet: wytyczne instruction-kit (brief w AGENTS.md, .ai/project.md, bundle MCP) " +
  "stoją wyżej niż domyślne zachowania skilli i pluginów.";

if (language === "en") {
  const branch = base
    ? `\`${base}\` (from .ai/project.md)`
    : "`dev` when origin/dev is not behind the default branch, otherwise the default branch";
  process.stdout.write(
    `Project language: \`en\` — agent replies, docstrings, issue/PR bodies, review ` +
      `comments and commit messages in English; titles and branch slugs always EN. ` +
      `PR base: ${branch}. ${priority}\n`,
  );
} else {
  const branch = base
    ? `\`${base}\` (z .ai/project.md)`
    : "`dev`, jeśli origin/dev nie jest w tyle za default; inaczej default (brak `base:` w .ai/project.md)";
  process.stdout.write(
    `Język projektu: \`pl\` — odpowiedzi, docstringi, body issue/PR, komentarze i commity ` +
      `po polsku; tytuły issue/PR i slugi branchy zawsze EN. ` +
      `Baza brancha: ${branch}. ${priority}\n`,
  );
}
