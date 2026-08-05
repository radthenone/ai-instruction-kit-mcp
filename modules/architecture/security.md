# Security — baseline projektów

## Cel

Minimalny, powtarzalny zestaw zasad bezpieczeństwa dla monorepo FE/BE.
Przy auth, płatnościach, ACL → zawsze `/review-security` przed pushem
(`core:code-review`).

## Sekrety i konfiguracja

| Dozwolone | Zakazane |
|-----------|----------|
| Sekrety w env / secret manager (CI, host) | Commit `.env` z prawdziwymi kluczami |
| `STRIPE_SECRET_KEY` tylko backend | Secret key / webhook secret w frontend / mobile |
| Publishable / public keys w kliencie | Hardcode tokenów w kodzie / MD / issue |

Szczegóły env: `arch:configuration`. Overlay projektu może wskazać konkretny vault.

## Auth i sesja

- Jedna strategia na projekt: allauth headless **albo** JWT — nie obie bez podziału
  (`capability:auth`).
- Mobile: token w SecureStore, nie AsyncStorage / Zustand.
- Web: preferuj httpOnly cookie; nie trzymaj access token w `localStorage` bez powodu.
- Po logout: unieważnij sesję server-side + wyczyść storage klienta.
- Hasła / MFA / recovery: tylko przez capability auth, nie w app domenowej.

## Autoryzacja (API)

- Każdy ViewSet: jawne `permission_classes` (nie polegaj wyłącznie na global default
  bez świadomej decyzji).
- Izolacja obiektów: filtruj w `get_queryset()` po `request.user` / tenancie.
- Test: „user B nie czyta / nie edytuje obiektu user A” (`arch:testing`).
- ACL / grupy: migracje uprawnień; nie hardcode `is_superuser` w logice biznesowej.

## HTTP / DRF

- HTTPS wszędzie poza lokalnym dev.
- CSRF przy cookie session (web); mobile z tokenem — świadomy model (brak cookie CSRF).
- CORS: allowlist originów, nie `*` z credentials.
- Throttling: global + scoped na login, signup, password reset, płatności.
- Upload: walidacja typu/rozmiaru; pliki przez `capability:files`, nie zaufaj
  `Content-Type` od klienta bez sprawdzenia.

## Płatności i webhooks

- Weryfikuj podpis webhooka (Stripe `whsec_…`) przed mutacją zamówienia.
- Idempotencja handlerów webhook (ponowione eventy).
- Nigdy nie ufaj samemu statusowi z klienta — źródło prawdy: webhook / retrieve API.
- Szczegóły: `capability:payments`.

## Dane wrażliwe

- Nie loguj: hasła, tokeny, pełne numery kart, PESEL, pełne numery kont.
- Logi: `arch:observability`.
- PII w odpowiedziach API: tylko pola potrzebne UI; unikaj dumpów całego User.

## Frontend

- Nie trzymaj sekretów w `EXPO_PUBLIC_*` / `NEXT_PUBLIC_*` / Vite `VITE_*`.
- Deep linki OAuth: allowlist redirect URI.
- XSS: nie `dangerouslySetInnerHTML` / niesanityzowany HTML z API bez potrzeby.

## Checklist przed PR (auth / payments / files)

- [ ] Brak nowych sekretów w repo
- [ ] Permissions + izolacja queryset przetestowane
- [ ] Webhook / vendor mockowany w unitach; podpis opisany
- [ ] `/review-security` uruchomiony

## Antywzorce

- `AllowAny` na mutacjach „na chwilę”.
- Debug endpoint z dumpem settings w prod.
- Wyłączenie SSL verify „żeby działało”.
- Współdzielony admin password w README.

## Powiązane

- `capability:auth`, `capability:payments`, `capability:files`
- `arch:configuration`, `arch:observability`, `arch:api-errors`
- `core:code-review` — `/review-security`
- OWASP API / ASVS — źródło zewnętrzne (Context7 / docs)
