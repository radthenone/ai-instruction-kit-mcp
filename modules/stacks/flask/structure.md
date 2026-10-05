# Struktura katalogów — Flask

`<backend>` = klucz `backend:` w sekcji `## Ścieżki` w `.ai/project.md`. Poniżej układ
względem tego katalogu — gdy repo ma inny, trzymaj się repo i opisz rozjazd w overlayu.

## Layout

```text
<backend>/
  src/app/
    __init__.py          # create_app(settings: Settings | None) → Flask
    config.py            # Settings(BaseSettings) — wartości z env
    extensions.py        # db = SQLAlchemy(model_class=Base), migrate = Migrate()
    errors.py            # wyjątki domenowe + register_error_handler
    validation.py        # parse_body(Model) / parse_query(Model) → Pydantic
    <feature>/           # obszar domeny, np. orders/
      __init__.py        # bp = Blueprint("orders", __name__, url_prefix="/api/orders")
      routes.py          # widoki (HTTP)
      schemas.py         # Pydantic: OrderCreate, OrderUpdate, OrderRead
      models.py          # SQLAlchemy: class Order(db.Model)
      service.py         # reguły biznesowe, transakcje
    integrations/        # adaptery vendorów (płatności, mail, storage)
  migrations/            # Flask-Migrate (Alembic): env.py, versions/
  tests/
    conftest.py
    <feature>/
  wsgi.py                # app = create_app() — punkt wejścia gunicorna
  pyproject.toml
```

## Podział odpowiedzialności

| Plik | Robi | Nie robi |
|------|------|----------|
| `routes.py` | parsowanie wejścia przez Pydantic, status HTTP, `jsonify` / dict | SQL, reguły biznesowe |
| `schemas.py` | kształt danych API, walidacja pól | zapis do bazy |
| `service.py` | reguły domeny, `db.session.commit()`, wołanie integracji | `request`, `abort`, `jsonify` |
| `models.py` | mapowanie tabel, relacje | walidacja wejścia API |
| `extensions.py` | instancje rozszerzeń bez aplikacji | konfiguracja z env |

## Zasady

- Blueprint rejestrowany w `create_app` (`app.register_blueprint(bp)`); obszar nie importuje
  modeli innego obszaru — woła jego serwis.
- `wsgi.py` jest jedynym miejscem, gdzie aplikacja powstaje przy imporcie.
- Integracje zewnętrzne przez `pattern:capability-provider`, gdy Profil go włącza.
- Testy w `<backend>/tests/`, lustrzanie do obszarów (`stack:flask:testing`).
