#!/usr/bin/env node
/**
 * Guardrail na zapisy plikow (PreToolUse: Edit|Write|MultiEdit|NotebookEdit).
 *
 * Polityka — rozstrzyga wylacznie o LOKALIZACJI zapisu:
 *   - wewnatrz repo biezacego projektu  -> allow, zawsze
 *   - poza nim                          -> ask, zawsze (inne repo, katalog domowy,
 *     konfiguracja systemowa: git tego nie odzyska)
 *   - katalog tymczasowy agenta         -> allow (z zalozenia jednorazowy)
 *
 * Progu na rozmiar zmiany tu nie ma i nie powinno byc. Hook widzi tylko payload
 * narzedzia, wiec kazdy prog na liczbe usunietych linii jest zgadywaniem, co
 * znaczy "duza zmiana" — placi sie za to promptami przy zwyklej pracy w repo,
 * a w repo od cofania jest git. Poza repo cofac nie ma czym i tam bramka stoi.
 *
 * Kontrakt: Claude Code (PreToolUse). Klienci o innym ksztalcie wyjscia dostaja
 * tlumaczenie w invoke-hook.js — patrz templates/shared/guards/invoke-hook.js.
 * Cursor nie jest tu obslugiwany: ma tylko `afterFileEdit`, czyli zdarzenie PO
 * zapisie, wiec nie da sie zablokowac operacji przed wykonaniem.
 */
import { existsSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";

const decide = (permissionDecision, permissionDecisionReason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision, permissionDecisionReason },
    }) + "\n"
  );
  process.exit(0);
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

// Windows nie rozroznia wielkosci liter w sciezkach: "m:\repo" i "M:\repo" to
// ten sam katalog, a klient potrafi podac raz tak, raz tak. Porownanie bajt po
// bajcie robilo z zapisu we wlasnym repo "zapis poza projektem" i pytalo przy
// kazdej edycji. Tylko win32 — na POSIX /Home/x naprawde nie jest /home/x,
// a case-insensitivity macOS zalezy od wolumenu, wiec zakladac jej nie wolno.
const caseFold = (p) => (process.platform === "win32" ? p.toLowerCase() : p);

const under = (file, root) => {
  const f = caseFold(file);
  const r = caseFold(resolve(root));
  return f === r || f.startsWith(r + sep);
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

    decide("allow", "zapis w obrebie projektu");
  } catch (err) {
    // Nieoczekiwana awaria nie moze po cichu poszerzyc dostepu.
    decide("ask", `gate-file-writes: blad hooka (${err.message}) — potwierdz recznie`);
  }
});
