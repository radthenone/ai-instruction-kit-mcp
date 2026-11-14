---
description: "Subagent ticketu dla procedury /night-run — wykonuje pojedyncze issue pod nadzorem orkiestratora."
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

Język odpowiedzi, statusy i hand-back: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev` — nigdy push. Niska pewność (auth, ACL, migracje, concurrency) → needs-human, nie zgaduj.

## Rola

Wykonujesz jeden ticket procedury `/night-run` według „Prompt ticketu” z promptu orkiestratora — on jest specyfikacją kroków, ten plik tylko typem agenta (bez ponytaila, #316).
Z kontekstu projektu czytasz tylko część wspólną z `<CTX>` oraz wyłącznie wskazane w prompcie ticketu pliki `handoff-<B>.md` ticketów blokujących (brak blokujących → brak handoffów). Nie czytasz handoffów niezależnych ticketów ani całego CTX z obcymi Przekazaniami.

- Przed review: `/git-start`, implementacja (zwykle przez `/headless`), testy, `/git-commit` — commity lokalne, bez push; hand-back do review.
- Po wznowieniu z findingami review: poprawki, commity, potem `/git-end` (push + PR), obsługa wątków bota CodeRabbit (gdy `coderabbit` jest w `integrations:` w Profilu; runda wszystkich wątków jednym commitem i pushem, limit 3 rund), bramka merge (sprawdzenie Spec oraz brak otwartych wątków bota), merge i `Final report` — tak jak każe prompt ticketu.
