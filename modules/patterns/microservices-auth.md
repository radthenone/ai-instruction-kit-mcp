# Auth między serwisami — JWT + service key

## Dwa mechanizmy (nie mieszaj)

| Mechanizm | Kto | Po co |
|-----------|-----|-------|
| **User JWT** | Frontend → gateway → app | Tożsamość zalogowanego użytkownika |
| **Service key / service JWT** | App → auth-service (S2S) | Czy caller to zaufany serwis wewnętrzny |

## User JWT (RS256)

1. Użytkownik loguje się przez auth-service (MFA, social, email).
2. Auth-service wydaje access token (krótki, 5–15 min) + refresh token.
3. Gateway przekazuje `Authorization: Bearer <token>` do app.
4. App weryfikuje JWT **lokalnie** kluczem publicznym — bez call do auth-service przy każdym requeście.

### Mobile vs Web

Format JWT jest ten sam. Różni się storage:

| Platforma | Access token | Refresh token |
|-----------|--------------|---------------|
| Web | httpOnly cookie | httpOnly cookie |
| Expo/RN | expo-secure-store / keychain | secure-store (dłuższy TTL) |

**Nigdy** AsyncStorage na mobile dla tokenów.

## Service-to-service

Gdy store-app pyta auth-service o profil użytkownika:

- Nagłówek `X-Service-Key: <secret>` lub krótkotrwały service JWT
- Timeout (np. 3s) — wolny auth nie blokuje całego requestu
- Circuit breaker przy wielu serwisach

## Database per service

- Auth-service: users, credentials, MFA, social accounts
- Store-app: profiles, orders, products (tylko swoje dane)
- Cars-app: bookings, vehicles (tylko swoje dane)

Synchronizacja lekkich kopii (display_name, avatar) przez eventy (Redis/Celery), nie ciągłe REST do auth.

## APP_KEY

Wspólny sekret per para serwisów lub rejestr kluczy w auth-service. Rotacja przez env / secrets manager. Solo-dev: statyczny klucz w `.env` w sieci Docker wystarczy.
