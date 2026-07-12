# Redis — broker kolejki (Celery)

## Kiedy stosować

Broker wiadomości dla Celery, gdy profil ma:

```yaml
decisions:
  queue: redis
  tasks: celery
```

Prosty setup solo-dev — jeden kontener Redis, cache na DB `1`, broker na DB `0`.

## Konfiguracja Celery

```python
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
```

## Kiedy wybrać RabbitMQ zamiast Redis

| Redis broker | RabbitMQ broker |
|--------------|-----------------|
| Mniej moving parts w dev | Lepsze gwarancje dostarczenia |
| Solo-dev, mały ruch | Większy ruch, routing exchange |
| Profil: `queue: redis` | Profil: `queue: rabbitmq` |

Zmiana brokera = edycja profilu + moduł `infra:queue:rabbitmq` — bez zmian w logice tasków.

## Powiązane

- `infra:tasks:celery` — definicja tasków, idempotencja
- `infra:cache:redis` — osobny slot cache
