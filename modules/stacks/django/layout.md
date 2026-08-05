# Stack — Django (HTML templates)

## Zakres

Django **bez** DRF jako API — render HTML po stronie serwera (`templates/`).

`--frontend` / `--mobile` nie są wymagane; jeśli podane — ostrzeżenie (UI i tak w BE).

## Layout (generyczny)

```text
backend/
  src/
    apps/<name>/
      models/
      views/
      forms/
      templates/<name>/
      urls.py
    core/
      settings/
      urls.py
    templates/
    manage.py
  pyproject.toml
```

## Zasady

- Widoki + formy Django; nie zakładaj REST/Orval.
- Testy: `arch:testing` + pytest-django.
- Szczegóły ORM/migracji: `arch:migrations`.

## Powiązane

- `arch:monorepo-layout` — wybór layoutu z CLI
- `stack:django-drf:*` — gdy potrzebujesz REST zamiast HTML
