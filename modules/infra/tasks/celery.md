# Celery — zadania asynchroniczne

## Kiedy stosować

Profil projektu:

```yaml
decisions:
  tasks: celery
  queue: redis    # lub rabbitmq
```

Operacje poza cyklem HTTP: mail, push, PDF, miniatury, webhook retry, masowe notyfikacje.

## Struktura w projekcie

```text
backend/src/core/celery.py
backend/src/apps/<app>/tasks.py
backend/src/core/integrations/*/tasks.py   # taski integracji
```

## Zasady tasków

| Zasada | Dlaczego |
|--------|----------|
| Idempotentność | Retry nie podwaja efektu |
| Argumenty = ID (UUID) | Nie serializuj obiektów ORM |
| `autoretry_for` + backoff | Webhooki i sieć |
| Krótki task | Ciężka logika w service, task woła service |

## Worker w Docker

```text
celery-worker   — worker
celery-beat     — scheduler (opcjonalnie)
flower          — monitor dev (opcjonalnie)
```

## Broker — osobny slot

Task runner (`tasks: celery`) ≠ broker (`queue: redis|rabbitmq`).

- Zmiana brokera: edycja profilu + env — taski bez zmian.
- Moduły: `infra:queue:redis` lub `infra:queue:rabbitmq`.

## Powiązane

- `capability:payments` — webhook retry
- `capability:files-storage` — miniatury, cleanup
