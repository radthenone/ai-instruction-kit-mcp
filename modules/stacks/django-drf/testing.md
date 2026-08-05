# Testing — Django + DRF (pytest)

## Stack

| Narzędzie | Rola |
|-----------|------|
| `pytest` | runner |
| `pytest-django` | DB, settings, klient HTTP |
| `factory-boy` (+ `pytest-factoryboy` opcjonalnie) | fabryki modeli |
| `freezegun` / `time-machine` | czas |
| `responses` / `httpx` mock / `unittest.mock` | HTTP vendorów |

Ustawienia: `DJANGO_SETTINGS_MODULE` w `pytest.ini` lub `[tool.pytest.ini_options]`
w `pyproject.toml`. Lokalnie: `--reuse-db` przyspiesza (pytest-django).

```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings.test
addopts = --reuse-db -ra
markers =
    integration: wymaga Docker / zewnętrznych serwisów
    e2e: przeglądarka / pełny stack
```

## Layout

```text
backend/src/tests/
  conftest.py                 # api_client, user, auth helpers
  factories/
    __init__.py
    user.py
    <domain>.py
  accounts/
    test_serializers.py
    test_views.py
  <domain>/
    test_serializers.py
    test_views.py
    test_permissions.py
  integration/
    test_checkout_flow.py     # @pytest.mark.integration
```

Katalog `tests/` leży obok `apps/` / `core/` — **nie** wewnątrz każdej appki
(`stack:django-drf:structure`).

## Priorytet testów (DRF-first)

1. **Serializery** — `is_valid`, `create`/`update`, błędy walidacji, edge cases.
2. **Viewsety / API** — status codes, auth, izolacja querysetu, permissions.
3. **Permissions / ACL** — forbidden vs allowed dla ról.
4. **Modele** — tylko gdy jest nietrywialna logika (`clean`, status transitions).
5. **Celery / adaptery** — task z mockiem vendor; nie testuj samego `.delay()` bez body.
6. **Integracja** — pełny flow (np. checkout) przez `APIClient` + DB.

Nie pisz osobnych testów dla cienkiego wrappera `service → serializer.save()`.

## Dostęp do bazy

Każdy test potrzebujący ORM:

```python
import pytest

@pytest.mark.django_db
def test_creates_order(order_factory):
    order = order_factory()
    assert order.pk is not None
```

- Domyślnie: transakcja + rollback per test (jak Django `TestCase`).
- Potrzebujesz prawdziwych commitów / sygnałów `on_commit`:
  `@pytest.mark.django_db(transaction=True)` lub fixture `transactional_db`.
- N+1: `django_assert_num_queries` / `django_assert_max_num_queries` (pytest-django).

Unikaj autouse `enable_db_access_for_all_tests` w dużych suite — ukrywa które testy
naprawdę potrzebują DB i spowalnia czyste unit’y bez ORM.

## Klient API

Preferuj `APIClient` (DRF) przez fixture w `conftest.py`:

```python
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def auth_client(api_client: APIClient, user_factory) -> APIClient:
    user = user_factory()
    api_client.force_authenticate(user=user)
    return api_client
```

Dla sesji allauth / cookie — osobny helper zgodny z capability auth projektu
(nie mieszaj JWT i headless w jednym teście bez intencji).

## Fabryki

```python
# tests/factories/order.py
import factory
from apps.orders.models import Order

class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    status = "draft"
    # relacje: SubFactory / LazyAttribute — nie hardcode PK
```

Zasady:
- Fabryki budują **minimalny** poprawny obiekt; w teście nadpisuj tylko to, co scenariusz zmienia.
- Nie używaj `loaddata` / dumpów SQL jako domyślnej ścieżki.
- Wspólne scenariusze (user + cart) → fixture kompozytowa, nie kopiuj setupu.

## Mockowanie integracji

```python
from unittest.mock import MagicMock, patch

@patch("core.integrations.stripe.client.StripeClient.create_session")
def test_checkout_calls_stripe(mock_session: MagicMock, auth_client, ...):
    mock_session.return_value = {"id": "cs_test"}
    ...
```

Patch **ścieżkę użycia** (gdzie importuje kod produkcyjny), nie „gdzie zdefiniowano”.
Nie mockuj własnych ViewSetów / querysetów capability w tym samym monolicie.

## Nazewnictwo i parametryzacja

```python
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({}, 400),
        ({"quantity": 0}, 400),
        ({"quantity": 1}, 201),
    ],
)
@pytest.mark.django_db
def test_add_line_validation(auth_client, payload, expected_status):
    ...
```

Nazwy: `test_<akcja>_<warunek>_<oczekiwany_efekt>`.

## Co asertować w API

| Sprawdź | Przykład |
|---------|----------|
| Status | `assert response.status_code == 403` |
| Kształt / pola | klucze JSON, typy, snapshot ceny |
| Efekt DB | `Order.objects.filter(...).exists()` |
| Izolacja | user A nie dostaje obiektu user B |
| Permissions | anon → 401/403; rola bez prawa → 403 |

Unikaj samego `assert response.status_code == 200` bez body / side-effect.

## Integration

```python
@pytest.mark.integration
@pytest.mark.django_db
def test_checkout_end_to_end(...):
    ...
```

Uruchamiane gdy compose (Postgres, Redis, MinIO) jest dostępne.
W CI PR: albo job z services, albo `-m "not integration"` + nightly z markerem.

## Komendy

```bash
task test:backend
# lub
cd backend && pytest -m "not integration and not e2e"
```

Lint/typecheck osobno (`arch:ci-cd`, `taskfiles/lints.yml`).

## Antywzorce

- `TestCase` Django obok pytest bez potrzeby — trzymaj jeden styl (pytest).
- Tworzenie obiektów przez `Model.objects.create(...)` w 20 testach zamiast fabryki.
- Test „god object” z 15 assertami bez struktury.
- Zależność od kolejności (`pytest-order` jako proteza).
- Prawdziwe wywołania Stripe/S3 w unitach.

## Powiązane

- `arch:testing` — piramida i polityka monorepo
- `stack:django-drf:structure` — drzewo `src/tests/`
- `stack:django-drf:backend-standard` — priorytet warstw kodu
- `capability:auth` / `capability:payments` — scenariusze domenowe
