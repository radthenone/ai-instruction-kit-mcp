# Capability — Auth

## Zakres

Uwierzytelnianie użytkownika: login, rejestracja, MFA, social login, sesja.

## Wzorzec referencyjny: django-allauth headless

Preferowany dla aplikacji web + mobile (Expo) w kategorii shop / `_base`:

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
| Profile CRUD | DRF pod ścieżkami customers/accounts (profile, addresses) |

**Orval:** osobny klient z `/_allauth/openapi.json` i mutatorem auth — nie mieszaj z DRF schema.

## Alternatywa: JWT Bearer

Gdy projekt używa własnego `/api/auth/login/` → access + refresh JWT:

- Domain apps weryfikują token lokalnie (RS256 public key).
- Frontend: interceptor refresh przy 401.

Ten wariant wybieraj świadomie (overlay / fork profilu) — nie mieszaj z allauth headless
w tym samym API bez jasnego podziału.

## Frontend

```text
src/core/auth/        # session, platform (browser/app), storage native/web
src/features/auth/    # login, register, MFA, OAuth redirect
src/features/account/ # profil po zalogowaniu
```

## Testy

- Unit: adapterzy, uprawnienia CRUD profilu.
- Integration: login browser vs app client headers.

## Powiązane

- `pattern:microservices-auth` — gdy wiele serwisów
- `domain:shop` — zamówienia wymagają zalogowanego usera
- `stack:django-drf:structure`
