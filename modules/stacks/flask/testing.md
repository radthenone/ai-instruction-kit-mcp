# Testing — Flask (pytest)

## Stack

| Narzędzie | Rola |
|-----------|------|
| `pytest` | runner |
| `app.test_client()` | żądania HTTP do aplikacji bez serwera |
| `app.test_cli_runner()` | komendy `flask ...` (np. migracje, własne CLI) |
| `factory-boy` / proste fabryki | dane testowe |
| `responses` / `unittest.mock` | HTTP vendorów |

Konfiguracja w `<backend>/pyproject.toml` (`[tool.pytest.ini_options]`), markery
`integration` dla testów wymagających zewnętrznych usług.

## Layout

```text
<backend>/tests/
  conftest.py          # app, client, db, auth_client
  factories.py
  <feature>/
    test_routes.py     # HTTP: statusy, JSON, uprawnienia
    test_service.py    # reguły domeny bez HTTP
```

## Fixture aplikacji

```python
@pytest.fixture
def app() -> Iterator[Flask]:
    """Świeża aplikacja z konfiguracją testową i schematem bazy."""
    app = create_app(Settings(testing=True, database_url=TEST_DATABASE_URL))
    with app.app_context():
        db.create_all()          # albo upgrade() z Flask-Migrate — patrz niżej
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Klient HTTP testowanej aplikacji."""
    return app.test_client()
```

- Każdy test dostaje aplikację z factory — nigdy nie importuj instancji z `wsgi.py`.
- `TESTING=True` przepuszcza nieobsłużone wyjątki do testu zamiast zamieniać je na 500 —
  pod warunkiem, że 500 obsługuje handler `InternalServerError`, nie `Exception`.
- Zalogowany użytkownik: fixture `auth_client` ustawia nagłówek / sesję raz, testy
  nie powtarzają logowania.

## Baza testowa

- Osobna baza z env testów. `db.create_all()` jest szybkie, ale nie sprawdza migracji —
  przynajmniej jeden przebieg w CI na schemacie z `flask db upgrade`.
- Izolacja między testami: świeży schemat per test (jak wyżej) albo transakcja
  wycofywana na końcu — nie zależność od kolejności testów.
- SQLite zamiast produkcyjnej bazy tylko świadomie — inne typy i constrainty ukrywają błędy.

## Co testować

| Warstwa | Sprawdzaj |
|---------|-----------|
| Widok | status, JSON (brak wycieku pól), 401/403/404/422, format błędu z `arch:api-errors` |
| Serwis | reguły domeny, commit/rollback, wyjątki domenowe |
| Integracje | adapter z zamockowanym HTTP vendora; serwis z atrapą adaptera |

- `response.get_json()` zamiast parsowania `response.data` ręcznie.
- Mockuj granice (vendor, zegar), nie własny serwis w teście widoku.

## Powiązane

- `arch:testing` — piramida i polityka CI
- `stack:flask:backend-instructions` — factory, walidacja, błędy
