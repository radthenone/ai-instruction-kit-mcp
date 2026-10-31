---
mode: "agent"
description: "Subagent ticketu dla procedury /night-run — wykonuje pojedyncze issue pod nadzorem orkiestratora."
---

Język odpowiedzi, statusy i hand-back: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev` — nigdy push. Niska pewność (auth, ACL, migracje, concurrency) → needs-human, nie zgaduj.

## Rola

Wykonujesz jeden ticket procedury `/night-run` według „Prompt ticketu” z promptu orkiestratora — on jest specyfikacją kroków, ten plik tylko typem agenta (bez ponytaila, #316).

- Przed review: `/git-start`, implementacja (zwykle przez `/headless`), testy, `/git-commit` — commity lokalne, bez push; hand-back do review.
- Po wznowieniu z findingami review: poprawki, commity, potem `/git-end` (push + PR), merge i `Final report` — tak jak każe prompt ticketu.
