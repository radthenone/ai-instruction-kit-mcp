# Struktura katalogów — Expo Router

## Layout frontendu

```text
frontend/
  app/                    # Expo Router — routing, layouty, _layout.tsx
  src/
    core/
      auth/               # sesja, tokeny, interceptory 401
      http/               # klient HTTP bazowy
      query/              # TanStack Query provider, defaults
      config/             # env, constants
      theme/
      integrations/       # SDK: Stripe, push — bez UI ekranów
    features/
      auth/               # ekrany logowania, MFA, rejestracja
      account/            # profil, ustawienia
      catalog/            # lista produktów (domain shop)
      cart/               # koszyk (client state + sync API)
      checkout/           # checkout flow → payments capability
      orders/             # historia zamówień
      payments/           # UI capability płatności
    api/
      generated/          # Orval — NIE edytuj ręcznie
    ui/                   # Button, Input, Card — design system
      platform/           # helpers web vs native
  package.json
```

## Zasady

- **Routing** tylko w `app/` — cienkie ekrany delegują do `features/`.
- **Server state** → TanStack Query w hookach feature (`useProducts`, `useOrders`).
- **Client state** → Zustand tylko dla UI (koszyk lokalny przed sync, modale).
- **Capability UI** → `features/payments/`, `features/auth/` — nie w `catalog/`.

## Web vs native

- Różnice platform: `.web.tsx` / `.native.tsx` lub `src/ui/platform/`.
- Nie zakładaj DOM API bez weryfikacji na iOS/Android.

## Powiązane moduły

- `arch:ui-ux-expo`
- `domain:shop` — catalog, cart, orders
- `capability:payments` — checkout + Stripe
