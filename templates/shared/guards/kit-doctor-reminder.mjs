#!/usr/bin/env node
/**
 * Hook SessionStart (#269): przypomnienie o otwartej partii doctora.
 *
 * `kit-ai reload` zapisuje zgłoszenia do naprawy w `.ai/.kit-doctor.json`, a tryb C
 * `/kit-project-edit` po naprawie plik usuwa. Dopóki plik jest, agent dostaje raz na
 * sesję (SessionStart) jedną linię kontekstu z poleceniem trybu C. Bez pliku — cisza.
 *
 * Katalog projektu: `CLAUDE_PROJECT_DIR` (Claude Code), potem `cwd` z wejścia hooka
 * (Codex, Copilot), na końcu katalog procesu. Format wyjścia jak w Claude Code.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

let cwd = "";
try {
  cwd = JSON.parse(readFileSync(0, "utf8") || "{}").cwd || "";
} catch {
  cwd = "";
}
const root = process.env.CLAUDE_PROJECT_DIR || cwd || process.cwd();

if (!existsSync(join(root, ".ai", ".kit-doctor.json"))) process.exit(0);

const context =
  "kit-doctor: otwarta partia zgłoszeń doctora w `.ai/.kit-doctor.json` → " +
  'uruchom `/kit-project-edit "napraw zgłoszenia doctora"` (po naprawie plik znika).';

process.stdout.write(
  JSON.stringify({ hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: context } }) + "\n"
);
