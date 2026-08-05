# Bugbot — reguły projektu (monorepo Django + Expo)

Dostosuj ścieżki i taski do `.ai/project.md`. Bugbot ładuje ten plik przy review PR.

## Ogólne

- Odpowiedzi agentów po polsku; kod po angielsku; docstringi po polsku.
- Nie commituj `.env`, kluczy API, haseł, tokenów CI.
- Preferuj minimalny diff — flaguj drive-by refactory poza zakresem PR.

## Backend (`backend/`)

If the PR modifies files under `backend/` and there are no changes in `backend/**/test*.py`, `backend/**/tests/**`, or `backend/**/*_test.py`:

- Add a blocking bug titled "Missing tests for backend changes"
- Body: "Dodaj lub zaktualizuj testy pytest dla zmian w backendzie."

If changed files include serializers, viewsets, urls, or models affecting API
**and** the project uses Orval (`codegen: orval` in `.ai/project.md` / extras, or REST+FE without `codegen: manual|none`):

- Add a blocking bug unless `frontend/src/api/generated/` or Orval output was regenerated.
- Body: "Po zmianie kontraktu API uruchom `task ovral:generate` i commituj wygenerowany klient."

If overlay says `codegen: manual` or `codegen: none`: do **not** require Orval regeneration.

If any changed Python file lacks type hints on new public functions:

- Add a non-blocking finding per `core:typing-python`.

Flag `eval(`, `exec(`, raw SQL string concatenation with user input, and `permission_classes = []` on new viewsets without justification.

## Frontend (`frontend/`)

If the PR modifies `frontend/` without `task lints:frontend:typecheck` passing (assume CI will catch — flag risky patterns):

- Flag imports from `react-native` in `.web.tsx` files.
- Flag `any` on new public interfaces without `@ts-expect-error` justification.

If Expo native modules or `app.json` plugins change without EAS note in PR description:

- Add a non-blocking finding: "Zmiana native — wymaga EAS build, nie tylko OTA."

## Auth, ACL, płatności

If changed paths match `**/auth/**`, `**/permissions/**`, `**/acl/**`, `**/payments/**`, `**/stripe/**`:

- Add a blocking bug if webhook handlers skip signature verification.
- Recommend `/review-security` in PR description if not already run locally.

## Sekrety i compliance

If dependency files change (`package.json`, `bun.lock`, `pyproject.toml`, `uv.lock`, `requirements.txt`):

- Flag new dependencies with copyleft licenses (GPL, AGPL) if project policy forbids them.

If diff contains patterns like `sk_live_`, `pk_live_`, `AWS_SECRET`, `password = "`:

- Add a blocking bug titled "Possible hardcoded secret."

## Taskfile

When suggesting fixes, prefer `task <namespace>:<nazwa>` from `.ai/project.md` over raw docker/bash commands.

## Lokalny workflow

Przed pushem developer powinien uruchomić `/review-bugbot` w Cursor. Hook `.cursor/hooks/gate-push.sh` przypomina o tym przy `git push`.
