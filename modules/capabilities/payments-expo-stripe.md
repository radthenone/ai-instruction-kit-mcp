# Stripe — Expo mobile (`@stripe/stripe-react-native`)

## Oficjalne źródła

- [Expo SDK: @stripe/stripe-react-native](https://docs.expo.dev/versions/latest/sdk/stripe/)
- [Stripe React Native API](https://stripe.dev/stripe-react-native/api-reference/index.html)
- [Stripe RN GitHub](https://github.com/stripe/stripe-react-native)

Przy pytaniach agenta — **Context7** lub powyższe docs (wersja z `expo install`).

## Instalacja

```bash
bun expo install @stripe/stripe-react-native
```

Wersja pakietu musi pasować do SDK Expo — używaj `expo install`, nie ręcznego semver.

## Config plugin (EAS / prebuild)

W `app.json` / `app.config.ts`:

```json
{
  "expo": {
    "plugins": [
      [
        "@stripe/stripe-react-native",
        {
          "merchantIdentifier": "merchant.com.twoja.app",
          "enableGooglePay": true
        }
      ]
    ]
  }
}
```

- `merchantIdentifier` — **iOS**, Apple Pay ([Stripe Apple Pay setup](https://docs.stripe.com/apple-pay?platform=react-native)).
- `enableGooglePay` — **Android**.
- Po zmianie pluginu: **prebuild / EAS rebuild** — nie wystarczy Metro restart.

## Ograniczenia Expo Go

| Funkcja | Expo Go | Dev build / EAS |
|---------|---------|-----------------|
| PaymentSheet (karta) | ✓ (ograniczenia) | ✓ |
| Apple Pay | ✗ | ✓ |
| Google Pay | ✗ | ✓ |

Do Apple/Google Pay planuj **development build** od początku feature płatności.

## Architektura w projekcie

```text
Backend                          Mobile
────────                         ──────
POST /api/payments/sessions/  →  useCreatePaymentSession()
  ← client_secret, ephemeral_key     ↓
                               initStripe({ publishableKey, urlScheme })
                                     ↓
                               initPaymentSheet({ paymentIntentClientSecret })
                                     ↓
                               presentPaymentSheet()
                                     ↓
Webhook → order.paid            polling / invalidate orders query
```

**Backend** wydaje `client_secret` (PaymentIntent) — **mobile nigdy nie widzi secret key**.

## Provider w drzewie React

```typescript
// src/core/integrations/stripe/StripeProvider.native.tsx
import { StripeProvider } from "@stripe/stripe-react-native";

export function AppStripeProvider({ children }: { children: React.ReactNode }) {
  return (
    <StripeProvider
      publishableKey={env.STRIPE_PUBLISHABLE_KEY}
      urlScheme={resolveStripeUrlScheme()}
      merchantIdentifier={env.STRIPE_MERCHANT_ID}
    >
      {children}
    </StripeProvider>
  );
}
```

Opakuj w root layout (`app/_layout.tsx`) — tylko native; web ma osobny provider Stripe.js.

## Hook checkout (wzorzec)

```typescript
// src/features/payments/hooks/usePaymentSheet.ts
import { useStripe } from "@stripe/stripe-react-native";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function usePaymentSheet(orderId: string) {
  const { initPaymentSheet, presentPaymentSheet } = useStripe();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const session = await paymentsApi.createSession({ orderId });
      const { error: initError } = await initPaymentSheet({
        paymentIntentClientSecret: session.clientSecret,
        merchantDisplayName: "Shop",
      });
      if (initError) throw initError;

      const { error: presentError } = await presentPaymentSheet();
      if (presentError) throw presentError;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders", orderId] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}
```

Typy `createSession` response — z Orval (`frontend/src/api/generated/`).

## urlScheme (redirect / 3DS)

```typescript
import * as Linking from "expo-linking";
import Constants from "expo-constants";

export function resolveStripeUrlScheme(): string {
  return Constants.appOwnership === "expo"
    ? Linking.createURL("/--/")
    : Linking.createURL("");
}
```

Bez poprawnego `urlScheme` redirect po 3DS nie wróci do app ([Expo docs — common issues](https://docs.expo.dev/versions/latest/sdk/stripe/)).

## i18n PaymentSheet (iOS)

Android: locale z systemu. iOS: w `app.json`:

```json
"ios": {
  "infoPlist": {
    "CFBundleAllowMixedLocalizations": true,
    "CFBundleLocalizations": ["pl", "en"]
  }
}
```

## Zakazy

- `STRIPE_SECRET_KEY` w mobile — tylko publishable key w kliencie.
- Ustawianie `paid` w store po `presentPaymentSheet` sukces — UI może pokazać „oczekuje”, status z API/webhook.
- Import `@stripe/stripe-react-native` w feature domenowych (`catalog/`) — tylko `features/payments/` i `core/integrations/stripe/`.

## Web

Na web użyj `@stripe/react-stripe-js`, nie stripe-react-native — patrz `stack:expo-router:web-target`.

## Powiązane

- `capability:payments` — backend, webhooks
- `domain:shop` — checkout flow
- `stack:expo-router:mobile-native`
