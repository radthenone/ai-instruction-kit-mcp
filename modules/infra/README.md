# Infra — katalog modułów infrastruktury

Moduły `infra:*` wybierasz slotami w profilu projektu (`decisions`).

## Sloty i warianty

| Slot | Klucz profilu | Dostępne wartości | Moduł |
|------|---------------|-------------------|-------|
| Baza danych | `database` | `postgres` | `infra:database:postgres` |
| Cache | `cache` | `redis` | `infra:cache:redis` |
| Kolejka (broker) | `queue` | `redis`, `rabbitmq` | `infra:queue:redis`, `infra:queue:rabbitmq` |
| Storage | `storage` | `s3`, `minio`, `aws` | `infra:storage:s3` |
| Taski async | `tasks` | `celery` | `infra:tasks:celery` |

## Przykład — kategoria shop (Redis broker)

```yaml
decisions:
  database: postgres
  cache: redis
  queue: redis
  storage: s3
  tasks: celery
```

## Przykład — RabbitMQ zamiast Redis broker

```yaml
decisions:
  database: postgres
  cache: redis        # cache nadal Redis
  queue: rabbitmq   # broker Celery → RabbitMQ
  storage: s3
  tasks: celery
```

Zmiana brokera = edycja profilu. Kod tasków bez zmian.

## Dodawanie nowego wariantu

1. Dodaj plik MD w odpowiednim podkatalogu, np. `infra/database/mysql.md`
2. Zarejestruj w `manifest.yaml`: `infra:database:mysql`
3. Rozszerz mapowanie w `resolver.py` → slot `database: mysql`
4. Użyj w profilu projektu

## Lekki tryb VPS (auto, nie slot)

`infra:vps-lightweight` nie wchodzi przez `decisions` — dokleja go resolver, gdy
host to VPS (`KIT_HOST_PROFILE=vps` albo heurystyka: Linux, małe zasoby, brak swapu,
wirtualizacja/brak desktopu; CI i WSL zawsze `local`). Trafia do każdego bundle'a.
Projekt dopisuje tylko podział lekkie/ciężkie taski w `.ai/project.md` (przez
`/kit-project-edit`). Bez hooka blokującego.
