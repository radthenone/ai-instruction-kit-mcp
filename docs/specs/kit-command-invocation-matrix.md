# Matryca wywołań komend kita

Stan na 2026-11-25. Test T3 na worktree PR #560 (`fix/534-kit-skill-prefix`). VS Code sprawdzony ręcznie przez autora 2026-11-25. Powiązane: #522, #534.

| Klient | Ścieżka skilla w repo | Forma natywna (#534) | Forma w T3 | Status |
|---|---|---|---|---|
| Codex | `.codex/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md` | `$kit-ai:git-start` | `/skill:kit-ai:git-start` | T3: działa (test `--help`). Natywnie: działa. |
| Antigravity | `.agents/skills/<name>/SKILL.md` | `/kit-ai:git-start` | `/skill:kit-ai:git-start` | T3: działa (test `--help`). Natywnie: działa. |
| VS Code (Copilot) | `.github/prompts/<name>.prompt.md` | `/git-start` (bez prefiksu, `name_prefix: ""`) | — (VS Code nie jest klientem T3) | Natywnie: działa. `name: kit-ai:probe` z dwukropkiem przyjęty. Tryb Local działa. |

## Zasady

- Prefiks w `name:` SKILL.md dla Codex i Antigravity pochodzi z `name_prefix` w `command_prefixes` w `manifest.yaml` (`kit-ai:`, #534). Nazwa katalogu zostaje bez dwukropka.
- Skille spoza kita (np. `/tdd`, `/grill-me`, `/code-review`) nie dostają prefiksu.
- Przed #534 forma w T3 bez prefiksu: `/skill:git-start` (źródło w T3: Project).

## Stan

- Forma w T3 `/skill:kit-ai:git-start` działa w Codex i Antigravity (test `--help`, PR #560).
- Formy natywne `$kit-ai:git-start` (Codex) i `/kit-ai:git-start` (Antigravity): działają (kryterium ręczne #534 spełnione).
- VS Code: komendy kita działają jako `/git-start`. Pole `name:` przyjmuje dwukropek, więc prefiks `kit-ai:` jest możliwy. Kit go dziś nie nadaje (`vscode.name_prefix: ""` w `manifest.yaml`). Ewentualna zmiana: osobne issue.
- #522 zamknięte: wszystkie trzy klienty sprawdzone.
