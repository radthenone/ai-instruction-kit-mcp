# Django + DRF — przegląd stacku

## Typowa struktura monorepo

```text
backend/
  src/
    core/           # settings, urls, celery, envs, integrations
    apps/           # aplikacje domenowe i capability
    common/         # abstrakcje współdzielone
    schema.yaml     # kontrakt OpenAPI (opcjonalnie)
  pyproject.toml
  uv.lock
```

## Biblioteki (typowy zestaw)

- `django`, `djangorestframework`
- `django-allauth` (auth headless)
- `drf-spectacular` (OpenAPI)
- `celery`, `redis`
- `pytest`, `ruff`

## Zasady

- **DRF-first** — szczegóły w `stack:django-drf:backend-standard`.
- **Capability + provider** — integracje zewnętrzne przez `core/integrations/`.
- Kontrakt API — schema-first; frontend generuje klienta (Orval/openapi-typescript).
- Stałe globalne tylko w `core/settings/**` i `.env`.

## Powiązane moduły

- `stack:django-drf:backend-standard` — standard tworzenia kodu
- `stack:django-drf:backend-instructions` — instrukcje agenta dla `backend/**`
- `pattern:capability-provider` — integracje zewnętrzne
- `pattern:providers-and-settings` — konfiguracja providerów
