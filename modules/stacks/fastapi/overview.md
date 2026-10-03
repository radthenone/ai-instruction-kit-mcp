# FastAPI — przegląd Stacku

Tier `backend: fastapi`. API HTTP na FastAPI + Pydantic v2, ORM SQLAlchemy 2 z migracjami
Alembic. Katalog kodu: klucz `backend:` w sekcji `## Ścieżki` w `.ai/project.md`
(dalej: `<backend>`).

## Biblioteki (typowy zestaw)

| Biblioteka | Rola |
|------------|------|
| `fastapi` (+ `uvicorn` / `fastapi[standard]`) | routing, zależności, OpenAPI |
| `pydantic` v2, `pydantic-settings` | schematy wejścia/wyjścia, konfiguracja z env |
| `sqlalchemy` 2.x (+ `asyncpg` albo `psycopg`) | ORM, styl `select()` |
| `alembic` | migracje schematu |
| `httpx`, `pytest`, `pytest-asyncio` albo `anyio` | testy |
| `ruff`, `mypy` / `pyright` | lint, typowanie (`core:typing-python`) |

Wersje sprawdzaj w lockfile (`<backend>/uv.lock`, `pyproject.toml`) — nie z pamięci.

## Zasady w skrócie

- **Router = warstwa HTTP.** `APIRouter` per obszar domeny; endpoint parsuje wejście,
  woła serwis i zwraca schemat. Bez zapytań SQL i reguł biznesowych w funkcji endpointu.
- **Zależności przez `Depends` z `Annotated`.** Sesja DB, aktualny użytkownik, ustawienia —
  wstrzykiwane, nie importowane jako globalne singletony.
- **Pydantic v2 na granicy.** Osobne schematy wejścia (`…Create`, `…Update`) i wyjścia
  (`…Read`); model ORM nigdy nie wychodzi z endpointu bez `response_model`.
- **Async świadomie.** `async def` tylko, gdy cały łańcuch I/O jest asynchroniczny;
  blokujący kod w `def` (FastAPI odpali go w puli wątków).
- **Kontrakt = OpenAPI z aplikacji.** Klient web/mobile generowany z schematu
  (`codegen:` w Profilu, `arch:api-contract`).
- **Błędy jednym formatem** — wyjątki domenowe + handlery (`arch:api-errors`).

## Moduły Stacku

- `stack:fastapi:structure` — układ katalogów i podział warstw
- `stack:fastapi:backend-instructions` — instrukcje agenta: routery, zależności, Pydantic,
  async, SQLAlchemy, Alembic, błędy
- `stack:fastapi:testing` — pytest + httpx, nadpisywanie zależności, baza testowa

## Powiązane

- `arch:api-contract`, `arch:api-errors`, `arch:configuration`, `arch:migrations`,
  `arch:testing`, `arch:security`, `core:typing-python`
