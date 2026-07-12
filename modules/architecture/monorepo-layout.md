# Monorepo — układ i rozdział frontend / backend

## Zasada nadrzędna

Frontend i backend to **osobne aplikacje** spięte **kontraktem API**, nie wspólnym kodem.

```text
project-root/
├── backend/          # Django + DRF — osobny lifecycle, osobne testy
├── frontend/         # Expo Router — osobny lifecycle, osobne testy
├── docker/           # obrazy, nginx, compose fragments
├── taskfiles/        # Taskfile modules
├── Taskfile.yml      # jeden punkt wejścia komend
├── .ai/
│   ├── project.profile.yaml   # wybór modułów instruction-kit
│   └── project.md             # overlay: porty, nazwy, taski
└── .github/workflows/         # CI/CD
```

## Rozdział odpowiedzialności

| Warstwa | Katalog | Odpowiada za |
|---------|---------|--------------|
| Backend | `backend/` | API, modele, auth server-side, integracje, Celery |
| Frontend | `frontend/` | UI, routing, stan klienta, konsumpcja API |
| Kontrakt | `backend/src/schema.yaml` + OpenAPI | Wspólny język FE/BE |
| Infra dev | `docker-compose.yml` | Postgres, Redis, MinIO, kontenery |
| Automatyzacja | `Taskfile.yml` | migracje, testy, lint, generowanie klienta |

## Czego NIE robić

- Nie importuj kodu backendu w frontendzie (ani odwrotnie).
- Nie duplikuj logiki biznesowej w obu warstwach — backend jest źródłem prawdy.
- Nie trzymaj instrukcji architektury w repo projektu — używaj instruction-kit MCP + overlay.

## Powiązane moduły

- `arch:api-contract` — OpenAPI, Orval, wersjonowanie API
- `arch:fe-be-separation` — granice warstw w kodzie
- `stack:django-drf:structure` — struktura katalogów backendu
- `stack:expo-router:structure` — struktura katalogów frontendu
