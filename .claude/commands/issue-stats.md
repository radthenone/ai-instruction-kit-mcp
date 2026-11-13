---
description: Analiza i priorytetyzacja otwartych issues pod kątem gotowości do pracy autonomicznej (/night-run). Generuje 4-sekcyjny raport statusu, roadmapy, metodyki i segmentacji. Wywołuj jako /issue-stats.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

Język odpowiedzi i hand-backu: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`.

# /issue-stats — analiza backlogu pod night-run

Generuje 4-sekcyjny raport z otwartych issues repozytorium:
1. Status bieżący: Co faktycznie zostało do zrobienia?
2. Rekomendowana kolejność prac (Roadmapa)
3. Podejście, skille i metodyka per zadanie
4. Przegląd gotowości issues pod night-run

## Komenda CLI

Możesz też wywołać bezpośrednio w terminalu:
```bash
kit-ai issue stats
```

## Algorytm

### 1. Pobierz dane z GitHuba

```bash
gh issue list --state open --limit 100 --json number,title,labels,body,state
gh pr list --state merged --limit 50 --json number,title,baseRefName,headRefName,body
```

### 2. Wykryj zmergowane issues

Dla każdego otwartego issue sprawdź, czy powiązany PR został już zmergowany na gałąź integracyjną (`dev`, `master`, `main`).
Powiązanie weryfikuj po:
- tytule PR zawierającym `(#N)` lub `#N`,
- gałęzi PR (`headRefName`) zawierającej numer issue (np. `feat/N-...`, `fix/N-...`),
- słowach kluczowych w opisie PR (`closes #N`, `fixes #N`, `resolves #N`).
Jeśli tak — oznacz issue jako zmergowane (czeka na weryfikację lub zamknięcie).

### 3. Kategoryzacja, zależności i nakład pracy

- **Pominięte:** etykiety blokujące (`ready-for-human`, `needs-info`, `needs-triage`, `wontfix`).
- **Oczekujące:** otwarte issues bez etykiety `ready-for-agent`.
- **Gotowe do realizacji:** oznaczone `ready-for-agent`.
- **Zależności:** wykrywaj zależności z treści (np. `zależy od #X`, `wymaga #X`, `po #X`). Zadanie nadrzędne/zależne musi w roadmapie następować po warunku wstępnym.
- **Nakład (effort):** na podstawie liczby kryteriów akceptacji w treści issue:
  - `S`: $\le$ 2 kryteria (szacunek: 5–15 min)
  - `M`: 3–4 kryteria (szacunek: 15–30 min)
  - `L`: > 4 kryteria (szacunek: 30–60 min)
- Flaga `needs-local` — zadania wymagające lokalnego środowiska wykonawczego.

### 4. Wygeneruj 4 sekcje raportu

Raport musi zawierać dokładnie 4 sekcje:
1. `## 1. Status bieżący: Co faktycznie zostało do zrobienia?` — tabele z kolumnami `# | Tytuł | Typ | Etykiety`.
2. `## 2. Rekomendowana kolejność prac (Roadmapa)` — graf zależności (ASCII/Mermaid), uzasadnienie kolejności i tabela priorytetów.
3. `## 3. Podejście, skille i metodyka per zadanie` — procedury `/grill-me`, `/git-start`, `/tdd`, commit, review (`/review-bugbot` + stack), `/git-end`.
4. `## 4. Przegląd gotowości issues pod night-run` — tabela gotowości, instrukcje zdjęcia blokad (`gh issue edit`), segmentacja i łączna komenda `/night-run`.
