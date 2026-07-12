# Providery, adaptery i konfiguracja (backend `src/`)

## Cel dokumentu

Opisuje **jeden wspólny wzorzec** integracji zewnętrznych w produkcyjnym
`backend/src/`: storage (S3/MinIO), płatności, mail, notyfikacje, MT i każda
przyszła integracja oparta o SDK lub HTTP API.

**Zasada:** konfiguracja (env, domyślne wartości, mapy scope→bucket, lista
providerów) żyje w **`core/settings/`**. Kod aplikacji **nie hardcoduje** nazw
bucketów, kluczy API ani nazw providerów.

**DRF-first** (`stack:django-drf:backend-standard`) dotyczy domeny (`orders`,
`products`, `accounts`). Ten dokument dotyczy **capability i integracji** — nie
zastępuje serializera + viewsetu przy zwykłym CRUD.

Powiązane:

- `pattern:capability-provider` — capability vs domena, zakazy
- `stack:django-drf:backend-standard` — kiedy serializer, kiedy provider
- `backend/src/_temp/ecommerce_backend_blueprint/` — kod referencyjny do ręcznego
  przenoszenia do `src/` (blueprint ma uproszczone snippety settings, nie pełny
  `core/settings/components/` produkcji)

## Kiedy stosować ten wzorzec

```text
Czy kod woła zewnętrzny system (SDK, HTTP, webhook, kolejka)?
  → TAK: 4 warstwy (settings → registry → adapter → capability)
  → NIE: Model → Serializer → ViewSet
```

Przykłady integracji (lista nie jest zamknięta):

| Obszar | Capability / integracja | Adapter |
|--------|-------------------------|---------|
| Pliki | `apps/files` | S3 (MinIO dev = ten sam kod co AWS) |
| Płatności | `apps/payments` | Stripe, PayU, P24, Tpay |
| Mail | `core/integrations/mail` | SMTP / Mailhog |
| Notyfikacje | `apps/notifications` | database, email, WS, Expo push |
| Auth społecznościowy | `core/integrations/allauth` | Google, Apple (hook frameworka) |
| Tłumaczenia MT | `core/integrations/machine_translation` | LibreTranslate, … |
| Dokumenty/PDF | `apps/documents`, `core/renderers` | renderer + zapis przez `apps/files` |

## Cztery warstwy

```text
1. Settings / .env          → stałe, mapy, domyślne wartości (jedno źródło prawdy)
2. core/integrations/       → adaptery vendora (import stripe/boto3 TYLKO tutaj)
   └── <capability>/
       ├── providers/       → wywołania wychodzące (create payment, put object)
       ├── webhooks/        → parsowanie przychodzących callbacków (opcjonalnie)
       └── registry.py      → factory z settings
3. apps/<capability>/       → modele DB, HTTP API, orkiestracja capability
   └── services/            → upload, create_payment_for_order, webhook dispatch
4. apps/<domain>/           → DRF CRUD; woła capability przez ID / API, nie vendora
```

**Podmiana providera:** zmiana env + wpis w registry — bez edycji `orders` ani
`products`.

## Struktura folderów `core/integrations/`

Podział po **capability**, nie po vendorze:

```text
core/integrations/
  storage/
    providers/          # s3.py (MinIO + AWS), local.py
    registry.py         # get_storage_for_scope(scope)
  payments/
    providers/          # stripe_gateway.py, payu_gateway.py, …
    webhooks/           # stripe.py — podpis i normalizacja eventu
    registry.py         # get_payment_gateway(name)
  mail/                 # adapter + taski (już w src/)
  notifications/        # kanały dostarczania
  allauth/              # wyjątek: adaptery Django, nie osobny apps/
```

**Nie** twórz osobnych folderów `minio/` i `aws/` — to jeden adapter S3 z innym
`AWS_S3_ENDPOINT_URL`.

### Webhooki — podział odpowiedzialności

| Warstwa | Odpowiedzialność |
|---------|------------------|
| `core/integrations/.../webhooks/` | Walidacja podpisu, mapowanie payloadu vendora |
| `apps/payments/views/` | Cienki HTTP (`AllowAny`, routing) |
| `apps/payments/services/webhook_service.py` | Idempotencja, `Order.paid`, stock |

## Settings — produkcja (`backend/src/`)

Pełna konfiguracja Django: `backend/src/core/settings/components/`.

| Plik | Zawartość |
|------|-----------|
| `storage.py` | `USE_AWS`, `AWS_*`, `STORAGES`, docelowo `FILE_SCOPE_BUCKETS` |
| `email.py` | SMTP, backend mailowy |
| `payments.py` | *(docelowo)* `ECOMMERCE_PAYMENT_*`, `STRIPE_*` |
| `auth.py`, `celery.py`, … | bez zmian |

Wzorzec ładowania z env (produkcja i blueprint):

```python
import os

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "minio")  # minio | s3 | local
ECOMMERCE_PAYMENT_DEFAULT_PROVIDER = os.environ.get(
    "ECOMMERCE_PAYMENT_DEFAULT_PROVIDER", "stripe"
)
```

### Storage

| Zmienna env | Domyślnie (dev MinIO) |
|-------------|------------------------|
| `STORAGE_BACKEND` | `minio` |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` |
| `S3_BUCKETS_NAMES` | lista do `init-minio.sh` (sync przy starcie) |
| `S3_BUCKET_PRODUCTS`, … | nadpisanie pojedynczego bucketu |

Mapa scope → bucket: `FILE_SCOPE_BUCKETS` w settings (blueprint:
`core/settings/file_policies.py`; produkcja: docelowo `components/storage.py` lub
osobny moduł importowany do settings).

### Płatności

| Zmienna env | Domyślnie |
|-------------|-----------|
| `ECOMMERCE_PAYMENT_DEFAULT_PROVIDER` | `stripe` |
| `ECOMMERCE_PAYMENT_ENABLED_PROVIDERS` | `stripe` |
| `STRIPE_SECRET_KEY` | `""` |
| `STRIPE_WEBHOOK_SECRET` | `""` |
| `STRIPE_PUBLISHABLE_KEY` | `""` |

## Płatności — sesja i adapter

```text
POST /orders/checkout/           → CheckoutCreateSerializer (domena)
POST /payments/sessions/         → CreatePaymentSessionSerializer.create()
                                   → create_payment_for_order()
                                   → get_payment_gateway(provider)
POST /payments/webhooks/{name}/  → get_webhook_parser(name) → webhook_service
```

Modele capability: `Payment`, `PaymentSession`, `PaymentWebhookEvent`.

Frontend **nie** ustawia `order.paid` — źródło prawdy to webhook.

## Storage — scope i jeden backend S3

```text
apps/files/services/upload_service.py
  → get_storage_for_scope(scope)     # core/integrations/storage/registry.py
  → bucket z FILE_SCOPE_BUCKETS      # settings
```

**Zakazy:**

- `ImageField(storage=ProductStorage())` na modelu domenowym
- `import boto3` w `apps/products`
- hardcoded `bucket_name = "products"` w klasie storage

## Capability service ≠ domenowy service

| Typ | Dozwolony? |
|-----|------------|
| `ProfileService` owijający ten sam serializer co ViewSet | ❌ |
| `create_payment_for_order`, `upload_stored_file`, `dispatch_payment_webhook` | ✅ |
| `MailService` + Celery w `core/integrations/mail` | ✅ |

## Stan produkcji vs blueprint

| Obszar | `backend/src/` (produkcja) | `_temp` (wzorzec kodu) |
|--------|---------------------------|-------------------------|
| Settings | Pełne `core/settings/components/` | Snippety: `ecommerce_snippets.py`, `file_policies.py` |
| Storage | `core/storage/storages.py` (do refaktoru na scoped + settings) | Wzorzec scoped S3 + registry |
| Płatności | `apps/payments` — szkielet | Pełny flow sessions + webhooks |
| Pliki | brak `apps/files` | Pełna capability `apps/files` |

Przenosisz **wzorzec** z `_temp` do `src/` ręcznie; settings produkcji **rozszerzasz**,
nie kopiujesz blueprintu 1:1.

## Checklista agenta

```text
[ ] Konfiguracja tylko w core/settings (+ .env), z domyślnymi wartościami dev
[ ] Adapter vendora w core/integrations/<capability>/providers/ lub webhooks/
[ ] Registry czyta settings; ImproperlyConfigured gdy provider wyłączony
[ ] Capability: modele + serializers + cienkie views + services/
[ ] Domena: DRF-first; brak importu vendora
[ ] Webhook: parser w integrations; biznes w apps/<capability>/services/
[ ] Po zmianie kontraktu API: schema.yaml → task ovral:generate
```
