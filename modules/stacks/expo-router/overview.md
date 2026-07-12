# Expo Router — przegląd stacku

## Typowa struktura monorepo

```text
frontend/
  app/              # routing Expo Router (file-based)
  src/
    core/           # auth, api, env, theme, http, query
    features/       # moduły domenowe
    api/            # klienty i typy (generowane + ręczne)
    ui/             # współdzielone komponenty UI
  package.json
  bun.lock
```

## Biblioteki (typowy zestaw)

- `expo-router`
- `@tanstack/react-query` — **server state**
- `zustand` — **tylko local/app state**
- `react-hook-form`, `zod`
- `orval` (generowanie klienta z OpenAPI)
- `nativewind`

## Zasady stanu

| Warstwa | Narzędzie | Co trzyma |
|---------|-----------|-----------|
| Server state | TanStack Query | dane z API, cache, invalidation |
| Client state | Zustand | UI: modale, filtry, theme |
| Form state | react-hook-form + zod | walidacja formularzy |

**Nie** przenoś danych serwerowych do Zustand bez bardzo mocnego uzasadnienia.

## Warstwy odpowiedzialności

- Routing → `frontend/app/`
- Logika domenowa → `frontend/src/features/`
- Fundamenty techniczne → `frontend/src/core/`
- SDK vendorów → `frontend/src/core/integrations/`
- Wspólne UI → `frontend/src/ui/`

## Expo docs

Przy pytaniach o Expo używaj oficjalnych źródeł (Context7 lub):

- https://docs.expo.dev/llms.txt
- https://docs.expo.dev/skills/

## Powiązane moduły

- `stack:expo-router:frontend-instructions` — instrukcje agenta dla `frontend/**`
- `pattern:capability-provider` — capability UI i integracje
