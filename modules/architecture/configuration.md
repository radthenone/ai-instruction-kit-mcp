# Configuration — env i settings (12-factor light)

## Cel

Konfiguracja poza kodem; ten sam artefakt działa na dev/staging/prod przy zmianie env.

## Warstwy

```text
.env / secret manager     →  core/envs.py (lub równoważne)  →  core/settings/**
                                                                      ↓
                                                         kod aplikacji (tylko settings.*)
```

| Warstwa | Odpowiedzialność |
|---------|------------------|
| Env | sekrety, hosty, feature flagi runtime |
| `settings/` | złożenie Django/DRF/Celery z env; mapy scope→bucket |
| Kod domenowy | **zero** magicznych literałów hostów/kluczy |

Szczegóły registry providerów: `pattern:providers-and-settings`.

## Zasady

1. Wymagane zmienne waliduj przy starcie (fail-fast), nie przy pierwszym requeście.
2. Osobne pliki settings per env tylko gdy konieczne (`settings/local.py`) —
   preferuj jeden kod + różne env.
3. Feature flagi: bool/env lub prosty settings dict — dokumentuj default w overlay.
4. Publiczne zmienne FE (`EXPO_PUBLIC_*`): tylko URL API, publishable keys, flagi UI —
   nigdy secret (`arch:security`).
5. Nie commituj `.env`; commituj `.env.example` z pustymi/placeholderami.

## Checklist nowej zmiennej

- [ ] Nazwa w `.env.example` + opis w overlay / extras
- [ ] Odczyt w jednym miejscu (envs/settings), nie `os.environ` w view
- [ ] Domyślna wartość bezpieczna albo brak defaultu dla sekretów
- [ ] Dokumentacja: czy dotyczy BE, FE, czy obu

## Antywzorce

- `if settings.DEBUG: allow_all` skopiowane do prod przez pomyłkę konfiguracji.
- Różne nazwy tej samej zmiennej w Docker vs Taskfile vs docs.
- Feature flag jako commit comment / branch zamiast env.

## Powiązane

- `pattern:providers-and-settings`
- `arch:security`
- `infra:storage:s3` — scope → bucket w settings
