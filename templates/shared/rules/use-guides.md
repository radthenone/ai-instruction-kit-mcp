# Warstwy AI + instruction-kit

## Fundament

| Zadanie | Źródło |
|---------|--------|
| Backend / frontend / arch / infra | MCP `project-guides` → `get_bundle` |
| Porty, Taskfile, Docker | MCP `get_overlay` / `.ai/project.md` |
| codegen | MCP `get_codegen` / `codegen:` w `.ai/project.profile.yaml` |
| Docs bibliotek | Context7 (user MCP) |
| Review stacku | **minimalny zestaw** — zob. `code-review` (nie wszystkie `/review-*`) |
| Dwa okna | `/subagent-backend` ↔ `/subagent-frontend` (cross API+UI) |
| Nauka / niepewna koncepcja **przed** kodem | `/teacher-backend`, `/teacher-frontend`, `/teacher-architecture` (readonly — uczą, nie piszą) |
| Przed pushem | `/review-bugbot` + opc. stack + hooki `gate-*` |
| Branch / PR | `/git-start`, `/git-check`, `/git-commit`, `/git-end` + `git-branch-pr` |
| Język prozy | MCP `get_language` / `--language pl\|en` |
| Worktree / finisz | Superpowers (opc.) na branchu z `/git-start` |
| PR → CI green | Autopilot po `/git-end` |

Moduły: Tiery z `.ai/project.profile.yaml` (backend/web/mobile) + overlay `.ai/project.md`.  

Profil w workspace to jedyne źródło wyborów (ADR-0007); `--preset` / `--profile` są ignorowane.

**Wszystkie agenty:** `AGENTS.md` + reguła git-branch-pr. Po PR — Autopilot; nie dubluj TDD Matt+Superpowers.

## Grill / TDD — kiedy

| Sytuacja | Działanie |
|----------|-----------|
| Niejasny scope, wiele ścieżek, trade-offy | `/grill-me` **przed** kodem |
| Oczywisty bugfix / 1–2 pliki | **Bez** grilla → `/git-start` |
| Logika biznesowa, edge case’y | opc. `/tdd` (jeden path: Matt *albo* Superpowers TDD) |

## Niska pewność (wszystkie agenty)

Auth, ACL, billing, migracje, concurrency, brak dowodu w repo → **zapytaj użytkownika**. Nie „naprawiaj na ślepo”. Finding bez pewności = pytanie, nie fakt.

## Proces i meta (poza kitem — nie zastępują MCP)

| Warstwa | Przykład | Kiedy |
|---------|----------|-------|
| Proces | mattpocock `/grill-me`, `/tdd` | niejasny scope; red-green |
| Meta | Superpowers worktree / finishing / debug | izolacja, domknięcie brancha |
| PR loop | Autopilot | CI + komentarze aż merge-ready |

Priorytet: użytkownik → overlay+MCP → `/git-*`+review → Matt → Superpowers → Autopilot.  
TDD: jeden path (preferuj Matt `/tdd`).
