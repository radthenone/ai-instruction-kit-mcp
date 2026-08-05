# Kontrakt API — schema-first

## Zasada

Backend definiuje kontrakt; frontend go konsumuje. Kolejność pracy:

1. Zaprojektuj endpoint (serializer + viewset).
2. Zaktualizuj schema OpenAPI (`drf-spectacular` → `schema.yaml`).
3. Wygeneruj klienta TypeScript (`task ovral:generate` / Orval).
4. Użyj wygenerowanych typów w frontendzie.

## Backend

- `drf-spectacular` generuje OpenAPI z DRF.
- Schema trzymana w repo: `backend/src/schema.yaml` (lub export w CI).
- Wersjonowanie URL: `/api/v1/...` gdy potrzebne breaking changes.

## Frontend

- Klient i typy w `frontend/src/api/generated/` — **nie edytuj ręcznie**.
- Hooki TanStack Query owijają wygenerowane funkcje API.
- Przy 401: interceptor → refresh sesji → retry (szczegóły w `capability:auth`).

## Sekwencja po zmianie API

```text
backend (serializer/view/schema) → task ovral:generate → task lints:frontend:typecheck
```

## Testowanie bez frontendu

Backend musi być testowalny samodzielnie: pytest, Postman, Swagger UI — zanim powstanie UI.

## Powiązane moduły

- `stack:django-drf:backend-standard` — DRF-first
- `arch:api-errors` — format błędów FE/BE
- `stack:expo-router:structure` — gdzie trzymać klienta API
