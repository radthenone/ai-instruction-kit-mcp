# CI/CD — pipeline, jakość, deploy

## Filozofia

Monorepo = **osobne joby** per warstwa. Jeden czerwony test nie powinien ukrywać która platforma padła. Taskfile jest źródłem prawdy komend — CI wywołuje taski, nie kopiuje składni ad hoc.

## Macierz platform

| Job | Co testuje | Kiedy uruchamiać |
|-----|------------|------------------|
| `backend-lint` | ruff | każdy PR |
| `backend-types` | mypy / pyright / **pyrefly** | każdy PR |
| `backend-test` | pytest (+ docker compose test) | każdy PR |
| `frontend-lint` | eslint | każdy PR |
| `frontend-types` | tsc strict | każdy PR |
| `frontend-test` | jest (jeśli jest) | każdy PR |
| `api-contract` | schema drift + Orval check | PR dotykający API |
| `eas-build` | native binary | tag / manual / nightly |

Mobile **nie blokuje** każdego PR kosztem EAS — lint + tsc wystarczą na PR; EAS na merge do main lub tag.

## Przykład CI (typowe monorepo Django + Expo)

Job CI uruchamia: ruff → typecheck (Pyrefly / mypy) → pytest `-m "not integration"`.
Frontend: eslint → tsc → prettier.

**Często brakuje względem szkieletu poniżej:** job `api-contract`, testy integracyjne w Dockerze na PR, testy frontendowe, EAS.
Pre-commit (ruff, eslint) działa **lokalnie** — nie zawsze w CI.

## GitHub Actions — szkielet docelowy

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres: ...
      redis: ...
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: task lints:backend:ruff:check
      - name: Typecheck
        run: task lints:backend:typecheck
      - name: Test
        run: task test:backend

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - name: Install
        run: cd frontend && bun install --frozen-lockfile
      - name: Lint
        run: task lints:frontend:lint:check
      - name: Typecheck
        run: task lints:frontend:typecheck

  api-contract:
    runs-on: ubuntu-latest
    steps:
      - name: Verify OpenAPI / generated client
        run: |
          task ovral:generate
          git diff --exit-code frontend/src/api/generated/
```

## API contract gate

Po zmianie serializerów / viewsetów:

1. Backend generuje / aktualizuje schema.
2. `task ovral:generate`
3. CI: `git diff --exit-code` na `frontend/src/api/generated/` — brak driftu.

Zapobiega mergowi PR z rozjechanym kontraktem FE/BE.

## Backend testy integracyjne

- `docker-compose.test.yml` — Postgres + Redis (+ MinIO jeśli testujesz files).
- Fixtures pytest — transakcje rollback per test (`django_db`).
- Testy webhook Stripe: mock podpisu w adapterze, nie live API.

## Frontend — mobile vs web w CI

| Check | Wykrywa |
|-------|---------|
| `tsc --noEmit` | błędy typów w `.native.tsx` i `.web.tsx` |
| eslint | importy native w web-only |
| (opcj.) Maestro / Detox | E2E mobile — później |

Osobny job `frontend-web-build` opcjonalny — `expo export --platform web` na main.

## EAS Build (mobile)

```yaml
# .github/workflows/eas-build.yml — workflow_dispatch lub tag v*
jobs:
  build:
    steps:
      - uses: expo/expo-github-action@v8
      - run: eas build --platform all --profile production --non-interactive
```

Sekrety: `EXPO_TOKEN`, `STRIPE_PUBLISHABLE_KEY` w EAS Secrets — nie w repo.

## Deploy backend (VPS / Docker)

```text
1. docker build backend
2. task db:migrate (na środowisku docelowym)
3. rolling restart worker + beat + web
4. healthcheck GET /health/
```

## Deploy web

- Static: artefakt z `expo export --platform web` → nginx / CDN.
- API URL przez env build-time (`EXPO_PUBLIC_API_URL`).

## Deploy mobile

- Sklepy: EAS Submit po `eas build`.
- OTA (Expo Updates): tylko JS bundle — **nie** dla zmian native (Stripe plugin, permissions).

## Sekrety

| Gdzie | Co |
|-------|-----|
| GitHub Secrets | CI tokens, test DB |
| EAS Secrets | Stripe publishable, API URL prod |
| `.env` lokalnie | nigdy w git |

## Branch protection (rekomendacja)

- Wymagaj: backend-test + frontend-types + api-contract (jeśli dotyczy).
- Opcjonalnie: check `Cursor Bugbot` (AI review na PR).
- Opcjonalnie: code review człowieka przed merge.

## AI code review (Bugbot)

Pełny workflow: moduł `core:code-review` (bundle `devops` lub `architecture`).

Skrót:

1. Lokalnie przed pushem: `/review-bugbot` w Cursor (hook `.cursor/hooks/gate-push.sh` przypomina).
2. Po pushu: Bugbot na PR (automatycznie lub `cursor review` w komentarzu).
3. Reguły zespołowe: `.cursor/BUGBOT.md` + dashboard Bugbota.

Szablony plików: `templates/cursor/` w instruction-kit.

## Powiązane

- `core:code-review` — lokalny review, GitHub, raporty, dry-run API
- `arch:platforms` — trzy cele buildu
- `arch:api-contract` — Orval
- Overlay projektu — konkretne nazwy tasków w `.ai/project.md`
