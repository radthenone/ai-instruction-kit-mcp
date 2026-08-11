# AGENTS.md

## Warstwy AI (nie mieszaj)

| Warstwa | Co | Gdzie | Po co |
|---------|-----|------|--------|
| **1. Fundament** | instruction-kit MCP + `/git-*` + `/review-*` | `.cursor/mcp.json`, `.ai/`, agents | Stack, konwencja gita, review |
| **2. Proces** | mattpocock | skills | `/grill-me`, `/tdd` — *jak* budować feature |
| **3. Meta / izolacja** | Superpowers | plugin / skills | worktree, brainstorm, debug, **finishing** branch |
| **4. PR → green** | Autopilot (Cursor) | skill Autopilot | pętla CI + komentarze na istniejącym PR |

Kit = prawda o stacku **i** nazwach branchy. Matt = proces feature. Superpowers = sesja / worktree / finisz. Autopilot = dociąganie PR. **Nie** zamieniaj kita na Matta/Superpowers.

## Instruction-kit (MCP)

| Obszar | Akcja |
|--------|-------|
| Backend / frontend / arch | `get_bundle` |
| Unikalne dla repo | `get_overlay` / `.ai/project.md` |
| Docs bibliotek | Context7 |

`--preset` w mcp.json; overlay w `.ai/project.md`; lokalny `project.profile.yaml` tylko przy forku.

## Priorytet źródeł

1. Polecenie użytkownika  
2. `.ai/project.md` + bundle MCP  
3. `/git-*` / `/review-*` / `git-branch-pr`  
4. Matt (`/grill-me`, `/tdd`)  
5. Superpowers (worktree, finishing, debug…)  
6. Autopilot (po otwarciu PR)  
7. Ten plik  

Konflikt TDD: Matt `/tdd` *albo* Superpowers TDD — nie oba. Domyślnie Matt na nowe feature’e.

## Branch / PR / Superpowers / Autopilot

Pełna reguła: `.cursor/rules/git-branch-pr.mdc`.

```text
[/grill-me gdy scope niejasny] → /git-start → [worktree?] → kod [+/tdd]
  → [/git-check] → /git-commit → /review-bugbot (+ min. stack) → /git-end | finishing→PR → Autopilot → merge
```

- **`/git-start` / `/git-check` / `/git-commit` / `/git-end`** — issue, sync, Conventional commit(s), push+PR.  
- **`/grill-me`** — tylko przy niejasnym scope / trade-offach (nie przy oczywistym fixie).  
- **`/teacher-backend` / `/teacher-frontend` / `/teacher-architecture`** — nauka **przed** kodem: koncepcja, „dlaczego tak”, opcje i koszty. Nie edytują plików; nie mylić z `/review-*` (te działają na gotowym diffie).  
- **Superpowers worktree** — opcjonalna izolacja *na już nazwanym* branchu.  
- **Finishing** — lokalne testy OK → opcja PR (zamiast lub obok `/git-end`).  
- **Autopilot** — po PR: CI/komentarze aż merge-ready (bez auto-merge).

Chronione: `main` / `master` / `dev`.

## Flow jednej zmiany

1. (Opc.) `/grill-me` — **tylko** gdy scope niejasny  
2. `/git-start` — issue + branch  
3. (Opc.) Superpowers worktree  
4. MCP `get_bundle` + `get_overlay` (+ `get_language`; odczytaj `codegen:`)  
5. Implementacja (+ opc. `/tdd`)  
6. (Opc.) `/git-check` — gdy scope/diff rozjechał się z issue  
7. `/git-commit` — Conventional Commit(s) z lokalnego diffa  
8. `/review-bugbot` + **minimalny** stack (`/review-backend` i/lub `/review-frontend`; nie wszystkie `/review-*`)  
9. `/git-end` **lub** Superpowers finishing → PR  
10. (Opc.) Autopilot → CI green → merge  

## Niska pewność

Auth, ACL, billing, migracje, concurrency, brak dowodu w repo → **zapytaj użytkownika**. Nie naprawiaj na ślepo. Finding bez pewności = pytanie, nie fakt.

## Codegen (Orval)

W overlay (`.ai/project.md` / extras) ustaw `codegen: orval` (default) \| `none` \| `graphql`.  
Docelowo też flaga MCP `--codegen` (design — jeszcze nie w CLI). Review FE/BE honorują tę wartość.  

## Język

Źródło prawdy: MCP `get_language` oraz `--language` / `GUIDES_LANGUAGE` / `language:` w profilu (bootstrap domyślnie **`pl`**).

| Element | Zawsze | Zależne od `--language` |
|---------|--------|-------------------------|
| Identyfikatory w kodzie | EN | — |
| Tytuł issue / PR / slug brancha | EN | — |
| Odpowiedzi agenta, docstringi, body issue/PR, komentarze, commity | — | `pl` albo `en` |

## Slash commands

| Prefiks | Przykłady | Źródło |
|---------|-----------|--------|
| `/compact` | **Cursor only** — alias Summarize; nie Claude/Codex | kit → `.cursor/skills/compact/` |
| `/git-*` | `/git-start`, `/git-check`, `/git-commit`, `/git-end` | kit |
| `/review-*` | `/review-backend`, `/review-bugbot` | kit + Cursor |
| `/subagent-*` | `/subagent-backend` | kit |
| `/teacher-*` | `/teacher-backend`, `/teacher-frontend`, `/teacher-architecture` | kit |
| `/grill-me`, `/tdd`, … | proces | mattpocock |
| Superpowers / Autopilot | worktree, finishing, CI loop | plugin / skills Cursor |

## Code review

Przed `git push`: `/review-bugbot` + minimalny stack (nie cały wachlarz). Auth/płatności: `/review-security`.  
Format stack review: `Severity | Location | Finding | Fix`.  
`/review-tests` = dowód że komendy przechodzą — nie drugi stylista.  
Hooki: `gate-push.sh` (ask), `gate-destructive.sh` (deny force na main/master/dev / reset --hard).
Bootstrap: `scripts/bootstrap-project.sh`.
