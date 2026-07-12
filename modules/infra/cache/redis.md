# Redis — cache

## Kiedy stosować

Warstwa cache Django, sesje (opcjonalnie), rate limiting, pub/sub lekkich eventów.

**Redis jako cache ≠ Redis jako broker kolejki** — to osobne sloty w profilu:

| Slot profilu | Moduł | Rola |
|--------------|-------|------|
| `cache: redis` | ten plik | cache Django, sessions opcjonalnie |
| `queue: redis` | `infra:queue:redis` | broker Celery |

Możesz mieć oba jednocześnie (typowy dev: jeden kontener Redis, dwa logiczne DB index).

## Konfiguracja Django

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_CACHE_URL", default="redis://redis:6379/1"),
    }
}
```

## Zasady

- Klucze cache z prefiksem projektu: `{project}:...`
- TTL świadomie — słowniki długo, dane live krótko
- Invalidacja po mutacji API (sygnał, Celery, lub explicit delete w serializerze)

## Dev (Docker)

```text
redis:latest
bez publicznego portu (tylko sieć Docker) — wystarczy do dev
```

## Alternatywy

| Moduł | Kiedy |
|-------|-------|
| `infra:cache:redis` | domyślnie |
| *(przyszłe)* `infra:cache:memcached` | legacy / prosty cache |

## Powiązane

- `infra:queue:redis` — ten sam Redis, inny DB index, inna rola
- `infra:tasks:celery` — worker korzysta z brokera, nie z cache
