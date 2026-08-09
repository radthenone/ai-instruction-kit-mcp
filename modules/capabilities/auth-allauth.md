# Auth — django-allauth headless

Wariant `decisions.auth: allauth`. Preferowany dla web + mobile (Expo) w kategorii shop / `_base`.

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

## Orval

Osobny klient wygenerowany z `/_allauth/openapi.json` + osobny mutator auth —
**nie mieszaj** ze schema głównego DRF API. Dwa klienty, dwa mutatory:

```text
src/api/generated/allauth/   # z /_allauth/openapi.json, mutator: cookies/X-Session-Token
src/api/generated/api/       # z DRF schema, mutator: standardowy
```

`task ovral:generate` regeneruje oba (dwa wejścia w `orval.config.ts`).

## Powiązane

- `capability:auth` — część wspólna (frontend, testy)
- `arch:api-contract` — Orval, ogólne zasady kontraktu
