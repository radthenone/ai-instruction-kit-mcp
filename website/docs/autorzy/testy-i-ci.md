# Testy i CI

Kit ma testy `unittest` w `tests/` oraz suity powłoki. Pełna suita trwa kilkanaście minut, więc lokalnie uruchamiasz tylko to, czego dotykasz. Pełną suitę odpala CI.

## Lokalnie

W świeżym klonie najpierw `uv sync`. Polecenia z `--no-sync` nie instalują zależności, więc bez niego dostaniesz błąd importu, np. `yaml`.

```bash title="Git Bash · bash"
uv run python -m unittest discover -s tests -p test_bootstrap.py   # jeden moduł
uv run --no-sync python scripts/test_changed.py                     # moduły powiązane ze zmianami
uv run --no-sync python scripts/test_changed.py --dry-run           # tylko lista modułów
uv run --no-sync python scripts/test_changed.py -j 4                # równolegle
```

Uwaga: moduły testowe importują `_shell` z katalogu `tests/`. Uruchamiaj je przez `discover -s tests`, a nie przez `python -m unittest tests.test_x`. Inaczej dostaniesz `ModuleNotFoundError: No module named '_shell'`, który nie jest regresją.

Logi modułów trafiają do `.cache/test-runs/<timestamp>/<moduł>.log`.

## Testy guardów

```bash title="Git Bash · bash"
uv run python -m unittest discover -s tests -p test_guards.py    # tabela allow i deny każdego guarda
bash tests/test_guard_adapter.sh                                  # tłumaczenie kontraktu klientów
```

## Pełna suita

Pełna suita obejmuje też suity powłoki. Wciąga je `tests/test_shell_suites.py` do `unittest discover`. Odpala ją CI. Lokalnie pełną suitę uruchamiasz tylko wtedy, gdy zmieniasz coś, co przecina wiele modułów.

## CI

- unittest, w tym suity powłoki,
- smoke serwera FastMCP,
- test świeżości Brief Rules (`TestBriefRulesFreshness` w `tests/test_brief_rules.py`).

Lokalnie sprawdzisz świeżość Brief Rules tak:

```bash title="bash"
python3 scripts/render_brief_rules.py --check
```

## Zależności Pythona

Serwer MCP przypina major zależności, bo `uvx` rozwiązuje je od zera i nie bierze lokalnego `uv.lock`:

```toml title="pyproject.toml (fragment)"
mcp>=1.0.0,<2      # FastMCP w wersji 1.x. mcp 2.0 usuwa mcp.server.fastmcp
pyyaml>=6.0,<7
```

## Zasada dowodu

Zmiana bez dowodu, że komendy przechodzą, nie jest skończona. Podaj w PR polecenia, które uruchomiłeś, i ich wynik. Zob. [Review](../komendy/review.md), agent `review-tests`.
