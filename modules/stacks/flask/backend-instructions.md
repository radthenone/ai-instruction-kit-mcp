# Backend instructions — Flask

## Zakres

Zmiany w `<backend>/**` (klucz `backend:` w `## Ścieżki` w `.ai/project.md`). Układ:
`stack:flask:structure`. Wersje bibliotek — lockfile; wątpliwość co do API = Context7,
nie pamięć (Flask-SQLAlchemy 3 i SQLAlchemy 2 zmieniły sporo względem starszych tutoriali).

## App factory i rozszerzenia

```python
def create_app(settings: Settings | None = None) -> Flask:
    """Zbuduj aplikację z konfiguracją z env (albo podaną w testach)."""
    app = Flask(__name__)
    app.config.from_mapping((settings or Settings()).flask_config())
    db.init_app(app)
    migrate.init_app(app, db)
    register_error_handlers(app)
    app.register_blueprint(orders_bp)
    return app
```

- Rozszerzenia w `extensions.py` bez aplikacji, podpinane przez `init_app` — dzięki temu
  testy tworzą świeżą aplikację z inną konfiguracją.
- Konfiguracja z env (`pydantic-settings`), nie z plików `.py` w repo (`arch:configuration`).
- Kod potrzebujący aplikacji poza requestem (CLI, zadania) używa `current_app`
  w `with app.app_context():`, nie importuje instancji.

## Blueprinty i widoki

- Blueprint per obszar domeny z `url_prefix`; dekoratory skrótowe `@bp.get`, `@bp.post`.
- Widok: parsuje wejście, woła serwis, zwraca `(dict, status)` albo
  `schema.model_dump(mode="json")`. Bez zapytań i reguł domeny w widoku.
- Tworzenie → `201`, brak treści → `204`, nie `200` dla wszystkiego.

```python
@bp.post("")
def create_order() -> tuple[dict, int]:
    """Utwórz zamówienie zalogowanego użytkownika."""
    payload = parse_body(OrderCreate)
    order = order_service.create(owner=current_user(), data=payload)
    return OrderRead.model_validate(order).model_dump(mode="json"), 201
```

## Walidacja — Pydantic v2

- Jeden helper `parse_body(Model)` / `parse_query(Model)`:
  `Model.model_validate(request.get_json())`; `ValidationError` łapie
  handler i zamienia na `422` w formacie projektu. Nie waliduj ręcznie `if "x" not in data`.
  Bez `silent=True` ani `or {}` — zepsuty JSON / zły `Content-Type` ma dać `400`/`415`,
  a nie przejść jako `{}` (przy `PATCH` z polami opcjonalnymi to cichy „sukces” bez zmian).
- Schematy wejścia i wyjścia osobno (`OrderCreate`, `OrderUpdate`, `OrderRead` z
  `model_config = ConfigDict(from_attributes=True)`); model ORM nigdy nie idzie do JSON-a
  bezpośrednio.
- `PATCH`: `payload.model_dump(exclude_unset=True)`.
- API v1 Pydantic (`.dict()`, `parse_obj`, `orm_mode`) jest przestarzałe.

## SQLAlchemy 2 przez Flask-SQLAlchemy 3

- `db = SQLAlchemy(model_class=Base)`, gdzie `class Base(DeclarativeBase)`; kolumny
  `Mapped[...] = mapped_column(...)`.
- Zapytania stylem 2.0: `db.session.execute(db.select(Order).where(...)).scalars()`,
  `db.get_or_404(Order, id)` w widoku, `db.session.get(Order, id)` w serwisie.
  `Order.query...` to styl legacy — nie dokładaj nowego kodu w tym stylu.
- Relacje ładowane jawnie (`selectinload`) tam, gdzie widok iteruje po kolekcji — inaczej N+1.
- Transakcja w serwisie: zmiany + `db.session.commit()`; przy wyjątku `rollback()`
  (Flask-SQLAlchemy zamyka sesję po requeście, ale nie cofa za Ciebie częściowego commita).

## Migracje (Flask-Migrate / Alembic)

- Każda zmiana modelu = migracja w tym samym PR: `flask db migrate -m "..."`, potem
  **przegląd** pliku — autogenerate nie wykrywa zmian nazw kolumn (drop + add) ani części
  constraintów.
- `flask db upgrade` w CI i przy deployu; migracje danych osobno od schematu (`arch:migrations`).
- Nie edytuj migracji już wypuszczonej na wspólną bazę.

## Błędy API

- Serwis rzuca wyjątki domenowe (`OrderNotFound`, `PermissionDenied`), nie `abort()` —
  serwis nie zna HTTP.
- `errors.py`: `app.register_error_handler(DomainError, ...)`, `ValidationError` (Pydantic),
  `HTTPException` (werkzeug — także 404/405 z routingu) → jednolity JSON (`arch:api-errors`).
  Bez handlera Flask zwraca HTML, którego klient API nie sparsuje.
- Nieobsłużony wyjątek → `500` w tym samym formacie, szczegóły tylko w logach. Handler
  na `InternalServerError` (oryginał w `e.original_exception`), nie na `Exception` —
  inaczej `TESTING=True` nie przepuści wyjątku do testu.

## Kontrakt API

- Zmiana kształtu odpowiedzi, ścieżki albo statusu = zmiana kontraktu. Przy
  `codegen: orval` (MCP `get_codegen`) schemat OpenAPI musi się odświeżyć i klient
  zregenerować w tym samym PR (task z `.ai/project.md`).

## Async

Flask to WSGI: widok `async def` działa, ale każdy request i tak zajmuje wątek workera —
nie daje współbieżności jak ASGI. Długie operacje → kolejka zadań (Slot `tasks` w Profilu),
nie wątki tworzone w widoku.

## Zasady obowiązkowe

- Najpierw wskaż pliki związane z problemem; nie dokładaj warstw, których repo nie ma.
- Type hints na publicznych funkcjach (`core:typing-python`); docstringi w języku Profilu.
- Testy do każdej zmiany zachowania (`stack:flask:testing`).

## Overlay projektu

Taski, porty, Docker i faktyczne ścieżki — `.ai/project.md`.
