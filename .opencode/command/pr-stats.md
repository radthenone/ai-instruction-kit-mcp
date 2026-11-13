---
description: "Inspekcja otwartych PR-ów — tabela stanu CI/checks, analiza ryzyk i konfliktów, rekomendowane akcje i blokery merge. Wywołuj jako /pr-stats."
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

Język odpowiedzi i hand-backu: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`.

# /pr-stats — inspekcja otwartych Pull Requestów

Generuje 3-sekcyjny raport z otwartych PR-ów w repozytorium:
1. Tabela PR (numer, tytuł, baza, autor, draft, checks, review, mergeable, ryzyko)
2. Analiza ryzyk (HIGH, MEDIUM, LOW)
3. Rekomendowane akcje (gotowe do merge, konflikty, failing checks, review)

## Komenda CLI

Możesz też wywołać bezpośrednio w terminalu:
```bash
kit-ai pr stats
```

## Algorytm

### 1. Pobierz otwarte PR-y

```bash
gh pr list --state open --limit 50 --json number,title,baseRefName,headRefName,author,state,isDraft,mergeable
```

### 2. Sprawdź checks i reviews

Dla każdego PR pobierz status check runs oraz recenzje (w tym botów: CodeRabbit, BugBot):
```bash
gh pr checks <numer> --json name,status,conclusion
gh pr view <numer> --json reviews
```

### 3. Analiza ryzyk

- **HIGH:** failing checks, stan `CHANGES_REQUESTED` lub status `CONFLICTING`.
- **MEDIUM:** pending checks lub brak review człowieka.
- **LOW:** checks przeszły pomyślnie i istnieje akceptacja (approved).

### 4. Wygeneruj 3 sekcje raportu

Raport musi zawierać dokładnie 3 sekcje:
1. `## 1. Tabela PR`
2. `## 2. Analiza ryzyk`
3. `## 3. Rekomendowane akcje`
