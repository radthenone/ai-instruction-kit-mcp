#!/usr/bin/env node
/**
 * Guardrail na zapisy plikow (PreToolUse: Edit|Write|MultiEdit|NotebookEdit).
 *
 * Polityka:
 *   - wewnatrz repo biezacego projektu  -> allow, chyba ze edycja usuwa duzo linii
 *     netto -> ask, z nazwa pliku i liczba linii
 *   - poza nim                          -> ask, zawsze (inne repo, katalog domowy,
 *     konfiguracja systemowa: git tego nie odzyska)
 *   - katalog tymczasowy agenta         -> allow (z zalozenia jednorazowy)
 *
 * Hook nie umie ocenic, czy zmiana jest "duza" w sensie znaczeniowym — widzi tylko
 * payload narzedzia. Liczba usunietych linii netto jest mierzalnym przyblizeniem.
 * Prog: GUARD_DELETE_LINE_THRESHOLD (domyslnie 30).
 *
 * Kontrakt: Claude Code (PreToolUse). Klienci o innym ksztalcie wyjscia dostaja
 * tlumaczenie w invoke-hook.js — patrz templates/shared/guards/invoke-hook.js.
 * Cursor nie jest tu obslugiwany: ma tylko `afterFileEdit`, czyli zdarzenie PO
 * zapisie, wiec nie da sie zablokowac operacji przed wykonaniem.
 */
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";

const THRESHOLD = Number(process.env.GUARD_DELETE_LINE_THRESHOLD || 30);

const decide = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
};

const lines = (s) => (s ? String(s).split("\n").length : 0);

function repoRoot(from) {
  let dir = from;
  for (;;) {
    if (existsSync(join(dir, ".git"))) return dir;
    const up = dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
}

const under = (file, root) => {
  const r = resolve(root);
  return file === r || file.startsWith(r + sep);
};

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  let payload;
  try {
    payload = JSON.parse(input || "{}");
  } catch {
    decide("ask", "gate-file-writes: nie dalo sie odczytac payloadu hooka");
  }

  try {
    const tool = payload.tool_name || "";
    const toolInput = payload.tool_input || {};
    const raw = toolInput.file_path || toolInput.notebook_path;
    if (!raw) decide("allow", "brak sciezki w tool_input");

    // Payload potrafi uzywac "/" nawet tam, gdzie path.sep to "\" — normalizuj.
    const file = resolve(raw);

    // Katalog tymczasowy agenta: pliki robocze, nie warte promptu.
    if (/\/(tmp|temp)\/claude\//i.test(file.split(sep).join("/"))) {
      decide("allow", "katalog tymczasowy agenta");
    }

    const cwd = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const project = repoRoot(resolve(cwd)) || resolve(cwd);

    if (!under(file, project)) {
      decide("ask", `poza projektem (${project}): zapis do ${file}. Git tego nie odzyska — potwierdz swiadomie.`);
    }

    // Ile linii netto ubywa po tej edycji?
    let removed = 0;
    if (tool === "Edit") {
      removed = lines(toolInput.old_string) - lines(toolInput.new_string);
    } else if (tool === "MultiEdit") {
      for (const edit of toolInput.edits || []) {
        removed += lines(edit.old_string) - lines(edit.new_string);
      }
    } else if (tool === "Write") {
      if (!existsSync(file) || statSync(file).isDirectory()) {
        decide("allow", "nowy plik w projekcie");
      }
      removed = lines(readFileSync(file, "utf8")) - lines(toolInput.content);
    } else if (tool === "NotebookEdit") {
      if (toolInput.edit_mode === "delete") {
        decide("ask", `usuniecie komorki notebooka: ${file}`);
      }
    }

    if (removed >= THRESHOLD) {
      decide(
        "ask",
        `usuwa ${removed} linii netto z ${file} (prog ${THRESHOLD}). Wyjasnij co i dlaczego przed potwierdzeniem.`
      );
    }

    decide("allow", "zmiana w projekcie ponizej progu");
  } catch (err) {
    // Nieoczekiwana awaria nie moze po cichu poszerzyc dostepu.
    decide("ask", `gate-file-writes: blad hooka (${err.message}) — potwierdz recznie`);
  }
});
