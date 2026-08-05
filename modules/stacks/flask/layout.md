# Stack — Flask

## Zakres

API / app HTTP na Flask. Wymaga `--frontend` gdy serwujesz osobny klient SPA.

## Layout (generyczny)

```text
backend/
  src/
    app/
      blueprints/
        <feature>/
      extensions.py
      factory.py
      config.py
    tests/
  pyproject.toml
```

## Zasady

- Blueprints per feature; config z env (`arch:configuration`).
- JSON API: jednolite błędy (`arch:api-errors`).

## Powiązane

- `arch:testing`, `arch:security`
