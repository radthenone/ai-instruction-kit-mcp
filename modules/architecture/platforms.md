# Platformy — backend, web, mobile

## Trzy cele buildu

Projekt full-stack to **nie jeden frontend** — to trzy osobne cele z wspólnym kontraktem API:

| Platforma | Technologia | Artefakt | CI / deploy |
|-----------|-------------|----------|-------------|
| **Backend** | Django + DRF | Docker image / WSGI | pytest, ruff, migrate |
| **Mobile** | Expo Router (iOS, Android) | EAS Build / dev client | EAS, native prebuild |
| **Web** | Expo Router (web target) | static export / SSR | tsc, eslint, web build |

Wspólny kod w `frontend/` — różnice przez `.web.tsx` / `.native.tsx` i `core/integrations/`.

## Zasada kontraktu

```text
                    ┌─────────────┐
                    │   Backend   │  OpenAPI / schema.yaml
                    │  Django DRF │
                    └──────┬──────┘
                           │ REST + auth
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Expo Web    Expo iOS    Expo Android
         (browser)   (native)    (native)
```

- Jeden backend, wiele klientów — **schema-first** (`arch:api-contract`).
- Typy TS generowane z OpenAPI (Orval) — wspólne dla web i mobile.
- Logika biznesowa płatności **zawsze** na backendzie; klient tylko potwierdza UI (PaymentSheet, redirect).

## Co jest wspólne vs platform-specific

| Warstwa | Wspólne | Web only | Native only |
|---------|---------|----------|-------------|
| API hooks (TanStack Query) | ✓ | | |
| Typy z Orval | ✓ | | |
| Routing (Expo Router) | ✓ (file-based) | DOM layout | native stack |
| Auth storage | | httpOnly cookie | SecureStore / Keychain |
| Płatności Stripe | flow API | `@stripe/react-stripe-js` | `@stripe/stripe-react-native` |
| Push notifications | | (web push opcj.) | Expo Notifications |
| Deep linking | | URL path | `Linking`, universal links |

## Kiedy pisać `.web` / `.native`

- **Domyślnie** jeden plik — gdy kod działa wszędzie (hooki API, typy, logika bez UI).
- **`.native.tsx`** — PaymentSheet, Keychain, haptics, native modals.
- **`.web.tsx`** — Stripe Elements, DOM-only layout, `window` API.

Nie duplikuj całych feature — tylko cienka warstwa UI/platformy.

## Dev workflow

| Cel | Typowa komenda |
|-----|----------------|
| Backend | `task backend:run` |
| Mobile (Expo Go / dev client) | `task frontend:run` |
| Web | `task frontend:run` + platform web lub `expo start --web` |
| Android build | `task frontend:build:android` |
| iOS / EAS | EAS CLI (`eas build`) |

## Powiązane

- `stack:expo-router:mobile-native` — native, EAS, SecureStore
- `stack:expo-router:web-target` — web target
- `capability:payments:expo-stripe` — Stripe na mobile
- `arch:ci-cd` — osobne joby CI per platforma
