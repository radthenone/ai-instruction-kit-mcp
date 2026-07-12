# Rozdział frontend ↔ backend w kodzie

## Backend — co zostaje po stronie serwera

- Modele ORM, migracje, constraints
- Walidacja biznesowa (serializer)
- Permissions, throttling
- Integracje zewnętrzne (`core/integrations/`)
- Taski Celery
- Webhooki (adapter → event wewnętrzny)

Backend **nie wie** o komponentach React, routingu Expo ani stanie UI.

## Frontend — co zostaje po stronie klienta

- Routing (`app/`)
- Renderowanie UI, animacje, layout
- Server state (TanStack Query) — cache, refetch
- Client state (Zustand) — modale, filtry, theme
- Walidacja formularza (zod) — UX; backend i tak waliduje ponownie

Frontend **nie ustawia** stanu biznesowego z backendu (np. `paid=true`) bez API.

## Granice capability

| Capability | Backend | Frontend |
|------------|---------|------------|
| Auth | allauth, sesja, JWT | `core/auth/` sesja + `features/auth/` ekrany |
| Pliki | `apps/files`, storage adapter | `features/files`, upload przez API |
| Płatności | `apps/payments`, Stripe webhook | `features/payments`, SDK w `core/integrations/` |

Szczegóły per capability: moduły `capability:*`.

## Agregacja (BFF)

Gdy ekran potrzebuje danych z wielu źródeł — backend może złożyć odpowiedź w jednym endpoincie (BFF w app domenowej), zamiast wielu calli z frontendu.

## Powiązane moduły

- `pattern:capability-overview`
- `arch:api-contract`
