# Bugbot — reguły projektu

Sekcje Tierów (backend, web/mobile) Bootstrap zostawia tylko dla Tierów wybranych w `.ai/project.profile.yaml`.
Stack każdego Tieru: MCP `get_bundle`. Dostosuj ścieżki i taski do `.ai/project.md` (sekcja `## Ścieżki`). Bugbot ładuje ten plik przy review PR.

## Reguły projektu

<!-- project:rules -->
If the diff adds or renames a function, class, or test (`test_*`, `class Test*`; strings in `describe`/`it` are prose, not names) with a non-English name:

- Add a blocking bug titled "Non-English identifier"
- Body: "Nazwy funkcji, klas i testów po angielsku (terminy z nagłówków `CONTEXT.md`, jeśli istnieje); opis zachowania w docstringu."
<!-- /project:rules -->

## Ogólne

- Odpowiedzi agentów po polsku; kod po angielsku; docstringi po polsku.
- Nie commituj `.env`, kluczy API, haseł, tokenów CI.
- Preferuj minimalny diff — flaguj drive-by refactory poza zakresem PR.

If the diff adds or renames a function, class, or test (`test_*`, `class Test*`; strings in `describe`/`it` are prose, not names) with a non-English name:

- Add a blocking bug titled "Non-English identifier"
- Body: "Nazwy funkcji, klas i testów po angielsku (terminy z nagłówków `CONTEXT.md`, jeśli istnieje); opis zachowania w docstringu."

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

Przed pushem developer powinien uruchomić `/review-bugbot` w Cursor (przypomina o tym `/git-end`). Guard `git-guard.mjs` blokuje push bezpośrednio na main/master/dev.
