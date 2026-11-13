---
name: issue-stats
description: Analiza i priorytetyzacja otwartych issues pod kątem gotowości do pracy autonomicznej (/night-run). Generuje 4-sekcyjny raport statusu, roadmapy, metodyki i segmentacji. Wywołuj jako /issue-stats.
model-tier: light
classification: procedure
---

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
gh pr list --state merged --limit 50 --json number,title,baseRefName
```

### 2. Wykryj zmergowane issues

Dla każdego otwartego issue sprawdź, czy powiązany PR został już zmergowany na gałąź integracyjną (`dev`, `master`, `main`). Jeśli tak — oznacz issue jako zmergowane (czeka na weryfikację lub zamknięcie).

### 3. Kategoryzacja i nakład pracy

- **Pominięte:** etykiety blokujące (`ready-for-human`, `needs-info`, `needs-triage`, `wontfix`).
- **Oczekujące:** otwarte issues bez etykiety `ready-for-agent`.
- **Gotowe do realizacji:** oznaczone `ready-for-agent`.
- **Nakład (effort):** na podstawie liczby kryteriów akceptacji w treści issue:
  - `S`: $\le$ 2 kryteria
  - `M`: 3–4 kryteria
  - `L`: > 4 kryteria
- Flaga `needs-local` — zadania wymagające lokalnego środowiska wykonawczego.

### 4. Wygeneruj 4 sekcje raportu

Raport musi zawierać dokładnie 4 sekcje:
1. `## 1. Status bieżący: Co faktycznie zostało do zrobienia?`
2. `## 2. Rekomendowana kolejność prac (Roadmapa)`
3. `## 3. Podejście, skille i metodyka per zadanie`
4. `## 4. Przegląd gotowości issues pod night-run`
