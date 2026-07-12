# Architektura capability + provider (olivin-app)

## Cel dokumentu

Ten dokument opisuje **obowiązkowy** wzorzec architektoniczny dla integracji zewnętrznych
(storage, płatności, mail, push, realtime, tłumaczenia maszynowe, renderowanie dokumentów)
oraz dla **capability apps** z własnymi URL-ami API.

Agenci AI muszą stosować te zasady przy **każdej** nowej funkcjonalności, która dotyka
infrastruktury lub wielu modułów domenowych.

Blueprint referencyjny: `backend/src/_temp/ecommerce_backend_blueprint/`,
`frontend/_temp/ecommerce_frontend_blueprint/`.

## Dwa rodzaje modułów

### Capability apps (infrastruktura / platforma)

Moduły z **własnymi URL-ami**, konsumowane przez frontend i przez domenę przez **service**,
nie przez import modeli obcych app:

| Capability | Backend app | Przykładowe URL-e | Frontend feature |
|------------|-------------|-------------------|------------------|
| Pliki | `apps/files` | `POST /files/`, `DELETE /files/{id}/` | `features/files` |
| Płatności | `apps/payments` | `POST /payments/sessions/`, webhooks | `features/payments` |
| Notyfikacje | `apps/notifications` | inbox API, push tokens, WS | `features/notifications` |
| Auth (allauth) | `core/integrations/allauth` + `apps/accounts` | `/api/auth/...` (allauth headless) | `features/auth`, `core/auth` |
| Dokumenty (opcjonalnie) | `apps/documents` | `POST /documents/render/` | `features/documents` |

### Domain apps (biznes)

Moduły domenowe: `products`, `orders`, `categories`, `discounts`, `inventory`, …

**Zasada:** domena **nie importuje** bibliotek zewnętrznych (`stripe`, `boto3`, `expo-notifications`)
ani modeli z innych domen bez wyraźnej potrzeby. Woła **service capability** albo publikuje **event**.

**Uwaga (DRF-first):** zwykły CRUD zasobów domenowych (`Profile`, `Order`, `Product`) idzie przez
**serializer + viewset** (`stack:django-drf:backend-standard`). „Service" w tym dokumencie dotyczy
**capability** (pliki, płatności, mail) i integracji — nie oznacza folderu `services/` przy każdym
modelu domenowym.

## Warstwy backendu

```text
apps/<domain>/          modele, serializers, views — CRUD REST; opcjonalnie selectors/filters/tasks
apps/<capability>/      modele capability, HTTP/WS, orkiestracja — cienkie widoki + service capability
core/integrations/      adaptery providerów (stripe, minio, mail, allauth, channels)
core/providers/         protokoły / rejestry (opcjonalnie, gdy współdzielone)
common/                 abstrakcje bez vendora (TranslatableModel, pagination, locale)
```

### Provider pattern

1. **Protokół** (interfejs) — metody biznesowe bez szczegółów vendora.
2. **Implementacja** — `StripeGateway`, `S3StorageBackend`, `SmtpMailAdapter`, …
3. **Rejestr / factory** — wybór implementacji z `settings` / `.env`.
4. **Service** — orkiestracja capability; app domenowa woła capability, nie providera.

Szczegóły env, struktura folderów (`providers/`, `webhooks/`), checklista i stan
`src/` vs blueprint: **`pattern:providers-and-settings`**.

### Wspólny wzorzec (storage, płatności, mail, …)

```text
settings (.env + domyślne)  →  registry  →  adapter  →  capability service + HTTP
```

| Warstwa | Przykład |
|---------|----------|
| Settings | `FILE_SCOPE_BUCKETS`, `ECOMMERCE_PAYMENT_ENABLED_PROVIDERS` |
| `core/integrations/.../providers/` | `StripeGateway`, scoped S3 storage |
| `core/integrations/.../webhooks/` | parser podpisu Stripe (przychodzące callbacki) |
| Registry | `get_payment_gateway`, `get_storage_for_scope` |
| `apps/<capability>/` | `Payment`, `StoredFile`, `create_payment_for_order`, `upload_stored_file` |

**Podmiana providera** = env + registry. Domena (`orders`, `products`) bez zmian.

**Reguła decyzyjna (nie zamknięta lista capability):** czy kod woła zewnętrzny
system? → 4 warstwy. Zwykły CRUD REST? → DRF-first.

Przykład env:

```text
STORAGE_BACKEND=minio          # lub s3, local
ECOMMERCE_PAYMENT_DEFAULT_PROVIDER=stripe
ECOMMERCE_PAYMENT_ENABLED_PROVIDERS=stripe
NOTIFICATION_CHANNELS=database,websocket,email
```

### Zakazy (backend)

- `import stripe` w `apps/products` lub `apps/orders` — **zakaz**.
- Bezpośredni upload pliku w modelu domenowym (`ImageField` na `Product`) — **zakaz**;
  użyj `apps/files` + FK / `fileId`.
- Ustawianie `order.paid` z frontendu — **zakaz**; webhook + service.
- Payload webhooka Stripe przekazywany 1:1 do domeny — **zakaz**; adapter → event wewnętrzny.

### Celery

Operacje **ciężkie lub sieciowe** poza cyklem request/response:

- e-mail, push, SMS
- generowanie PDF / faktury (`core/renderers`)
- miniatury, konwersja WebP
- retry webhooków, reconcile płatności
- cleanup osieroconych plików (`StoredFile` status `pending`)
- masowe notyfikacje (promocja, kod rabatowy)

Taski: **idempotentne**, argumenty = identyfikatory (UUID), nie obiekty ORM.

### Eventy domenowe

Capability `notifications` i `documents` reagują na **eventy wewnętrzne** (`OrderPaid`,
`PromoCodeAssigned`, `InvoiceRequested`), nie na bezpośrednie wołania z widoków orders.

Na start w monolicie: service + Celery task; później: outbox / broker.

### Pliki (`apps/files`)

Rekord `StoredFile` w DB = **źródło prawdy** o artefakcie. Storage = nośnik bajtów.

Lifecycle: `pending → uploaded → processed → attached → deleted`.

Domena podpina plik przez `fileId` (np. `POST /catalog/products/{id}/images/`).

### Płatności (`apps/payments`)

Flow sklepu mobilnego:

```text
POST /orders/checkout/ → POST /payments/sessions/ → PaymentSheet → webhook → poll order
```

Provider Stripe z `automatic_payment_methods` (karta, BLIK, P24, wallety — Dashboard PL).

### Notyfikacje (`apps/notifications`)

Wielokanałowe dostarczanie: **database**, **websocket** (Channels), **email** (mail integration),
**push** (Expo). Kanały przez **NotificationChannelProvider** w `core/integrations/notifications/`.

Auth WebSocket: centralnie w `core/integrations/channels/`, nie w każdym consumerze.

## Warstwy frontendu (Expo)

```text
app/                    routing Expo Router
src/features/<domain>/  UI + hooki domenowe (catalog, cart, checkout)
src/features/<capability>/  files, payments, notifications — własne serwisy API
src/core/integrations/  adaptery SDK (stripe, expo push) — bez logiki ekranu
src/core/auth/          sesja allauth, token storage — bez ekranów logowania
src/core/api/           klient HTTP wspólny (tymczasowo w blueprintcie _temp)
```

### Orval — dwa wyjścia (potwierdzone w `frontend/orval.config.js`)

Nie ma osobnego targetu „ecommerce”. Są **dwa** źródła OpenAPI:

| Target Orval | Schema | Folder wyjściowy | Zawartość |
|--------------|--------|------------------|-----------|
| `allauth-headless` | `/_allauth/openapi.json` | `frontend/src/api/generated/auth/**` | sesja, login, MFA, reset hasła, providery |
| `app` | `/api/schema/` + filtr tagów | `frontend/src/api/generated/apps/**` | **wszystko z Django/DRF** objęte tagiem w `APPS_TAGS` |

Dziś `APPS_TAGS = ["Addresses", "Profiles", "Health"]`. Sklep (produkty, zamówienia,
pliki, płatności, …) po wdrożeniu w backendzie dostaje **własne tagi w `schema.yaml`**
i trafia do **tego samego** `generated/apps/**` — wystarczy rozszerzyć `APPS_TAGS`.

Auth **nie** jest w `/api/schema/` — to osobny kontrakt allauth headless.

Blueprint `_temp` używa ręcznego `ecommerceGet/Post` dopóki endpointy sklepu nie są
w schema; potem serwisy w `features/*` przepinasz na import z `@api/generated/apps/...`.
Mutatory: `auth-mutator.ts` (auth), `app-mutator.ts` (apps — profil, adresy, sklep).

### Zakazy (frontend)

- `import { useStripe }` w `features/catalog` — **zakaz**; tylko `features/checkout` + `core/integrations/payments`.
- Upload pliku w komponencie produktu bez `features/files` — **zakaz**.
- Server state w Zustand — **zakaz** (TanStack Query).

Checkout **orkiestruje** (`orders` → `payments` → PaymentSheet → poll), nie implementuje Stripe.

## Przyszłe mikroserwisy

Granice capability apps są naturalnymi granicami serwisów (`files-service`, `payments-service`).
Przy wydzieleniu zmienia się transport (HTTP między serwisami), nie kontrakt wobec frontendu.

## Checklista dla agenta (nowa funkcjonalność)

```text
[ ] Czy to integracja zewnętrzna? → provider + integration + service
[ ] Czy to capability z własnym API? → osobna app + feature frontend
[ ] Czy domena musi wiedzieć? → tylko przez service / event / fileId
[ ] Czy operacja jest ciężka? → Celery task z idempotencją
[ ] Czy frontend woła właściwy feature capability?
[ ] Czy STEP_BY_STEP blueprint wymaga aktualizacji?
```
