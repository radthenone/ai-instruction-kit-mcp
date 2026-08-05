# Stack — FastAPI

## Zakres

API HTTP z FastAPI + Pydantic. Wymaga `--frontend` (expo|react).

## Layout (generyczny)

```text
backend/
  src/
    app/
      api/
        routes/
        deps.py
      domain/
        <feature>/
      core/
        config.py
        logging.py
      main.py
    tests/
  pyproject.toml
```

## Zasady

- Kontrakt: OpenAPI z FastAPI; klient FE generowany (Orval / openapi-typescript).
- Błędy: spójny JSON (`arch:api-errors`).
- Integracje zewnętrzne: adaptery w osobnym pakiecie, nie w routerze.

## Powiązane

- `arch:api-contract`, `arch:testing`, `arch:security`
