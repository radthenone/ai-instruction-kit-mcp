# Backend instructions — FastAPI

## Zakres

Zmiany w `<backend>/**` (klucz `backend:` w `## Ścieżki` w `.ai/project.md`). Układ:
`stack:fastapi:structure`. Wersje bibliotek — lockfile; API FastAPI/Pydantic/SQLAlchemy
zmienia się między wydaniami, więc wątpliwość = Context7, nie pamięć.

## Routery

- Jeden `APIRouter` na obszar domeny, `prefix` i `tags` przy routerze, nie przy każdym
  endpoincie. Składanie w `api/router.py`, w `main.py` jedno `include_router`.
- Endpoint deklaruje `response_model` (albo typ zwracany) i `status_code`; tworzenie → `201`,
  brak treści → `204`.
- Funkcja endpointu: parsuje wejście, woła serwis, zwraca schemat. Reguły biznesowe
  i zapytania SQL mieszkają w serwisie.

```python
router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, session: SessionDep, user: CurrentUserDep) -> Order:
    """Utwórz zamówienie bieżącego użytkownika."""
    return await order_service.create(session, owner=user, data=payload)
```

## Zależności (`Depends`)

- Aliasy `Annotated` w `api/deps.py`: `SessionDep = Annotated[AsyncSession, Depends(get_session)]`,
  `CurrentUserDep`, `SettingsDep`. Endpointy używają aliasów, nie powtarzają `Depends(...)`.
- Sesja DB z zależności z `yield` — jedna sesja na request, zamknięcie w `finally`.
- Uprawnienia jako zależności (`require_role("admin")`) albo `dependencies=[...]` na routerze.
- Nie trzymaj stanu w modułach (globalna sesja, klient HTTP tworzony przy imporcie).
  Zasoby na cały proces — w `lifespan` (`FastAPI(lifespan=...)`), nie w `@app.on_event`.

## Pydantic v2

- Schematy wejścia i wyjścia osobno: `OrderCreate`, `OrderUpdate` (pola opcjonalne),
  `OrderRead` (`model_config = ConfigDict(from_attributes=True)`).
- Walidacja: `Field(...)` z ograniczeniami, `@field_validator` / `@model_validator`.
  API v1 (`@validator`, `.dict()`, `orm_mode`, `parse_obj`) jest przestarzałe — używaj
  `model_dump()`, `model_validate()`, `from_attributes`.
- `PATCH`: `payload.model_dump(exclude_unset=True)`, żeby nie nadpisać pól, których klient
  nie wysłał.
- Konfiguracja: `pydantic-settings` (`BaseSettings`, `SettingsConfigDict(env_file=...)`)
  + `get_settings()` z `lru_cache`; wartości z env, nie z kodu (`arch:configuration`).

## Async vs sync

- `async def` endpoint → wszystko w środku asynchroniczne: `AsyncSession`, `httpx.AsyncClient`,
  sterownik `asyncpg`. Jedno blokujące wywołanie (`requests`, `time.sleep`, sync ORM)
  zatrzymuje cały event loop.
- Biblioteka tylko synchroniczna → endpoint `def` (pula wątków) albo
  `await run_in_threadpool(fn, ...)`.
- Nie mieszaj sync i async sesji SQLAlchemy w jednym obszarze.
- Ciężka praca poza requestem → kolejka zadań (Slot `tasks` w Profilu); `BackgroundTasks`
  tylko dla krótkich czynności „po odpowiedzi”, bez gwarancji wykonania.

## SQLAlchemy 2

- Modele: `class Base(DeclarativeBase)`, kolumny `Mapped[...] = mapped_column(...)`,
  relacje `Mapped[list["OrderLine"]] = relationship(back_populates=...)`.
- Zapytania stylem 2.0: `await session.scalars(select(Order).where(...))`,
  `session.get(Order, id)`. Bez `session.query(...)` (styl 1.x).
- Async + relacje: jawne ładowanie (`selectinload`, `joinedload`) — leniwe ładowanie
  w async rzuca `MissingGreenlet`. Pętla po wynikach bez eager loadingu = N+1.
- Transakcja w serwisie: `async with session.begin():` albo jawne `commit()`; endpoint
  nie commituje. `expire_on_commit=False` w `async_sessionmaker`, gdy zwracasz obiekt po commicie.

## Alembic

- Każda zmiana modelu = migracja w tym samym PR: `alembic revision --autogenerate -m "..."`.
- Autogenerate **przeglądaj** — nie wykrywa zmian nazw kolumn (zrobi drop + add), części
  typów i constraintów. Popraw ręcznie przed commitem.
- `env.py` importuje `Base.metadata` ze wszystkich modeli; konfiguracja async przez
  `run_sync`. Migracje danych osobno od zmian schematu (`arch:migrations`).
- Nie edytuj migracji już wypuszczonej na wspólną bazę — nowa migracja.

## Błędy API

- Serwis rzuca wyjątki domenowe (`OrderNotFound`, `PermissionDenied`), nie `HTTPException` —
  serwis nie zna HTTP.
- `core/errors.py`: `@app.exception_handler(DomainError)` mapuje na status i jednolity JSON
  (`arch:api-errors`); w routerze `HTTPException` tylko dla błędów czysto HTTP.
- `RequestValidationError` (422) — zostaw format FastAPI albo przemapuj w jednym handlerze
  na format projektu; nie per endpoint.
- Odpowiedzi błędów w OpenAPI: `responses={404: {"model": ErrorRead}}`, żeby wygenerowany
  klient znał ich typ.

## Kontrakt API

- Zmiana schematu odpowiedzi, ścieżki albo statusu = zmiana kontraktu. Przy
  `codegen: orval` (MCP `get_codegen`) — regeneracja klienta w tym samym PR
  (task z `.ai/project.md`).
- `operation_id` stabilne (np. `generate_unique_id_function`), żeby nazwy funkcji
  w wygenerowanym kliencie nie zmieniały się przy przenosinach endpointów.

## Zasady obowiązkowe

- Najpierw wskaż pliki związane z problemem; nie dokładaj warstw, których repo nie ma.
- Type hints na publicznych funkcjach (`core:typing-python`); docstringi w języku Profilu.
- Testy do każdej zmiany zachowania (`stack:fastapi:testing`).

## Overlay projektu

Taski, porty, Docker i faktyczne ścieżki — `.ai/project.md`.
