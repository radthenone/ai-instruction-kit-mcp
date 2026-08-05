# Observability — logi, korelacja, sygnały

## Cel

Da się zdiagnozować produkcję bez `print` i bez logowania sekretów.
Standard jest **lekki** — pełny APM (Datadog/Sentry) opcjonalnie w overlay projektu.

## Logowanie (backend)

| Zasada | Opis |
|--------|------|
| Logger, nie print | `logging` / ustalony pack logger projektu |
| Poziomy | DEBUG lokalnie; INFO+ w staging/prod |
| Struktura | Preferuj key=value / JSON (request_id, user_id hash, path, status) |
| Zakaz PII/secrets | Hasła, tokeny, karty, pełny PESEL, raw Authorization header |

Przykładowe pola bezpieczne: `request_id`, `method`, `path`, `status_code`,
`duration_ms`, `order_id` (UUID), `user_id` (int/uuid — świadomie).

## Korelacja

1. Middleware / ASGI: wygeneruj lub przepuść `X-Request-ID` (lub `traceparent`).
2. Wstaw ID do kontekstu logów (contextvars / filter).
3. Przy wywołaniu Celery: przekaż `request_id` w kwargs lub headers taska.
4. Przy HTTP do vendora: opcjonalnie ten sam ID w logu wyjściowym (nie zawsze w
   request do Stripe).

Frontend: przy błędach API loguj / raportuj `request_id` z headera odpowiedzi,
jeśli BE go zwraca — ułatwia support.

## Błędy i alerty

| Warstwa | Narzędzie (przykład) | Kiedy |
|---------|----------------------|--------|
| Unhandled BE | Sentry / odpowiednik | staging + prod |
| Unhandled FE | Sentry RN / web | staging + prod |
| Business metrics | logi + metryki (opc.) | płatności failed, webhook retry exhausted |

Nie spamuj Sentry oczekiwanymi 4xx walidacji — filtruj lub sample.

## Celery / taski

- Log start / success / failure z `task_id` + domain id.
- Po wyczerpaniu `max_retries` — ERROR + alert (nie tylko WARNING).
- Idempotencja: log „already processed” na INFO, nie jako wyjątek krytyczny.

## Health

- Liveness: proces żyje (`/health/` lub podobny).
- Readiness: DB (+ opcjonalnie Redis) osiągalne — osobny endpoint gdy orchestrator
  tego wymaga.
- Health **bez** sekretów i bez ciężkich zapytań.

## Antywzorce

- `print(payload)` z request body w viewsecie.
- Logowanie całego `request.headers`.
- Jeden globalny `except Exception: pass`.
- Metryki bez etykiet (niemożliwe filtrowanie per endpoint).

## Powiązane

- `arch:security` — co wolno logować
- `arch:api-errors` — body vs log (stacktrace tylko w logu)
- `infra:tasks:celery` — retry / on_commit
- Overlay — vendor APM, DSN, sampling
