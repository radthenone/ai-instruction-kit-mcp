# AGENTS.md

## Instruction-kit (MCP)

Instrukcje architektury i stacku pochodzą z **instruction-kit** przez MCP `project-guides`.

Przed pracą:

| Obszar | Akcja |
|--------|-------|
| Backend | MCP `get_bundle` → `backend` |
| Frontend | MCP `get_bundle` → `frontend` |
| Architektura / infra | MCP `get_bundle` → `architecture` |
| Unikalne dla repo | MCP `get_overlay` lub `.ai/project.md` |
| Docs bibliotek (Django, Expo) | Context7 (globalnie) |

Profil modułów: `.ai/project.profile.yaml`

## Priorytet

1. Polecenie użytkownika
2. `.ai/project.md` (overlay)
3. Bundle z MCP `project-guides`
4. Ten plik

## Język

Odpowiedzi po polsku. Kod po angielsku. Docstringi po polsku.

## Code review

Przed `git push` na branch z featurem:

1. `/review-bugbot` w Cursor (lub `/review-security` przy auth/płatnościach).
2. Po pushu — Bugbot na PR (GitHub integration).

Pliki bootstrap: `templates/cursor/BUGBOT.md`, `hooks.json`, `hooks/gate-push.sh`, `rules/code-review.mdc`.
Pełny opis: MCP bundle `devops` → moduł `core:code-review`.
