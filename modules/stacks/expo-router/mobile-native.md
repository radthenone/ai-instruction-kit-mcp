# Expo — mobile (iOS / Android)

## Kontekst

Expo Router to **React Native** — aplikacja mobilna to pierwszorzędny cel. Web jest drugim targetem tego samego repo, nie odwrotnie.

Docs: [Expo llms.txt](https://docs.expo.dev/llms.txt) · [Expo skills](https://docs.expo.dev/skills/)

## Instalacja i wersje

- Zależności native: `bun expo install <pkg>` (nie `npm install` losowej wersji).
- Wersja pakietu musi pasować do SDK Expo z `package.json` / `app.json`.
- Przed rekomendacją API — sprawdź wersję w lockfile i docs tej wersji.

## Dev client vs Expo Go

| Tryb | Kiedy |
|------|-------|
| **Expo Go** | szybki dev UI, moduły w Expo Go |
| **Development build** | natywne moduły spoza Go (Apple Pay, Google Pay, custom native) |

Stripe **Apple Pay / Google Pay** wymagają development build — nie działają w Expo Go ([Expo Stripe docs](https://docs.expo.dev/versions/latest/sdk/stripe/)).

## Secure storage (auth, tokeny)

```text
expo-secure-store  — access/refresh token na mobile
NIGDY AsyncStorage   — plain text, podatny na wyciek
```

Interceptor HTTP: 401 → refresh → retry — logika w `core/auth/`, nie w ekranach.

## Struktura plików native

```text
src/features/checkout/
  CheckoutScreen.tsx           # wspólna logika / layout
  PaymentStep.native.tsx       # PaymentSheet Stripe
  PaymentStep.web.tsx          # Stripe.js Elements (jeśli web)

src/core/integrations/stripe/
  initStripe.native.ts         # initStripe + urlScheme
  initStripe.web.ts            # loadStripe
  types.ts                     # wspólne typy sesji z API
```

## Deep linking i Stripe redirect

Przy redirect-based flow ustaw `urlScheme` w `initStripe`:

```typescript
import * as Linking from "expo-linking";
import Constants from "expo-constants";

const urlScheme =
  Constants.appOwnership === "expo"
    ? Linking.createURL("/--/")
    : Linking.createURL("");
```

Źródło: [Expo Stripe SDK — common issues](https://docs.expo.dev/versions/latest/sdk/stripe/).

## EAS Build

- `eas.json` — profile: `development`, `preview`, `production`.
- Sekrety (Stripe publishable key) przez EAS Secrets / env w build profile.
- CI: osobny job `eas build` na tag / manual dispatch — nie blokuje każdego PR (koszt).

## Performance mobile

- `expo-image` zamiast `<Image>` dla cache i placeholder.
- Lista produktów: `FlashList` przy długich listach.
- Unikaj ciężkich re-renderów w ekranach z koszykiem — selektory Zustand.

## Powiązane

- `arch:platforms` — backend vs web vs mobile
- `capability:payments:expo-stripe` — PaymentSheet
- `core:typing-typescript` — typy hooków i API
