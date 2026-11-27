# Overlay projektu — TYLKO unikalne informacje tego repo

base: dev

> Reużywalna zasada architektoniczna (zadziałałaby w innym projekcie tej samej kategorii)?
> Nie wpisuj jej tu — zaproponuj zmianę w instruction-kit (`core:repo-first`, sekcja
> "Nowa zasada architektoniczna — dokąd ją zapisać"). Tu tylko fakty **tego** repo.

## Codegen

Brak — repo nie ma pary backend + klient. Źródło prawdy: `codegen:` w
`.ai/project.profile.yaml` (tu `none`), odczyt przez MCP `get_codegen`.

## Struktura

- `src/guides/` — serwer MCP (Python): `server.py`, `resolver.py`, `manifest.py`, `bootstrap.py`
- `manifest.yaml` — rejestr modułów, Tierów i bundli (ADR-0001)
- `modules/` — treść modułów Markdown serwowana przez MCP
- `templates/` — pliki instalowane w projektach przez `scripts/bootstrap-project.sh`
- `tests/` — `unittest` (+ suity `tests/*.sh` przez `test_shell_suites.py`)

## Komendy

- Testy lokalne i dla review: `uv run --no-sync python scripts/test_changed.py` + konkretne moduły `uv run python -m unittest tests.<moduł>`
- Szybko: `uv run python -m unittest tests.test_resolver tests.test_manifest_mappings tests.test_mcp_compat`
- Pełna suita: **NIE uruchamiać `unittest discover -s tests` lokalnie ani podczas review** (trwa ~15–20 min przez suity bash — pełną suitę weryfikuje wyłącznie CI na PR).

Brak Taskfile i Dockera.

## Lockfile (weryfikacja wersji)

- `pyproject.toml`, `uv.lock`

## Stan implementacji vs instruction-kit

Repo jest samym kitem — Tiery `none`, w Bundle'ach sam core.
