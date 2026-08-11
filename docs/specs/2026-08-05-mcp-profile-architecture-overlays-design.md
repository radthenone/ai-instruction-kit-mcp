# MCP profile + architecture + overlays — design

**Status:** approved design (2026-08-05) — **CLI / resolver jeszcze nie**  
**Do czasu implementacji:** README, AGENTS i `use-guides` opisują **obecny** kontrakt (`--preset` + `.ai/project.md`).  
**Approach:** jawne flagi CLI (podejście 1) — `--profile` + `--backend` + `--frontend` ± `--mobile` + `--overlays`

## Goals

- Uprościć konfigurację projektu: **zero** lokalnego `project.profile.yaml` i **zero** `.ai/project.md`.
- `_base` zawsze fundamentem; kategorie (`shop`, …) tylko dokładają domain/capability/infra.
- Stack FE/BE wybierany wyłącznie w `mcpServers.args` (nie hardcodowany w YAML kategorii).
- Overlay zasad tylko przez jawną flagę `--overlays` (dowolne ścieżki MD).
- Każdy wariant backendu i layoutu frontu ma **osobny MD** z **generycznym** drzewem katalogów (bez domeny shop/todo).

## Non-goals

- Generowanie szkieletu kodu aplikacji (kit = instrukcje, nie scaffolder).
- Facety/`--tag` (pozostaje planowane, poza tym designem).
- Runtimeowa zmiana treści bundle per klient AI (`--clients` nadal tylko metadane).
- Migracja istniejących repo aplikacji w tym PR (osobny follow-up / bootstrap update).

## Decyzje (zatwierdzone w rozmowie)

| Temat | Decyzja |
|-------|---------|
| Lokalny YAML profilu | Usunięty z normalnego flow |
| `.ai/project.md` | Usunięty |
| Overlay | Tylko `--overlays PATH…` (np. `.ai/extras.md`, `.ai/AGENTS.md`) |
| Kategoria | `--profile NAME` (rename z `--preset`); zawsze `extends` `_base` |
| Stack | Podejście 1: jawne `--backend` / `--frontend` / opcjonalne `--mobile` |
| Django goły vs DRF | `django` = HTML templates; `django-drf` = REST |
| Backend v1 | Wszystkie 4: `django`, `django-drf`, `fastapi`, `flask` |
| Frontend | `--frontend expo\|react` = web; `--mobile expo\|react-native` opcjonalnie |
| Expo+Expo | Jeden katalog `frontend/` (web+native w jednym tree) |
| Tree w MD | Generyczne placeholdery (`apps/<name>/`, `features/<feature>/`) |
| Codegen FE | Flaga `--codegen orval\|manual\|none` (+ do czasu CLI: `codegen:` w overlay) |

## Sekcja 1 — warstwy args MCP

| Flaga | Rola | Default |
|-------|------|---------|
| `--profile NAME` | Kategoria z `profiles/NAME.yaml` w kicie | `_base` |
| `--backend VALUE` | Layout + reguły BE | bootstrap: `django-drf` |
| `--frontend VALUE` | Stack web | bootstrap: `expo` |
| `--mobile VALUE` | Opcjonalny stack mobile | brak |
| `--codegen VALUE` | Generowanie klienta API FE (`orval` \| `manual` \| `none`) | zob. niżej |
| `--overlays PATH` | 0..N plików MD (append); nadpisują zasady | brak |
| `--workspace PATH` | Root repo aplikacji | jak dziś |
| `--language` / `--clients` | bez zmian semantycznych | jak dziś |

### `--codegen` (Orval opcjonalny)

| Wartość | Znaczenie |
|---------|-----------|
| `orval` | FE generuje klienta z OpenAPI; po zmianie API regeneruj + commit |
| `manual` | Ręczny klient — bez Orval; review wymaga świadomej aktualizacji |
| `none` | Brak klienta generowanego (np. Django HTML) |

**Default bootstrap:** `orval` gdy backend REST + podano `--frontend`; inaczej `none`.  
**Do czasu CLI:** to samo w overlay: `codegen: orval|manual|none` — `get_overlay` + reviewery FE/BE.  
`get_architecture` (docelowo) zwraca też `codegen`.

**Usuwamy:** lokalny `--profile PATH`, auto-load `.ai/project.md`, wymaganie `project.profile.yaml`.

**Kompat (1 release):** `--preset NAME` = alias `--profile NAME`.

Przykład:

```json
"args": [
  "guides-mcp",
  "--profile", "shop",
  "--backend", "django-drf",
  "--frontend", "react",
  "--mobile", "expo",
  "--codegen", "orval",
  "--overlays", "${workspaceFolder}/.ai/extras.md",
  "--language", "pl",
  "--clients", "all",
  "--workspace", "${workspaceFolder}"
]
```

## Sekcja 2 — enumy i macierz FE

### `--backend`

| Wartość | Znaczenie |
|---------|-----------|
| `django` | Django + szablony HTML, bez REST |
| `django-drf` | Django + DRF (REST dla klientów) |
| `fastapi` | FastAPI + Pydantic |
| `flask` | Flask |

Przy `django` (HTML): `--frontend` / `--mobile` opcjonalne; jeśli podane — ostrzeżenie w logu / toolu, nie blokują startu (UI i tak w BE).

Przy `django-drf` | `fastapi` | `flask`: `--frontend` wymagane (walidacja CLI).

### `--frontend` + `--mobile`

| `--frontend` | `--mobile` | Layout |
|--------------|------------|--------|
| `expo` | *(brak)* | tylko Expo web |
| `expo` | `expo` | jeden `frontend/` Expo (web+native) |
| `react` | *(brak)* | tylko React web |
| `react` | `expo` | `frontend/web` + `frontend/mobile` (Expo) + `packages/` |
| `react` | `react-native` | `frontend/web` + `frontend/mobile` (RN) + `packages/` |
| `expo` | `react-native` | **deny** (niespójne) |

Nazwa mobile: zawsze `react-native` (nie `react-rn`).

## Sekcja 3 — resolver i tools

### Skład bundle (`get_bundle`)

1. Moduły z YAML `--profile` (domain/capability/infra/patterns z `_base` + kategorii) — **bez** stacków FE/BE w YAML.
2. Moduł(y) layoutu `--backend`.
3. Moduł(y) z macierzy `--frontend` ± `--mobile`.
4. Treści z `--overlays` (najwyższy priorytet — overlay zasad).

### Tools

| Tool | Zachowanie |
|------|------------|
| `get_bundle` | jak wyżej |
| `get_overlay` | concatenacja plików z `--overlays` (puste = komunikat „brak overlays”) |
| `get_architecture` | **nowy** — JSON/tekst: profile, backend, frontend, mobile, codegen, overlays paths |
| `list_profiles` | rename z `list_presets` (alias `list_presets` 1 release) |
| `get_language` / `get_clients` | bez zmian |

### Env (opcjonalne, lustrzane do CLI)

`GUIDES_PROFILE`, `GUIDES_BACKEND`, `GUIDES_FRONTEND`, `GUIDES_MOBILE`, `GUIDES_CODEGEN`, `GUIDES_OVERLAYS` (ścieżki rozdzielone `:` / `;` wg OS — preferuj wielokrotne `--overlays` w mcp.json).

## Sekcja 4 — struktura plików w kicie (decyzja autora)

```text
modules/stacks/
  django/
    layout.md                 # tree + zasady HTML
    code-standard.md          # opcjonalnie cienki / wspólny później
  django-drf/
    project-structure.md      # istniejący — uogólnić (bez nazw produktów)
    backend-code-standard.md
  fastapi/
    layout.md
  flask/
    layout.md

modules/stacks/frontend/
  expo-unified.md             # frontend/ jeden katalog (web+native)
  expo-web.md                 # tylko web Expo
  react-web.md                # tylko React DOM
  react-expo-split.md         # web React + mobile Expo + packages
  react-native-split.md       # web React + mobile RN + packages
```

`manifest.yaml`: nowe id modułów (`stack:fastapi:layout`, `stack:frontend:react-expo-split`, …). Resolver mapuje enum CLI → id.

`profiles/_base.yaml`: usunąć hardcod `stacks: django-drf / expo-router` — stack wyłącznie z CLI. `_base` zostawia patterns, typing, wspólne architecture (ci-cd, capability-provider) niezależne od konkretnego FE/BE.

`arch:monorepo-layout`: krótki indeks „wybór layoutu zależy od `--backend`/`--frontend`/`--mobile`” + linki; szczegółowe tree tylko w stack MD.

Treść tree: placeholdery `<name>`, `<feature>` — **zakaz** przykładów `products/`, `shop/`, `todo/` jako kanonu ścieżek.

Domain/capability MD (`domain:shop`, …) opisują **logikę i kontrakty**, nie narzucają konkretnego tree FE (odsyłają do wybranego stack frontend).

## Sekcja 5 — bootstrap

`scripts/bootstrap-project.sh`:

- Flag `--preset` → alias `--profile`.
- Nowe: `--backend`, `--frontend`, `--mobile`, `--overlays` (opcjonalne).
- Generowane mcp*: wpisuje wybrane flagi (nie tworzy `.ai/project.md` / `project.profile.yaml`).
- Opcja `--with-extras-stub`: tworzy pusty/szablon `.ai/extras.md` **i** dodaje go do `--overlays` (opcjonalna; default off).
- Usunąć / zdeprecjonować `--with-overlay` oparte o `project.md`.

## Sekcja 6 — testy

- Parsowanie CLI: profile default, conflict `expo`+`react-native`, wymagane `--frontend` gdy backend REST.
- Macierz FE → lista module ids.
- `get_overlay` czyta tylko `--overlays`, nie `.ai/project.md`.
- Alias `--preset` → ten sam path co `--profile`.
- Bootstrap smoke: wygenerowany fragment args zawiera backend/frontend.

## Sekcja 7 — docs / migration

- README + `profiles/README.md` + `AGENTS.md` + `use-guides`: nowa tabela flag.
- Usunąć `templates/project.profile.yaml` z zalecanego flow (albo oznaczyć deprecated / usunąć).
- `templates/project.md` → zastąpić szablonem `templates/extras.md` (opcjonalny stub).
- Komunikat breaking w README: projekty z `--preset` + `project.md` migrują na `--profile` + `--overlays`.

## Priorytet implementacji (kolejność planów)

1. **CLI + resolver + tools** (kontrakt args, bez pełnych treści FastAPI/Flask tree).
2. **MD layoutów** (4 BE + 5 FE macierzy) + manifest + odesłanie `_base`.
3. **Bootstrap + docs + testy** + usunięcie starych ścieżek overlay.

## Open questions (zamknięte w tym designie)

| Pytanie | Rozstrzygnięcie |
|---------|-----------------|
| Auto-load extras? | Nie — tylko `--overlays` |
| `get_overlay` vs rename? | Zostaje nazwa toola; źródło = `--overlays` |
| Mobile-only bez web? | Poza v1 — wymaga `--frontend` gdy backend REST |
| Django + frontend podany | Ostrzeżenie, nie hard fail |
