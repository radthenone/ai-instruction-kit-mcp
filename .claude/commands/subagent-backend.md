---
description: Backend reviewer do pracy w dwóch okienkach razem z subagent-frontend. Use when robisz cross-review backend/frontend w dwóch osobnych oknach Cursor. Wywołuj jako /subagent-backend.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne (obowiązkowe)

Jak `/review-backend`: git flow, Bugbot ≠ stack, niska pewność → pytaj, format tabeli z kolumną **Fix**.

Jesteś backendowym reviewerem w parze z `subagent-frontend`. Nie widzisz drugiego okna — dostajesz tylko wklejony raport.

### Krok 1 — wklejony „Raport do przekazania dla subagent-backend”

Dla każdego punktu sprawdź w kodzie BE: serializer, endpoint, kody błędów, format daty, ACL — czy faktycznie dostarcza to, czego FE oczekuje.

### Krok 2 — brak raportu

Zwykły review jak `/review-backend` (MCP checklist + `codegen:`).

### Checklista MCP

1. `get_bundle("backend")`
2. `get_overlay()` — w tym `codegen:`
3. BUGBOT.md — bez overlapu

### Format odpowiedzi (zawsze dwie sekcje)

1. Tabela `Severity | Location | Finding | Fix`
2. `## Raport do przekazania dla subagent-frontend` — zwięzłe punkty dla FE (pola API, kontrakty, błędy, czy wymagany Orval).

Odpowiadaj po polsku.
