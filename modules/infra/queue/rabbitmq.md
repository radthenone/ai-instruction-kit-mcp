# RabbitMQ — broker kolejki (Celery)

## Kiedy stosować

Broker wiadomości dla Celery, gdy profil ma:

```yaml
decisions:
  queue: rabbitmq
  tasks: celery
```

Wybierz RabbitMQ gdy potrzebujesz trwalszych kolejek, routing exchange lub oddzielenia brokera od Redis cache.

## Konfiguracja Celery

```python
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default="amqp://guest:guest@rabbitmq:5672//",
)
# Result backend: Redis lub rpc:// — osobna decyzja w settings
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
```

## Dev (Docker)

```text
rabbitmq:3-management
port 5672 wewnętrzny; 15672 opcjonalnie dla UI management
```

## Migracja z Redis broker

1. Zmień profil: `queue: rabbitmq`
2. Zaktualizuj `CELERY_BROKER_URL` w settings
3. Uruchom kontener RabbitMQ
4. Taski bez zmian — ten sam kod Celery

## Powiązane

- `infra:tasks:celery`
- `infra:cache:redis` — cache nadal może być Redis niezależnie od brokera
