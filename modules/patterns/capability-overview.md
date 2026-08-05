# Capability + Provider — przegląd

## Dwa rodzaje modułów

### Capability apps

Własne URL-e API, infrastruktura współdzielona:

| Moduł instrukcji | Backend app | Frontend feature |
|------------------|-------------|------------------|
| `capability:auth` | allauth + accounts | `core/auth`, `features/auth` |
| `capability:files` | apps/files | features/files |
| `capability:payments` | apps/payments | features/payments, checkout |

### Domain apps

Logika biznesowa — **nie importują vendorów**:

| Moduł | Przykład |
|-------|----------|
| `domain:shop` | products, orders, catalog, cart |

## Wzorzec 4 warstw (integracje)

```text
settings → registry → adapter (core/integrations/) → capability service + HTTP
```

Szczegóły: `pattern:providers-and-settings`.

## Reguła decyzyjna

```text
Kod woła zewnętrzny system (SDK, HTTP, webhook)?
  → TAK: capability + provider
  → NIE: DRF-first (serializer + viewset)
```

## Celery

Mail, PDF, miniatury, webhook retry, masowe notyfikacje → taski idempotentne, args = UUID.

## Eventy

`OrderPaid`, `OrderShipped` → `notifications` / `documents` reagują na event, nie na import z orders.

## Powiązane moduły

- `capability:auth`, `capability:files`, `capability:payments`
- `domain:shop`
- `pattern:providers-and-settings`
