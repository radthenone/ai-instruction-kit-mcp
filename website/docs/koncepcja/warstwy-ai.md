# Warstwy AI: nie mieszaj

Każde narzędzie w tym systemie ma jedną rolę. Gdy warstwy się mieszają, agent dostaje sprzeczne instrukcje, np. dwa sposoby na TDD albo dwa sposoby nazywania branchy.

| Warstwa | Co | Gdzie | Po co |
|---|---|---|---|
| **1. Fundament** | kit: MCP, `git-*`, `review-*` | `.mcp.json`, `.ai/`, agenci | stack, konwencja gita, Managed Worktree, review |
| **2. Proces** | mattpocock/skills | skille | `/grill-me`, `/tdd`: *jak* budować feature |
| **3. Meta / izolacja** | Superpowers | plugin, skille | worktree, brainstorm, debug, finishing branch |
| **4. PR → green** | Autopilot | skill w Cursorze | pętla CI i komentarzy na istniejącym PR |

**Kit jest prawdą o stacku, nazwach branchy i metodzie Managed Worktree.** Matt jest procesem feature. Superpowers jest sesją i finiszem. Autopilot dociąga PR.

## Priorytet źródeł

Gdy źródła się różnią, wygrywa wyższy wpis:

1. polecenie użytkownika,
2. `.ai/project.md` i bundle MCP,
3. `git-*`, `review-*`, `git-branch-pr`,
4. Matt (`/grill-me`, `/tdd`),
5. Superpowers (worktree, finishing, debug),
6. Autopilot (po otwarciu PR),
7. `AGENTS.md` w repo.

## Konflikt TDD

Matt `/tdd` **albo** Superpowers TDD, nigdy oba. Domyślnie Matt na nowe feature'y. Jeden path na feature.

## Kiedy który

- **Scope niejasny** albo decyzja z kompromisami: `/grill-me`. Nie używaj przy oczywistym fixie.
- **Nowy branch**: `git-start`. Gdy diff rozjechał się z issue: `git-check`. Commit: `git-commit`.
- **Review przed pushem**: `review-bugbot` i **minimalny** stack (`review-backend` i/lub `review-frontend`), nie wszystkie naraz.
- **Push i PR**: `git-end` **albo** Superpowers `finishing-a-development-branch`. Jedno z dwóch.
- **Nauka przed kodem**: `teacher-*`. Te agenty nie edytują plików.

Więcej: [Przepływ zmiany](przeplyw-zmiany.md).
