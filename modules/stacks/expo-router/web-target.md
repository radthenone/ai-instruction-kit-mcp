# Expo — web target

## Kontekst

Ten sam kod Expo Router może budować **web** (`expo export --platform web` lub dev server `--web`). To nie jest osobna aplikacja React SPA — to target Expo z ograniczeniami platformy.

## Różnice względem mobile

| Aspekt | Web | Mobile |
|--------|-----|--------|
| Auth token | httpOnly cookie (preferowane) | SecureStore |
| Stripe | `@stripe/react-stripe-js` | `@stripe/stripe-react-native` |
| Layout | CSS / DOM, hover | touch, safe area |
| API browser | `window`, `document` — tylko w `.web.tsx` | — |

## Pliki platformowe

```text
components/PayButton.web.tsx    → Stripe Elements
components/PayButton.native.tsx → PaymentSheet
components/PayButton.tsx        → shared props + re-export (opcjonalnie)
```

Reguła: **wspólny hook** `useCreatePaymentSession()`; różne komponenty UI per platforma.

## SSR / static export

- Sprawdź w projekcie czy używany jest static export czy dev-only web.
- TanStack Query: `staleTime` / dehydrate jeśli SSR — zależnie od setupu Expo web.
- Nie importuj modułów native w plikach współdzielonych bez guarda platformy.

## Testowanie web

- `task lints:frontend:typecheck` — obowiązkowo po zmianach.
- Ręcznie: `expo start --web` — checkout, auth cookie, CORS do API.

## CORS backend

Backend musi zezwalać origin web dev (`localhost:8081` itd.) — konfiguracja w Django `CORS_ALLOWED_ORIGINS`, nie hack w frontendzie.

## Powiązane

- `arch:platforms`
- `capability:payments:expo-stripe` — sekcja web Stripe.js
- `capability:auth` — cookies vs token
