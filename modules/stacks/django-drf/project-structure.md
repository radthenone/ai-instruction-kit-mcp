# Struktura katalogów — Django + DRF

## Layout backendu

```text
backend/
  src/
    core/
      settings/         # split settings (components/)
      urls.py
      celery.py
      envs.py
      integrations/     # adaptery vendorów — TYLKO tutaj import stripe/boto3
        storage/
        payments/
        mail/
        allauth/
    apps/
      accounts/         # profile użytkownika (DRF CRUD) + auth capability
      products/         # domain: katalog
      orders/           # domain: zamówienia
      payments/         # capability: sesje płatności, webhooks
      files/            # capability: upload, StoredFile
    common/             # pagination, permissions base, mixins, translatable
    tests/              # pytest — NIE w apps/
      conftest.py
      factories/
      shared/
      accounts/         # lustrzane katalogi vs apps (opcjonalnie)
      integration/
    schema.yaml         # OpenAPI export
    manage.py
  pyproject.toml
  uv.lock
```

## Zasady podziału apps

| Typ | Przykład | URL-e | Import vendorów |
|-----|----------|-------|-----------------|
| Domain | `products`, `orders` | `/api/products/`, `/api/orders/` | **zakaz** |
| Capability | `payments`, `files` | `/api/payments/`, `/api/files/` | tylko w `core/integrations/` |
| Auth | `accounts` + allauth | `/api/auth/` (headless) | allauth adapter |

## Minimalna appka domenowa

```text
apps/<domain>/
  models/
  serializers/
  views/
  urls.py
  migrations/
```

Opcjonalnie na żądanie: `filters/`, `selectors/`, `tasks.py` — nie domyślnie.

## Testy

- Kod produkcyjny w `apps/` / `core/` / `common/`.
- Testy w `src/tests/` z `factories/` i `integration/`.
- Nie trzymaj `tests.py` wewnątrz app jako jedynego miejsca dla dużych suite’ów.
- Polityka i przykłady: `stack:django-drf:testing`, `arch:testing`.

## Powiązane moduły

- `stack:django-drf:backend-standard` — DRF-first
- `stack:django-drf:testing` — pytest, factories, APIClient
- `domain:shop` — products + orders
- `capability:files` — media
- `capability:payments` — Stripe, webhooks
