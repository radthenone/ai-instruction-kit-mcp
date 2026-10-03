# Flask — przegląd Stacku

Tier `backend: flask`. JSON API na Flask 3 z walidacją Pydantic v2, ORM SQLAlchemy 2
(przez Flask-SQLAlchemy) i migracjami Alembic (przez Flask-Migrate). Katalog kodu: klucz
`backend:` w sekcji `## Ścieżki` w `.ai/project.md` (dalej: `<backend>`).

## Biblioteki (typowy zestaw)

| Biblioteka | Rola |
|------------|------|
| `flask` 3.x | aplikacja, blueprinty, request/response |
| `pydantic` v2 (+ `pydantic-settings`) | walidacja wejścia, serializacja wyjścia, konfiguracja |
| `flask-sqlalchemy` 3.x + `sqlalchemy` 2.x | ORM, styl `db.select()` |
| `flask-migrate` (Alembic) | migracje schematu |
| `gunicorn` | serwer WSGI na produkcji |
| `pytest` | testy (`app.test_client()`) |
| `ruff`, `mypy` / `pyright` | lint, typowanie (`core:typing-python`) |

Wersje sprawdzaj w lockfile (`<backend>/uv.lock`, `pyproject.toml`) — nie z pamięci.

## Zasady w skrócie

- **App factory.** `create_app(config)` buduje aplikację; rozszerzenia (`db`, `migrate`)
  tworzone na poziomie modułu i podpinane przez `init_app`. Żadnego globalnego `app`.
- **Blueprint per obszar domeny.** Widok parsuje wejście, woła serwis, zwraca JSON.
- **Pydantic na granicy.** Flask nie waliduje sam — każde wejście przechodzi przez
  `Model.model_validate(...)`, każde wyjście przez schemat (`model_dump(mode="json")`).
- **Błędy jednym formatem** — wyjątki domenowe + `register_error_handler` (`arch:api-errors`).
- **Kontrakt API jawnie.** Flask nie generuje OpenAPI sam — przy kliencie web/mobile
  i `codegen: orval` schemat musi powstawać z kodu (np. `flask-openapi3`, `spectree`,
  `apispec`) — wybór w `.ai/project.md`, `arch:api-contract`.

## Moduły Stacku

- `stack:flask:structure` — układ katalogów i podział warstw
- `stack:flask:backend-instructions` — instrukcje agenta: factory, blueprinty, Pydantic,
  SQLAlchemy, migracje, błędy
- `stack:flask:testing` — pytest, fixture aplikacji, baza testowa

## Powiązane

- `arch:api-contract`, `arch:api-errors`, `arch:configuration`, `arch:migrations`,
  `arch:testing`, `arch:security`, `core:typing-python`
