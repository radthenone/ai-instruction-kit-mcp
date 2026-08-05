# Domain — Shop (katalog + zamówienia)

## Zakres

Logika biznesowa sklepu: produkty, kategorie, koszyk, zamówienia, stany magazynowe — **bez**
integracji zewnętrznych (storage, Stripe, SMTP → odpowiednie capability).

## Backend apps (kategoria shop)

```text
apps/products/      # Product, Category, Variant — CRUD REST
apps/orders/        # Order, OrderLine, statusy — CRUD + checkout actions
apps/inventory/     # opcjonalnie: stock, reservations
apps/discounts/     # opcjonalnie: kody rabatowe
apps/categories/    # opcjonalnie osobno od products
apps/shipping/      # opcjonalnie: metody wysyłki
```

Profile użytkownika / adresy: zwykle `apps/accounts` (capability auth), nie w domain shop.

Pliki produktów: **`capability:files`** (`apps/files`) — domena trzyma tylko `file_id`.

## DRF-first

Typowy CRUD:

```text
Model → Serializer (validate, create, update) → ViewSet (get_queryset, perform_create)
```

- `ProductSerializer`, `ProductViewSet` — bez folderu `services/` jeśli jedyny caller to ViewSet.
- Tłumaczenia katalogu: wspólny `TranslatableModel` / JSON `translations` w `common/` (jeśli projekt i18n).
- Ceny: `django-money` (lub Decimal + currency); historia zmian: `simple-history` opcjonalnie.
- Custom `@action`: `checkout`, `cancel` — ciało w serializerze akcji lub metodzie modelu.
- Przy rozbudowie API: rozszerzaj tagi Orval / OpenAPI i regeneruj klienta.

## Relacje z capability

| Potrzeba | Wołaj | Nie rób |
|----------|-------|---------|
| Zdjęcie produktu | `files` → `file_id` | `ImageField` + upload inline |
| Opłacenie zamówienia | `payments.create_payment_for_order(order_id)` | Stripe w orders |
| Powiadomienie „zamówienie wysłane” | event → `notifications` | SMTP w orders |

## Model Order (skrót)

```text
Order: user, status (draft/pending/paid/shipped/cancelled), total, lines[]
OrderLine: product, quantity, unit_price (snapshot w momencie zakupu)
```

- Ceny na linii **snapshot** — zmiana ceny produktu nie zmienia historycznych zamówień.
- Status `paid` ustawiany **tylko** przez handler eventu z `payments`.

## Frontend features

```text
features/catalog/    # lista, filtry, szczegóły produktu
features/cart/       # lokalny stan + sync POST /api/cart/ opcjonalnie
features/checkout/   # adres, podsumowanie → payments
features/orders/     # historia, status, szczegóły
```

Stack frontu: Expo Router (web + opcjonalnie Android/iOS) — zob. `stack:expo-router:*`.

## Query keys (TanStack Query)

```text
['products', filters]
['product', id]
['orders']
['order', id]
['cart']
```

Invalidacja po checkout: `orders`, `cart`, `order/{id}`.

## Testy

- Unit: serializer validate, price snapshot, status transitions
- Integration: checkout flow z mock payment capability
- Layout testów backendu: `backend/src/tests/` (per-app + `factories/`, `integration/`)

## Powiązane

- `capability:payments` — checkout
- `capability:files` — zdjęcia / media
- `capability:auth` — konta, adresy
- `stack:django-drf:backend-standard`
