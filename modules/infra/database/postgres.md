# PostgreSQL — baza danych

## Kiedy stosować

Domyślna baza relacyjna dla Django. Jeden cluster Postgres na aplikację (monolit) lub **database per service** (mikroserwisy).

## Konfiguracja Django

| Zmienna | Przykład |
|---------|----------|
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `POSTGRES_DB` | nazwa bazy w Docker |

- Engine: `django.db.backends.postgresql`
- Migracje: wyłącznie przez Django (`makemigrations` / `migrate`).
- Connection pooling (PgBouncer) — opcjonalnie na produkcji.

## Dev (Docker)

```text
postgres:16
port mapowany na host, np. 5434:5432  ← unikalny per projekt
volume: nazwany, np. `<projekt>-postgres-data`
```

## Zasady dla agentów

1. Przed zmianą modelu — sprawdź istniejące migracje w `apps/<app>/migrations/`.
2. Nie usuwaj migracji bez uzasadnienia i planu rollbacku.
3. Indeksy i constraints definiuj w modelu (`Meta.indexes`, `UniqueConstraint`).
4. Transakcje: `transaction.atomic()` w serializerze przy wielu zapisach.

## Alternatywy w katalogu

| Moduł | Kiedy |
|-------|-------|
| `infra:database:postgres` | domyślnie — ten plik |
| *(przyszłe)* `infra:database:mysql` | gdy projekt wymaga MySQL |

## Powiązane

- `infra:cache:redis` — cache obok Postgres, nie zamiast
- `stack:django-drf:backend-standard` — modele i migracje
