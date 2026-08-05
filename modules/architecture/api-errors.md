# API errors — jednolity format błędów

## Cel

Jeden kontrakt błędów BE → FE. Agent nie wymyśla ad-hoc JSON przy każdym endpoincie.

## Backend (DRF)

Zalecenie: **`drf-standardized-errors`** jako `EXCEPTION_HANDLER` (RFC 9457 /
problem+json styl).

Zasady:

1. **Rzucaj wyjątki**, nie ręczny `Response({"error": ...}, status=4xx)`.
2. Walidacja API → `rest_framework.serializers.ValidationError`.
3. `Model.clean()` → `django.core.exceptions.ValidationError` (mapowane przez handler).
4. Brak uprawnień → `PermissionDenied` / 403; brak auth → 401.
5. Błędy domenowe → `APIException` (własna klasa z `default_code` / status) albo
   `ValidationError` w serializerze — **nie** `return None` / tuple „sukces lub błąd”.

Przykład intencji (kształt zależy od skonfigurowanego handlera):

```json
{
  "type": "validation_error",
  "errors": [
    { "code": "required", "detail": "This field is required.", "attr": "quantity" }
  ]
}
```

OpenAPI: opisz odpowiedzi 4xx w `drf-spectacular` (`@extend_schema`), żeby Orval
znał typy błędów (`arch:api-contract`).

## Mapowanie HTTP (kanon)

| Sytuacja | Status |
|----------|--------|
| Walidacja input | 400 |
| Brak / zła sesja | 401 |
| Brak uprawnień / cudzy obiekt | 403 |
| Nie znaleziono | 404 |
| Konflikt stanu (np. już opłacone) | 409 lub 400 z kodem domenowym |
| Rate limit | 429 |
| Błąd serwera / vendor nieoczekiwany | 500 (bez stacktrace w body prod) |

## Frontend

| Warstwa | Zachowanie |
|---------|------------|
| Formularz (RHF + zod) | Błędy pola z `attr` → `setError(field)`; reszta → toast / banner |
| TanStack Query mutacja | `onError`: rozróżnij network vs problem+json |
| Lista / detail | 404 → empty / not-found screen; 403 → „brak dostępu” |
| 401 | interceptor → refresh / re-login (`capability:auth`) — nie toast „unknown” |

Nie parsuj `error.message` stringiem ad-hoc, jeśli API zwraca `errors[].attr` —
użyj wspólnego helpera `mapApiErrorToForm(error)`.

MSW w testach: handlery 400/403 z tym samym kształtem (`stack:expo-router:testing`).

## FastAPI / Flask (gdy stack inny niż DRF)

Ten sam kontrakt semantyczny: spójny JSON (type/code/detail/attr), wyjątki zamiast
ręcznych dictów, dokumentacja w OpenAPI. Konkretny middleware — w module stacku.

## Antywzorce

- Różne kształty `{ "detail": "..." }` vs `{ "error": "..." }` vs `{ "message": "..." }`
  w jednym API.
- 200 OK z `{ "success": false }`.
- Stacktrace / SQL w body na produkcji.
- Tłumaczenie błędów tylko na FE przy hardcodzie PL na BE (zob. `arch:i18n`).

## Powiązane

- `stack:django-drf:backend-standard` — skrót + DRF-first
- `arch:api-contract` — schema / Orval
- `arch:security` — 401/403 vs wyciek danych
- `arch:i18n` — `gettext` w komunikatach walidacji
