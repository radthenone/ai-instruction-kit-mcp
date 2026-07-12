# Overlay projektu — TYLKO unikalne informacje tego repo

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

Opisz tu rozjazdy między **docelowymi** modułami MCP a **faktycznym** kodem (np. capability w szkielecie, blueprint w `_temp/`).
