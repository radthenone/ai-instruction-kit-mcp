# Capability — Payments (backend + kontrakt)

## Zakres

Sesje płatności, webhooki, status zamówienia. **Stripe** jako reference — ten sam wzorzec dla PayU/P24 przez adapter.

## Stan implementacji (w repo aplikacji)

| Element | Źródło prawdy |
|---------|---------------|
| `stripe` / SDK w deps | lockfile + `.ai/project.md` |
| App `payments` / adapter | kod aplikacji |
| Stripe na mobile/web | package.json + overlay |

Bundle MCP `payments` opisuje **docelowy** kontrakt. Implementuj według blueprintu lub overlay w repo aplikacji — nie zakładaj gotowego Stripe w produkcyjnym `src/` bez sprawdzenia.

Platformy klienckie (docelowo):

| Platforma | Moduł instrukcji |
|-----------|------------------|
| Mobile (Expo) | `capability:payments:expo-stripe` — `@stripe/stripe-react-native` |
| Web (Expo) | `stack:expo-router:web-target` — Stripe.js |
| Backend | ten dokument |

## Backend

```text
apps/payments/
  models.py              Payment, PaymentSession
  serializers.py         CreateSessionSerializer
  views.py               PaymentSessionViewSet, WebhookView
  services.py            orkiestracja capability (opcjonalnie cienka)
  tasks.py               retry webhook, reconcile

core/integrations/payments/
  providers/stripe_gateway.py   # import stripe TYLKO tutaj
  webhooks/stripe.py            # weryfikacja podpisu
  registry.py                   # get_payment_gateway(name)
```

## API — kontrakt (OpenAPI)

| Metoda | Endpoint | Request | Response |
|--------|----------|---------|----------|
| POST | `/api/payments/sessions/` | `{ order_id: uuid, provider?: string }` | `{ client_secret, payment_intent_id, publishable_key? }` |
| POST | `/api/payments/webhooks/stripe/` | raw body + Stripe-Signature | 200 / 400 |

Typy response generuj do frontendu przez Orval — **jeden kontrakt** dla web i mobile.

## Flow end-to-end

```text
1. Klient: POST sessions { order_id }
2. Backend: walidacja order (owner, status=draft/pending), kwota z DB
3. Backend: Stripe PaymentIntent.create(amount, metadata)
4. Backend: zapis PaymentSession, zwróć client_secret
5. Klient: PaymentSheet (mobile) / Elements (web)
6. Stripe webhook payment_intent.succeeded
7. Adapter → Celery → order.mark_paid() (atomic)
8. Klient: invalidate query orders / polling
```

## Zasady bezpieczeństwa

- Kwota **zawsze** z backendu (Order.total) — klient nie wysyła amount do zaufania.
- **Secret key** tylko server-side env.
- **Frontend nigdy nie ustawia `order.paid`** — webhook + backend.
- Webhook: weryfikuj podpis w adapterze; do domeny przekaż znormalizowany event (payment_id, status).

## Settings

```text
ECOMMERCE_PAYMENT_DEFAULT_PROVIDER=stripe
ECOMMERCE_PAYMENT_ENABLED_PROVIDERS=stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_...   # opcjonalnie zwracany w session dla mobile
```

## Celery

```python
@shared_task(bind=True, autoretry_for=(StripeError,), max_retries=5)
def process_payment_webhook(self, payment_id: str) -> None:
    ...
```

Idempotentnie — ten sam webhook 2× nie zmienia stanu 2×.

## Testy

- Unit: serializer odrzuca cudzy order, złą kwotę.
- Integration: mock Stripe API + mock webhook signature.
- Contract: schema zawiera PaymentSession response.

## Zakazy

- `import stripe` w `apps/orders`, `apps/products`
- Raw webhook body w widoku orders
- Hardcode kwot / currency w mobile

## Powiązane

- `capability:payments:expo-stripe` — mobile UI
- `domain:shop` — Order, checkout
- `pattern:providers-and-settings`
- [Expo Stripe SDK](https://docs.expo.dev/versions/latest/sdk/stripe/)
