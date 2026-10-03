# Struktura katalogów — FastAPI

`<backend>` = klucz `backend:` w sekcji `## Ścieżki` w `.ai/project.md`. Poniżej układ
względem tego katalogu — gdy repo ma inny, trzymaj się repo i opisz rozjazd w overlayu.

## Layout

```text
<backend>/
  src/app/
    main.py              # create_app(): FastAPI(lifespan=…), include_router, handlery błędów
    core/
      config.py          # Settings(BaseSettings) + get_settings()
      db.py              # engine, sessionmaker, get_session()
      security.py        # hasła, tokeny, get_current_user()
      errors.py          # wyjątki domenowe + exception handlers
    api/
      deps.py            # aliasy Annotated: SessionDep, CurrentUserDep, SettingsDep
      router.py          # APIRouter(prefix="/api") składający routery obszarów
    <feature>/           # obszar domeny, np. orders/
      router.py          # endpointy (HTTP)
      schemas.py         # Pydantic: OrderCreate, OrderUpdate, OrderRead
      models.py          # SQLAlchemy: class Order(Base)
      service.py         # reguły biznesowe, transakcje
      repository.py      # opcjonalnie — złożone zapytania
    integrations/        # adaptery vendorów (płatności, mail, storage)
  migrations/            # Alembic: env.py, versions/
  tests/
    conftest.py
    <feature>/
  alembic.ini
  pyproject.toml
```

## Podział odpowiedzialności

| Plik | Robi | Nie robi |
|------|------|----------|
| `router.py` | parsowanie wejścia, status HTTP, `response_model`, wołanie serwisu | SQL, reguły biznesowe |
| `schemas.py` | kształt danych API, walidacja pól | zapis do bazy |
| `service.py` | reguły domeny, transakcja, wołanie repozytorium / integracji | import `fastapi`, `Request` |
| `models.py` | mapowanie tabel, relacje | walidacja wejścia API |
| `integrations/` | jedyne miejsce importu SDK vendorów | logika domeny |

`repository.py` dokładaj, gdy zapytania przestają mieścić się czytelnie w serwisie —
nie z góry w każdym obszarze.

## Zasady

- Obszar domeny = katalog z własnym routerem; router obszaru nie importuje modeli
  innego obszaru — woła jego serwis.
- `main.py` tylko składa aplikację; konfiguracja w `core/config.py` (`arch:configuration`).
- Integracje zewnętrzne przez `pattern:capability-provider`, gdy Profil go włącza.
- Testy w `<backend>/tests/`, lustrzanie do obszarów (`stack:fastapi:testing`).
