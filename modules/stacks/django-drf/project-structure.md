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
      accounts/         # profile użytkownika (DRF CRUD)
      products/         # domain: katalog
      orders/           # domain: zamówienia
      payments/         # capability: sesje płatności, webhooks
      files/            # capability: upload, StoredFile
    common/             # pagination, permissions base, mixins
    schema.yaml         # OpenAPI export
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

## Powiązane moduły

- `stack:django-drf:backend-standard` — DRF-first
- `domain:shop` — products + orders
- `capability:payments` — Stripe, webhooks
