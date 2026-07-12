# Capability — Auth

## Zakres

Uwierzytelnianie użytkownika: login, rejestracja, MFA, social login, sesja.

## Wzorzec referencyjny: django-allauth headless (olivin-app)

```text
core/integrations/allauth/    # adaptery, taski cleanup
apps/accounts/                # Profile, adresy — DRF CRUD (nie logika auth)
```

| Aspekt | Implementacja |
|--------|---------------|
| API auth | allauth headless — `_allauth/{browser\|app}/v1/` |
| Web | cookies + CSRF, `allauthClient = "browser"` |
| Mobile | `X-Session-Token` + SecureStore, `allauthClient = "app"` |
| MFA | TOTP, recovery codes, WebAuthn |
| Social | Google / Facebook via `expo-auth-session` + Dev Client |
| Profile CRUD | DRF pod `customers/` (np. profile, addresses) |

**Orval:** osobny klient z `/_allauth/openapi.json` i mutatorem auth — nie mieszaj z DRF schema.

## Alternatywa: JWT Bearer

Gdy projekt używa własnego `/api/auth/login/` → access + refresh JWT:

- Domain apps weryfikują token lokalnie (RS256 public key).
- Frontend: interceptor refresh przy 401.

Ten wzorzec **nie** opisuje olivin-app — tam allauth headless.

## Frontend

```text
src/core/auth/        # session, platform (browser/app), storage native/web
src/features/auth/    # login, register, MFA, OAuth redirect
src/features/account/ # profil po zalogowaniu
```

| Platforma | Storage sesji |
|-----------|---------------|
| Web | httpOnly cookie (token storage no-op) |
| Expo | expo-secure-store — **nie** AsyncStorage |

OAuth na mobile wymaga **Dev Client** (nie Expo Go).

## Flow (allauth headless)

1. Login przez endpoint allauth (browser lub app client)
2. Web: cookie; mobile: `X-Session-Token` w kolejnych requestach
3. DRF viewsety filtrują po `request.user` w `get_queryset()`
4. Wylogowanie / refresh sesji — API allauth, nie własny JWT refresh

## Zakazy

- Logika auth w app domenowej (`orders`, `products`).
- Trzymanie tokenów sesji w Zustand na mobile.
- Zakładanie JWT flow gdy profil projektu używa allauth headless.

## Powiązane

- `pattern:microservices-auth` — gdy auth to osobny mikroserwis
- `arch:fe-be-separation`
- Overlay projektu — taski, porty, ekrany OAuth
