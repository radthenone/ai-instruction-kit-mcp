# Domain — Shop (katalog + zamówienia)

## Zakres

Logika biznesowa sklepu: produkty, kategorie, koszyk, zamówienia, stany magazynowe — **bez** integracji zewnętrznych.

## Stan w olivin-app

| Obszar | Stan |
|--------|------|
| `accounts` | żywy (User, Profile, Address) |
| `products` | częściowy — Product, Variant, `TranslatableModel`, **`ImageField`** |
| `orders`, `inventory`, … | szkielet |
| Frontend catalog/cart/checkout | brak w produkcyjnym `src/` — blueprint w `_temp/` |
| Orval `APPS_TAGS` | Addresses, Profiles, Health |

Przy rozbudowie domeny: rozszerzaj `APPS_TAGS` i regeneruj Orval po dodaniu viewsetów.

## Backend apps (docelowo)

```text
apps/products/      # Product, Category, Variant — CRUD REST
apps/orders/        # Order, OrderLine, statusy — CRUD + checkout actions
apps/inventory/     # opcjonalnie: stock, reservations
apps/discounts/     # opcjonalnie: kody rabatowe
```

## DRF-first

Typowy CRUD:

```text
Model → Serializer (validate, create, update) → ViewSet (get_queryset, perform_create)
```

- `ProductSerializer`, `ProductViewSet` — bez folderu `services/` jeśli jedyny caller to ViewSet.
- Tłumaczenia katalogu: `TranslatableModel` + JSON `translations` (olivin: `common.translatable`).
- Ceny: `django-money` (PLN); historia: `simple-history` na Product (olivin).
- Custom `@action`: `checkout`, `cancel` — ciało w serializerze akcji lub metodzie modelu.

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
features/cart/       # Zustand (local) + sync POST /api/cart/ opcjonalnie
features/checkout/   # adres, podsumowanie → payments
features/orders/     # historia, status, szczegóły
```

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

## Powiązane

- `capability:payments` — checkout
- `capability:files-storage` — zdjęcia produktów
- `stack:django-drf:backend-standard`
