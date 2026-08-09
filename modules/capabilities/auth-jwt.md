# Auth — JWT (djangorestframework-simplejwt)

Wariant `decisions.auth: jwt`. Własny `/api/auth/login/`, `/api/auth/refresh/` — access + refresh JWT.

| Aspekt | Implementacja |
|--------|---------------|
| Backend | `djangorestframework-simplejwt`, access krótkożyjący, refresh dłuższy (rotacja + blacklist) |
| Weryfikacja | Domain apps weryfikują token lokalnie (RS256 public key albo shared secret w monolicie) |
| Web | token w memory/httpOnly cookie (nie `localStorage` — `arch:security`) |
| Mobile | SecureStore |
| MFA / social | brak z pudełka — dopisz explicit jeśli potrzebne (`capability:auth:allauth` ma to gotowe) |

## Frontend

Interceptor refresh przy `401`: kolejkuj równoległe requesty podczas odświeżania tokena,
nie odpalaj wielu równoległych `/refresh/`.

## Orval

Jeden klient, jeden mutator — standardowy DRF schema, mutator dokłada `Authorization: Bearer`
i obsługuje refresh-on-401 (patrz interceptor wyżej). Brak osobnego auth-schema jak w allauth.

## Powiązane

- `capability:auth` — część wspólna (frontend, testy)
- `arch:api-contract` — Orval, ogólne zasady kontraktu
- `arch:security` — przechowywanie tokenów
