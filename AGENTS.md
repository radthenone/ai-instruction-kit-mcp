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
[/grill-me] → /git-start → [worktree?] → kod [+/tdd]
  → [/git-check] → /git-commit → /review-bugbot → /git-end | finishing→PR → Autopilot → merge
```

- **`/git-start` / `/git-check` / `/git-commit` / `/git-end`** — issue, sync, Conventional commit(s), push+PR.  

- **Superpowers worktree** — opcjonalna izolacja *na już nazwanym* branchu.  
- **Finishing** — lokalne testy OK → opcja PR (zamiast lub obok `/git-end`).  
- **Autopilot** — po PR: CI/komentarze aż merge-ready (bez auto-merge).

Chronione: `main` / `master` / `dev`.

## Flow jednej zmiany

1. (Opc.) `/grill-me`  
2. `/git-start` — issue + branch  
3. (Opc.) Superpowers worktree  
4. MCP `get_bundle` + `get_overlay` (+ `get_language`)  
5. Implementacja (+ opc. `/tdd`)  
6. (Opc.) `/git-check` — gdy scope/diff rozjechał się z issue  
7. `/git-commit` — Conventional Commit(s) z lokalnego diffa  
8. `/review-*` + `/review-bugbot`  
9. `/git-end` **lub** Superpowers finishing → PR  
10. (Opc.) Autopilot → CI green → merge  

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
| `/grill-me`, `/tdd`, … | proces | mattpocock |
| Superpowers / Autopilot | worktree, finishing, CI loop | plugin / skills Cursor |

## Code review

Przed `git push`: `/review-bugbot` (auth/płatności: `/review-security`).  
Hooki: `gate-push.sh` (ask), `gate-destructive.sh` (deny force na main/master/dev / reset --hard).
Bootstrap: `scripts/bootstrap-project.sh`.
