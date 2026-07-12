# Bugbot — guides-mcp (instruction-kit)

Reguły review dla tego repozytorium (Python MCP, moduły Markdown).

## Ogólne

- Kod źródłowy po angielsku; docstringi i dokumentacja modułów po polsku.
- Każda publiczna funkcja/klasa w `src/guides/` musi mieć type hints i docstring (Google style, PL).
- Nie commituj sekretów, tokenów, `.env`, kluczy API.

## Python (`src/guides/`)

If any changed file is under `src/guides/`:

- Flag missing type hints on new public `def` / `async def` without annotations.
- Flag missing docstrings on new public functions and classes.
- Flag bare `except:` or `except Exception:` without re-raise or explicit handling.
- If `resolver.py` or `manifest.py` changes without updates in `tests/`, add a non-blocking finding: "Rozważ testy dla zmian w resolverze/manifeście."

## Manifest i moduły

If the PR modifies `manifest.yaml` without corresponding `modules/**/*.md` (or vice versa for new module IDs):

- Add a blocking bug: "manifest.yaml i pliki modules/ muszą być zsynchronizowane."

If `profiles/*.yaml` changes break bundle resolution (missing module IDs):

- Add a blocking bug titled "Profil odwołuje się do nieistniejących modułów."

## Szablony (`templates/`)

If `templates/` changes without mention in `README.md` when adding new bootstrap files:

- Add a non-blocking finding: "Zaktualizuj README — sekcja plików do skopiowania w projekcie."

## Testy

If `src/guides/` changes and `tests/` has no changes:

- Add a non-blocking finding: "Brak aktualizacji testów przy zmianie logiki guides."

Przed pushem lokalnie: `python -m unittest discover -s tests`.

## Bezpieczeństwo

If any changed file matches patterns for hardcoded credentials (`password\s*=`, `api[_-]?key\s*=`, `Bearer\s+[A-Za-z0-9._-]{20,}`):

- Add a blocking bug titled "Possible hardcoded secret."

If `pyproject.toml` adds dependencies without version pin or known risky packages:

- Add a non-blocking security finding.

## Zakres zmian

Prefer minimal diffs. Flag drive-by refactors unrelated to the stated task in the same PR.
