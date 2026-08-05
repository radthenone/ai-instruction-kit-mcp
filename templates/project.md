# Overlay projektu — TYLKO unikalne informacje tego repo

## Codegen

```text
codegen: orval
```

Warianty: `orval` (domyślnie przy REST+FE) \| `manual` \| `none`.  
Przy `orval`: po zmianie API → `task ovral:generate` → commit klienta.  
Docelowa flaga MCP: `--codegen` (design; jeszcze nie w CLI).

## Struktura

- `backend/` — Django + DRF
- `frontend/` — Expo Router
- `Taskfile.yml` — główny punkt wejścia komend

## Taskfile

Preferuj `task <namespace>:<nazwa>` zamiast surowych komend Docker/bash.
Lista: `task --list`.

## Docker (dev)

| Kontener | Rola |
|----------|------|
| `<projekt>-postgres` | PostgreSQL |
| `<projekt>-redis` | Redis |
| `<projekt>-django` | Backend |

Uzupełnij porty, nazwy kontenerów i zmienne env specyficzne dla projektu.

## Ścieżki paczek lokalnych (opcjonalnie)

Jeśli projekt używa lokalnych forków — wpisz ścieżki tutaj. Domyślnie: brak.

## Lockfile (weryfikacja wersji)

- Backend: `backend/pyproject.toml`, `backend/uv.lock`
- Frontend: `frontend/package.json`, `frontend/bun.lock`

## Stan implementacji vs instruction-kit

Opisz tu **tylko** rozjazdy tego repo względem docelowych modułów MCP
(np. brak `apps/files` jeszcze, inny auth). Nie kopiuj stanu produktu do modules/ w kicie.