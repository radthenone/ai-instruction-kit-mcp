# Przekazanie sesji designu (Claude Code)

Plik instaluje kit, gdy projekt ma `claude` w `clients:` i Tier web lub mobile. Opisuje, jak
issue z etykietą `design: layout` albo `design: tokens` przechodzi przez sesję designu
w Claude Code i wraca do wspólnej ścieżki, którą implementuje dowolny klient.

## `design: layout` — nowy albo zmieniany ekran

Stan wejściowy: `design: layout` + `ready-for-human` (czeka na sesję designu).

1. Człowiek modeluje layout w artefakcie Design / panelu design systemu (Claude Design,
   claude.ai/design; zmiany z panelu ściąga `/design-sync`).
2. Claude Code pisze `docs/design/<N>.md` według formatu speca z bundla frontendu
   (`stack:frontend:ui-structure`: Breakpointy, Sekcje, Nowe / zmienione tokeny). Eksport
   referencji (`docs/design/<N>.png` albo `.html`) — opcjonalnie, obok speca.
3. `/git-start` → commit `docs(design): layout spec for #<N>` → `/git-end` → merge
   (gałąź bazowa jest chroniona — spec idzie zwykłym PR-em).
4. Przełącz stan:
   `gh issue edit <N> --remove-label ready-for-human --add-label ready-for-agent`

Od kroku 4 issue wraca do wspólnej ścieżki: `/night-run` albo `/headless` w dowolnym kliencie
implementuje ekran wyłącznie według speca.

## `design: tokens` — wygląd całej aplikacji

Stan wejściowy: `design: tokens` + `ready-for-human`.

1. Zmiana w panelu design systemu (`/design-sync` ściąga ją do sesji).
2. Claude Code aktualizuje źródło tokenów (klucz `design-tokens` w `.ai/project.md ## Ścieżki`).
3. Mały PR (`/git-start` → `/git-end`). Bez zmian w komponentach — tokeny niosą wygląd.
