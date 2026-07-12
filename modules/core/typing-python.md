# Python — standardy typowania (backend)

## Wymagania

- **Type hints** na każdej publicznej funkcji, metodzie klas, property.
- Python 3.11+ — używaj `list[str]`, `dict[str, Any]`, `X | None` zamiast `Optional`.
- Docstringi po polsku (Google style) na publicznych API.

## DRF

```python
from rest_framework.request import Request
from rest_framework.response import Response

class OrderViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer: OrderSerializer) -> None:
        serializer.save(user=self.request.user)
```

Serializery — typuj `validate`, `create`, `update` z konkretnymi typami wejścia/wyjścia gdzie sensowne.

## Serwisy capability

```python
def create_payment_for_order(*, order_id: UUID, provider: str = "stripe") -> PaymentSession:
    ...
```

- Keyword-only dla ID i flag (`*`).
- Zwracaj dataclass / TypedDict / model — nie „goły dict” bez kontraktu.

## Celery tasks

```python
@shared_task(bind=True, max_retries=3)
def process_stripe_webhook(self, payment_id: str) -> None:
    ...
```

Argumenty: `str` UUID, nie instancje modeli.

## Mypy / pyright

- Uruchamiaj `task lints:backend:typecheck` po zmianach w publicznych API.
- `# type: ignore` tylko z komentarzem dlaczego — nie masowo.

## Powiązane

- `stack:django-drf:backend-standard`
- `capability:payments` — typowane gateway interfaces
