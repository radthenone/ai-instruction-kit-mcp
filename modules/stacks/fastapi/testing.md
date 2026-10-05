# Testing — FastAPI (pytest + httpx)

## Stack

| Narzędzie | Rola |
|-----------|------|
| `pytest` | runner |
| `httpx.AsyncClient` + `ASGITransport` | klient HTTP do aplikacji bez serwera |
| `pytest-asyncio` (albo plugin `anyio`) | testy `async def` |
| `fastapi.testclient.TestClient` | wariant synchroniczny (aplikacje bez async DB) |
| `factory-boy` / proste fabryki | dane testowe |
| `respx` / `unittest.mock` | HTTP vendorów |

Konfiguracja w `<backend>/pyproject.toml` (`[tool.pytest.ini_options]`), np.
`asyncio_mode = "auto"` i markery `integration`.

## Layout

```text
<backend>/tests/
  conftest.py          # app, client, session, nadpisania zależności
  factories.py
  <feature>/
    test_router.py     # HTTP: statusy, kształt odpowiedzi, uprawnienia
    test_service.py    # reguły domeny bez HTTP
```

## Klient i nadpisywanie zależności

```python
@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Klient HTTP do aplikacji z sesją testową zamiast produkcyjnej."""
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- Zależności podmieniaj przez `app.dependency_overrides`, nie przez `patch` na module
  z endpointem.
- Zalogowany użytkownik: nadpisz `get_current_user` w fixture `auth_client`, zamiast
  generować prawdziwe tokeny w każdym teście.
- `ASGITransport` nie odpala `lifespan` — zasoby z lifespan podstaw w fixture
  (albo `asgi-lifespan` / `TestClient` jako context manager).

## Baza testowa

- Osobna baza (env `DATABASE_URL` w konfiguracji testów), schemat z migracji Alembic
  (`alembic upgrade head` raz na sesję) — wtedy testy łapią też błędy migracji.
- Izolacja: każdy test w transakcji wycofywanej na końcu (sesja na połączeniu
  z `begin()` + `rollback()`), albo czyszczenie tabel — nie zależność od kolejności testów.
- SQLite zamiast produkcyjnej bazy tylko świadomie — inne typy i constrainty ukrywają błędy.

## Co testować

| Warstwa | Sprawdzaj |
|---------|-----------|
| Router | status, `response_model` (brak wycieku pól), 401/403/404/422, paginacja |
| Serwis | reguły domeny, transakcje, wyjątki domenowe |
| Integracje | adapter z zamockowanym HTTP vendora (`respx`); serwis z atrapą adaptera |

- Test błędu sprawdza format z `arch:api-errors`, nie tylko status.
- Nie mockuj własnego serwisu w teście routera, jeśli test ma sprawdzić zachowanie —
  mockuj granicę (vendor, zegar).

## Powiązane

- `arch:testing` — piramida i polityka CI
- `stack:fastapi:backend-instructions` — zależności, sesja, błędy
