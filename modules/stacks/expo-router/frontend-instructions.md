# Instrukcje agenta — frontend (Expo Router)

## Zakres

Zmiany w `frontend/**` — **mobile (iOS/Android) i web** z tego samego repo. Zawsze sprawdź czy feature dotyczy jednej platformy czy obu.

## Platformy

Przeczytaj bundle lub moduły:

- `arch:platforms` — backend vs web vs mobile
- `stack:expo-router:mobile-native` — SecureStore, EAS, native moduły
- `stack:expo-router:web-target` — web, CORS, Stripe.js
- `capability:payments:expo-stripe` — PaymentSheet na mobile

## Struktura

- `app/` — routing (cienkie ekrany)
- `src/core/` — auth, http, query, theme, **integrations/**
- `src/features/` — logika domenowa i capability UI
- `src/api/generated/` — Orval — **nie edytuj**
- `src/ui/` — design system; `ui/platform/` — helpers web/native

## Capability boundaries

| Capability | Gdzie |
|------------|-------|
| auth | `core/auth/` + `features/auth/` |
| payments | `features/payments/` + `core/integrations/stripe/` |
| shop | `features/catalog/`, `cart/`, `checkout/`, `orders/` |

SDK vendorów (`@stripe/stripe-react-native`) **tylko** w integrations + features/payments — nie w catalog.

## Stan

- **TanStack Query** — server state (API)
- **Zustand** — client state (UI, koszyk przed sync)
- **react-hook-form + zod** — formularze

## Typowanie

- `core:typing-typescript` — strict, Orval types, query keys
- Po API change: `task ovral:generate` → `task lints:frontend:typecheck`

## Pliki platformowe

- Domyślnie jeden plik gdy działa wszędzie.
- `.native.tsx` — PaymentSheet, SecureStore, native API.
- `.web.tsx` — DOM, Stripe Elements.

## Docs Expo

- https://docs.expo.dev/llms.txt
- https://docs.expo.dev/skills/
- Stripe mobile: https://docs.expo.dev/versions/latest/sdk/stripe/

## Komendy

- `task lints:frontend:typecheck` — po każdej większej zmianie
- `task lints:frontend:lint:check`
- `task ovral:generate` — po zmianie API
- `task frontend:run:clear` — gdy Metro trzyma stary cache
- `task frontend:prebuild:clean` — po zmianie config plugin (Stripe)

## Odpowiedzi

Po polsku. Kod po angielsku. Diagnoza → pliki → ryzyka → plan.
