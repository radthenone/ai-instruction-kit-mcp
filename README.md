# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają **kategorię** (`--preset`) + opcjonalnie overlay / fork.

**Gdzie czytać / zmieniać konfigurację:**


| Co                                           | Gdzie pisać                                             |
| -------------------------------------------- | ------------------------------------------------------- |
| Argumenty MCP (`--preset`, `--language`, `--clients`, `--workspace`, …) | ten README (sekcja niżej) + szablony `templates/*/mcp*` |
| Lista kategorii i fork                       | [`profiles/README.md`](profiles/README.md)              |
| Kanon agentów / reguł (niezależny od IDE)    | [`templates/shared/`](templates/shared/README.md)       |
| Multi-client design                          | [design](docs/specs/2026-08-05-multi-client-templates-design.md) |
| Szczegóły jednego produktu                   | `.ai/project.md` w **repo aplikacji** (`codegen:` tu)  |
| Zmiana zestawu modułów vs kategoria          | `.ai/project.profile.yaml` + `--profile` (fork)         |
| Docelowy kontrakt `--profile` / stack / `--overlays` / `--codegen` | [design overlays](docs/specs/2026-08-05-mcp-profile-architecture-overlays-design.md) (**CLI stack jeszcze nie**) |
| Cursor `/compact` (alias Summarize)          | `templates/cursor/skills/compact/` → `.cursor/skills/` (nie Claude/Codex) |


## Struktura `docs/`

```text
docs/
├── adr/     — decyzje architektoniczne (format Nygarda)
├── agents/  — kontrakt issue trackera, etykiety triage, docs domenowe
├── specs/   — projekty przed implementacją
└── plans/   — plany implementacyjne
```

> `docs/specs/` i `docs/plans/` nazywały się wcześniej `docs/superpowers/{specs,plans}`. Zmiana jest celowa: Superpowers i `mattpocock/skills` to zewnętrzne biblioteki, z których kit **korzysta** — ich nazwa nie powinna strukturyzować drzewa docs tego repo.

## Konfiguracja projektu — argumenty `guides-mcp`

Wszystkie flagi serwera MCP wpisujesz w `args` klienta (Cursor: `.cursor/mcp.json`). Kolejność: najpierw `--from` / nazwa pakietu (`guides-mcp`), potem flagi poniżej.

### Warstwy (co gdzie należy)


| Warstwa                           | Mechanizm                                             | Przykład                 |
| --------------------------------- | ----------------------------------------------------- | ------------------------ |
| Fundament stacku                  | `--preset _base` (default bootstrapu)                 | Django+Expo, typing      |
| Kategoria domeny                  | `--preset shop`                                       | auth + shop + payments   |
| Powtarzalny wariant kategorii     | `--tag` / facety (**planowane**, niezaimplementowane) | `physical`, `digital`    |
| Fakty jednego repo                | `.ai/project.md` + `--workspace`                      | jubiler, porty, Taskfile |
| Inny zestaw modułów niż kategoria | `--profile` + lokalny YAML                            | queue: rabbitmq          |


Nie mieszaj: nazwa produktu ≠ preset; porty ≠ tag.

### Flagi (aktualne)

```json
{
  "mcpServers": {
    "project-guides": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git",
        "guides-mcp",
        "--preset", "_base",
        "--language", "pl",
        "--clients", "all",
        "--workspace", "${workspaceFolder}"
      ]
    }
  }
}
```


| Flaga              | Wymagana? | Rola                                                                                                                                               | Gdzie / jak zmieniać                                     |
| ------------------ | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `--from SOURCE`    | tak (uvx) | Źródło kita: `git+https://…` albo absolutna ścieżka lokalna                                                                                        | `.cursor/mcp.json` (i odpowiedniki innych klientów)      |
| `--preset NAME`    | tak       | Kategoria z `profiles/NAME.yaml` (`_base`, `shop`, …) — bez aliasów produktowych (używaj `shop`)                                                   | mcp.json; lista: MCP `list_presets` / `profiles/`        |
| `--language pl|en` | nie       | Język **prozy** (odpowiedzi, docstringi, body issue/PR, commity). **Tytuły** issue/PR/branch zawsze EN. Domyślnie: `language:` w profilu albo `pl` | mcp.json / bootstrap `--language`; env `GUIDES_LANGUAGE` |
| `--codegen orval\|none\|graphql` | nie | Generator klienta API — patrz sekcja "Codegen" niżej. Domyślnie: `orval` | mcp.json / bootstrap `--codegen`; env `GUIDES_CODEGEN`; tool `get_codegen` |
| `--clients LIST`   | nie       | Metadane IDE: `all` \| `cursor` \| `claude` \| `codex` \| `vscode` \| `kiro` \| `kilo` \| `antigravity` \| `opencode` (lista; alias `copilot`→`vscode`). **Nie** zmienia treści bundle | mcp.json / bootstrap `--clients` (default `all`); env `GUIDES_CLIENTS`; tool `get_clients` |
| `--workspace PATH` | zalecane  | Root aplikacji — stąd auto `.ai/project.md`                                                                                                        | mcp.json; Cursor/VS: `${workspaceFolder}`                |
| `--overlay PATH`   | nie       | Extra MD (można wielokrotnie)                                                                                                                      | mcp.json — rzadko; zwykle wystarczy workspace            |
| `--profile PATH`   | nie       | Lokalny fork YAML zamiast `--preset`                                                                                                               | mcp.json + plik w aplikacji                              |


Albo `--profile`, albo `--preset` — nie oba naraz. Bootstrap bez `--preset` w CLI i tak zapisuje `_base` w mcp.json. Bootstrap zapisuje też `--language` (domyślnie `pl`) oraz `--clients` (domyślnie `all`).

**Język:** MCP tool `get_language`. Priorytet: `--language` / `GUIDES_LANGUAGE` → `language:` w YAML profilu → `pl`. Moduł w bundle: `core:language-pl` albo `core:language-en`.

**Klienci AI:** MCP tool `get_clients` — tylko metadane instalacji; treść `get_bundle` jest identyczna dla każdego klienta.

**Codegen (Orval) — dziś w overlay, nie w CLI:** w `.ai/project.md` / `templates/extras.md` ustaw `codegen: orval` (default) \| `none` \| `graphql`. Reviewery FE/BE honorują to (przy `orval` wymagają regeneracji klienta po zmianie API; `graphql` → `arch:api-contract:graphql` zamiast REST). Docelowo flaga MCP `--codegen` — zob. design overlays.

**Sklep:** `"--preset", "shop"`. Szczegóły produktu tylko w `.ai/project.md`.

**Fork kategorii** (inny zestaw capabilities / `decisions`):

```yaml
# .ai/project.profile.yaml w repo aplikacji
name: moj-fork
extends: profiles/shop.yaml
decisions:
  queue: rabbitmq
```

W mcp.json zamień `--preset` na:

```text
"--profile", "${workspaceFolder}/.ai/project.profile.yaml"
```

Szczegóły: `[profiles/README.md](profiles/README.md)`.

### Tagi / facety (planowane — jeszcze nie w CLI)

Gdy wiele projektów dzieli **ten sam** powtarzalny wariant instrukcji (np. sklep fizyczny vs cyfrowy), zamiast mnożyć presety `shop-jewelry` / `shop-tokens`:

1. W `profiles/shop.yaml` zdefiniować dozwolone facety (np. `fulfillment: [physical, digital]`).
2. W mcp.json dodać np. `"--tag", "physical"` albo `"--facet", "fulfillment=physical"` (docelowa składnia przy implementacji).
3. Resolver dołoży wtedy dodatkowe MD z `modules/` — bez lokalnego forka, jeśli zestawy capabilities są te same.

**Teraz:** różnice jubiler vs tokeny → `.ai/project.md`. Tagi włączaj dopiero gdy wariant wraca w ≥2–3 projektach.

Szkic (nie działa jeszcze):

```json
"args": [
  "--from", "…",
  "guides-mcp",
  "--preset", "shop",
  "--tag", "physical",
  "--tag", "b2c",
  "--workspace", "${workspaceFolder}"
]
```



### Bootstrap

```bash
# Generyczny — default _base + --language pl (nie podawaj --preset)
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp \
  --with-overlay

# Tylko Cursor
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --clients cursor \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp

# Kategoria e-commerce, proza EN, wszyscy klienci AI
./scripts/bootstrap-project.sh /sciezka/do/moj-sklep \
  --preset shop \
  --language en \
  --clients all \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp
```

Zapisuje m.in. MCP per klient (`--preset`, `--language`, `--codegen`, `--clients`, `--workspace`), agents z `templates/shared/agents`, `BUGBOT.md` w root (wszyscy klienci) + `.cursor/BUGBOT.md` (natywny Cursor BugBot), skill Cursor `/compact`, hooki `gate-*` (Cursor), stamp `.ai/.kit-bootstrap.json` (patrz "Update kita w projekcie"). Wymaga **Python 3** (`python3` albo `python` z major==3).

**Declarative sync klientów:** domyślnie bootstrap **usuwa** kitowe pliki klientów spoza `--clients` (np. przełączenie z `--clients all` na `--clients claude` sprząta `.cursor/`, `.codex/` itd. wygenerowane przy poprzednim bootstrapie). Flaga `--keep-unselected-clients` wyłącza to sprzątanie — zostają pliki wszystkich klientów kiedykolwiek bootstrapowanych.

## MCP w innych klientach (multi-client)

Kanon treści: `templates/shared/{agents,rules}`. Adaptery IDE trzymają tylko format MCP / ścieżki natywne. Bootstrap `--clients` instaluje wybrane pakiety (default `all`).


| Klient                   | Id `--clients` | Plik MCP w aplikacji              | Klucz top-level                  | Szablon                          |
| ------------------------ | -------------- | --------------------------------- | -------------------------------- | -------------------------------- |
| Cursor                   | `cursor`       | `.cursor/mcp.json`                | `mcpServers`                     | `templates/cursor/mcp.json`      |
| Claude Code              | `claude`       | `.mcp.json` (root)                | `mcpServers`                     | `templates/claude/mcp.json`      |
| Codex CLI                | `codex`        | `.codex/config.toml`              | `[mcp_servers.x]` (TOML)         | `templates/codex/config.toml`    |
| GitHub Copilot (VS Code) | `vscode` (alias `copilot`) | `.vscode/mcp.json`     | `servers` (**nie** `mcpServers`) | `templates/vscode/mcp.json`      |
| Kiro                     | `kiro`         | `.kiro/settings/mcp.json`         | `mcpServers`                     | `templates/kiro/settings/mcp.json` |
| Kilo                     | `kilo`         | `.kilocode/mcp.json`              | `mcpServers`                     | `templates/kilo/mcp.json`        |
| Antigravity              | `antigravity`  | `.agents/mcp_config.json`         | `mcpServers`                     | `templates/antigravity/mcp_config.json` |
| opencode                 | `opencode`     | `opencode.json` (root)            | `mcp` (`type: "local"`)          | `templates/opencode/opencode.json` |


Zmienna dla `--workspace`:


| Klient          | Zmienna                                     |
| --------------- | ------------------------------------------- |
| Cursor, VS Code, Kiro, Kilo, Antigravity | `${workspaceFolder}`             |
| Claude Code     | `${CLAUDE_PROJECT_DIR:-.}`                  |
| Codex CLI, opencode | ścieżka absolutna (brak stabilnej zmiennej) |




## Instalacja per klient (krok po kroku)

Wspólne dla wszystkich: `git clone` / masz kita lokalnie → uruchom `bootstrap-project.sh` w **repo aplikacji** (nie w repo kita) z `--from` wskazującym na kita → zrestartuj IDE.

```bash
./scripts/bootstrap-project.sh /sciezka/do/mojej-appki \
  --from /m/projects/ai-instruction-kit-mcp \
  --clients cursor \
  --with-overlay
```

| Klient | `--clients` | Wymaga poza kitem | Extra config po bootstrapie |
| --- | --- | --- | --- |
| Cursor | `cursor` | Cursor IDE | Ustaw `--from` w `.cursor/mcp.json` jeśli nie `uvx`-owalny git remote. Hooki (`gate-*`) działają od razu — wymagają `bash` w PATH (Windows: Git Bash) |
| Claude Code | `claude` | `claude` CLI albo desktop app | `.mcp.json` w root — Claude Code czyta go automatycznie po `cd` do repo. `.claude/commands/*.md` = prawdziwe `/nazwa`, `.claude/agents/*.md` = subagenty (Task tool) |
| Codex CLI | `codex` | `codex` CLI | `.codex/config.toml` wymaga absolutnej ścieżki w `--workspace` (brak `${workspaceFolder}`) — bootstrap wypełnia sam z `TARGET` |
| GitHub Copilot (VS Code) | `vscode` (alias `copilot`) | VS Code + rozszerzenie GitHub Copilot Chat | `.vscode/mcp.json` (`servers`, nie `mcpServers`) + `.github/prompts/*.prompt.md` (Copilot Chat `/nazwa`) + `.github/copilot-instructions.md`. Wymaga w VS Code ustawienia `chat.promptFiles: true` (część wersji ma to domyślnie) |
| Kiro | `kiro` | Kiro IDE | `.kiro/settings/mcp.json` + `.kiro/steering/instruction-kit.md` + `.kiro/agents/` — format agentów kopiowany 1:1, **niezweryfikowany na żywym Kiro** |
| Kilo Code | `kilo` | rozszerzenie Kilo Code | `.kilocode/mcp.json` + `.kilocode/workflows/*.md` (`/nazwa`, `$ARGUMENTS` wspierane) |
| Google Antigravity | `antigravity` | Antigravity IDE | `.agents/mcp_config.json` + `.agents/workflows/*.md` (`/nazwa`; limit 12 000 znaków/plik — kit przycina) |
| opencode | `opencode` | `opencode` CLI | `opencode.json` w root (klucz `mcp`, `type: "local"`, `command` jako tablica) + `.opencode/command/*.md` (`/nazwa`, `$ARGUMENTS`) |

Wiele klientów naraz: `--clients cursor,claude` albo `--clients all`. Każdy klient dostaje **ten sam** `--preset`/`--language`/`--workspace` — różni się tylko format pliku MCP i ścieżka komend.

Po bootstrapie zawsze: **zrestartuj IDE/CLI** (MCP i komendy ładują się przy starcie), potem sprawdź że MCP wstał (np. `get_bundle` / lista narzędzi w kliencie).

## Czego kit **nie robi** / brakujące komendy

Świadome braki — nie zgłaszaj jako bug, tylko sprawdź czy potrzebujesz obejścia niżej:

| Brak | Status | Obejście |
| --- | --- | --- |
| `--tag` / facety wariantów presetu | Zaprojektowane, **nie w CLI** | Różnice trzymaj w `.ai/project.md` dopóki wariant nie powtórzy się w ≥2–3 projektach |
| `--codegen` (Orval) jako flaga MCP | Design, dziś tylko `.ai/project.md: codegen:` | Ustaw ręcznie w overlay |
| `--profile` + `--preset` jednocześnie | Niedozwolone | Wybierz jedno; fork = `--profile` |
| `/review-security` jako plik kita | Nie istnieje w `templates/shared/agents/` | To skill user/global (Cursor) — dodaj we własnym środowisku, kit go nie dostarcza |
| `/compact` poza Cursorem | Nie istnieje dla Claude/Codex/inne | To alias Cursor UI Summarize; Claude Code ma **wbudowane** `/compact` — nie koliduj, nie kopiuj |
| Natywna weryfikacja formatu VS Code/Kilo/Antigravity/opencode | Oparta o dokumentację (sierpień 2026), **nie testowana na żywych klientach** | Jeśli `/nazwa` nie działa w Twoim kliencie, zgłoś i popraw `scripts/render_agent_commands.py` |
| Auto-instalacja Superpowers/Autopilot | Niemożliwa ze skryptu (marketplace pluginów Claude/Cursor, wymaga interaktywnego `/plugin install`) | `--with-plugins` wypisze dokładne komendy/kroki, patrz niżej |

## Pluginy zewnętrzne — schemat użycia (4 warstwy)

Kit **nie** bundluje tych pluginów w `guides-mcp` (różna dystrybucja: MCP vs Claude/Cursor plugin marketplace vs npx skill). Pełna tabela warstw i priorytet źródeł: `AGENTS.md`.

```text
1. Fundament   — ten kit (MCP + /git-* + /review-*)     → instaluje bootstrap
2. Proces      — mattpocock/skills (/grill-me, /tdd)     → npx skills@latest add mattpocock/skills
3. Meta/izolacja — Superpowers (worktree, finishing…)     → Claude Code: /plugin marketplace add obra/superpowers-marketplace
                                                              /plugin install superpowers@superpowers-marketplace
4. PR → green  — Autopilot (Cursor)                       → Cursor: Settings → Extensions/Skills → Autopilot
```

Nie mieszaj warstw: kit = prawda o stacku i nazwach branchy, Matt = proces feature, Superpowers = sesja/worktree/finisz, Autopilot = dociąganie PR.

**Auto-instalacja przy bootstrapie:** `--with-plugins` (best-effort, opt-in — nic nie instaluje się bez tej flagi):

```bash
./scripts/bootstrap-project.sh ../moj-projekt \
  --clients claude \
  --from /m/projects/ai-instruction-kit-mcp \
  --with-plugins
```

Co robi: odpala `npx skills@latest add mattpocock/skills` w `TARGET` (wymaga `npx`/Node.js w PATH; best-effort — błąd nie przerywa bootstrapu), i wypisuje gotowe komendy do Superpowers/Autopilot (te dwa wymagają interaktywnego kroku w kliencie, nie da się ich odpalić z bash). TDD: jeden path na feature — domyślnie Matt `/tdd`, nie mieszaj z Superpowers TDD.

## Katalog modułów

```text
modules/
  core/              repo-first, workflow, typing, code-review, language-*, tooling-rtk
  architecture/      platforms, CI/CD, API (REST/GraphQL), security, testing, i18n,
                     taskfile, docker-structure, …
  stacks/
    django-drf/      (+ django/, fastapi/, flask/ layouts)
    expo-router/
    frontend/        warianty Expo/React (macierz web/mobile — design)
  capabilities/      auth (+ allauth/jwt/custom warianty), files, payments, …
  domains/           shop
  patterns/          capability-provider, providers-and-settings, gateway, webhooks, …
  infra/             database, cache, queue, storage, tasks, search
profiles/
  _base.yaml         fundament stacku (default)
  shop.yaml          kategoria e-commerce
  *.yaml             kolejne kategorie (blog, …) — nie nazwy produktów
templates/
  shared/            kanon agents + rules (źródło prawdy)
  cursor|claude|…    adaptery MCP / format IDE
```



## Sloty infrastruktury (`decisions`)

```yaml
decisions:
  database: postgres      # → infra:database:postgres
  cache: redis            # → infra:cache:redis
  queue: redis            # → infra:queue:redis  (lub rabbitmq)
  storage: s3             # → infra:storage:s3
  tasks: celery           # → infra:tasks:celery
  search: postgres        # → infra:search:postgres (lub meilisearch)
```

Moduły infra trafiają automatycznie do bundle `infra` i `devops`.

**Dodanie nowej technologii nie wymaga Pythona** (ADR-0001). Trzy kroki:

1. Napisz `modules/infra/queue/kafka.md`.
2. Zarejestruj go w `manifest.yaml` → `modules:`.
3. Dopisz wartość w `manifest.yaml` → `mappings.slots.queue.kafka`.

Nierozpoznana Decyzja (literówka `postgress`, technologia bez modułu) **nie wywraca
serwera** — ląduje w sekcji „Nierozpoznane decyzje" w `get_index` (ADR-0004).

## Wariant auth (`decisions.auth`)

```yaml
decisions:
  auth: custom      # default — brak enforced pakietu, opisz w .ai/project.md
  # auth: allauth   # → capability:auth:allauth (django-allauth headless)
  # auth: jwt       # → capability:auth:jwt (djangorestframework-simplejwt)
```

Inny mechanizm niż infra: nie tworzy osobnego bundle'a — dokleja się zaraz po
`capability:auth` wszędzie tam, gdzie ten moduł już jest wypisany w bundle
(`capabilities: [auth]` albo ręcznie w `bundles.backend`/`bundles.frontend`).
W manifeście to `mappings.variants.auth` (Wariant = wstaw po module bazowym),
w odróżnieniu od `mappings.substitutions.codegen` (Substytucja = podmień moduł bazowy).

## Słownik i decyzje

| Plik                       | Rola                                                                      |
| -------------------------- | ------------------------------------------------------------------------- |
| [`CONTEXT.md`](CONTEXT.md) | Ubiquitous language kita — Bundle, Preset, Slot, Wariant, Alias, Overlay… |
| [`docs/adr/`](docs/adr/)   | Decyzje architektoniczne z uzasadnieniem (dlaczego tak, a nie inaczej)    |

Nazwy z `CONTEXT.md` obowiązują w kodzie, docstringach i review. Zanim zaproponujesz
zmianę architektury, sprawdź `docs/adr/` — część rzeczy już rozstrzygnięto.

## Bundle'e MCP


| Bundle         | Zastosowanie                                |
| -------------- | ------------------------------------------- |
| `backend`      | Django, DRF, capabilities BE                |
| `frontend`     | Expo, UI/UX                                 |
| `shop`         | products, orders, cart                      |
| `payments`     | Stripe, webhooks                            |
| `architecture` | monorepo, kontrakt API, capability-provider |
| `infra`        | postgres, redis, queue, s3, celery          |
| `devops`       | CI/CD + infra                               |
| `full`         | wszystko + infra                            |




## Bootstrap w projekcie docelowym

W **repo aplikacji** uruchom `scripts/bootstrap-project.sh` albo skopiuj z `templates/`:


| Plik                                | Rola                                                                    | Wymagany?            |
| ----------------------------------- | ----------------------------------------------------------------------- | -------------------- |
| `.cursor/mcp.json`                  | uvx → `--preset` + `--language` + `--clients` + `--workspace` | tak (Cursor)        |
| `.mcp.json` / `.codex/` / `.vscode/` / … | MCP per klient z `--clients`                            | wg wybranego klienta |
| `.ai/project.md`                    | Overlay — Taskfile, Docker, porty, **`codegen:`**           | zalecany             |

| `.ai/project.profile.yaml`          | Lokalne nadpisania presetu                                              | **nie** (tylko fork) |
| `.cursor/rules/use-guides.mdc`      | Bootstrap MCP                                                           | tak                  |
| `.cursor/rules/code-review.mdc`     | Review przed pushem                                                     | tak                  |
| `.cursor/rules/git-branch-pr.mdc`   | `/git-start`+`/git-check`+`/git-commit`+`/git-end`, issue#, chronione main/master/dev | tak                  |
| `.cursor/BUGBOT.md`                 | Reguły Bugbota                                                          | tak                  |
| `.cursor/hooks.json` + `hooks/invoke-hook.js` + `hooks/*.sh` | Review + blokady destrukcyjne (node → bash wg OS) | tak                  |
| `AGENTS.md`                         | Cienki — odsyła do MCP                                                  | tak                  |
| `.cursor/agents/*.md`               | Subagenty `/review-*`, `/subagent-*`, `/git-*`                          | zalecany             |
| `.cursor/skills/compact/`           | **Tylko Cursor:** `/compact` = alias UI Summarize (nie Claude/Codex)    | zalecany (Cursor)    |


W projekcie docelowym **nie** duplikuj `modules/` — wystarczy preset + opcjonalny overlay.

## Update kita w projekcie

Bootstrap to **jednorazowy stempel**, nie sync. Trzy różne zachowania:

| Co | Przy ponownym `bootstrap-project.sh` |
| --- | --- |
| `.claude/agents/`, `.cursor/agents/`, `.claude/commands/`, `mcp.json`/`config.toml` | **Zawsze nadpisane** świeżą kopią z kita — traktuj jak wygenerowany kod, nie edytuj ręcznie |
| `AGENTS.md`, `.ai/project.md` | Kopiowane **tylko jeśli brak** — bootstrap nigdy więcej ich nie tyka, update ręczny |
| `modules/*.md` (treść instrukcji) | **W ogóle nie kopiowane** — MCP czyta je live z `--from` przy każdym `get_bundle`/`get_overlay`, więc zawsze aktualne bez re-bootstrapu |

Skąd wiedzieć **kiedy** re-bootstrapować (bez ciągłego czytania plików kita — tanie, jedno porównanie commitów):

```text
MCP tool: check_kit_status
```

Bootstrap zapisuje `.ai/.kit-bootstrap.json` (commit kita w momencie bootstrapu). `check_kit_status`
porównuje go z aktualnym `HEAD` kita (`git rev-parse` + `git diff --name-only` tylko na ścieżkach
które bootstrap faktycznie kopiuje) i zwraca: aktualny / zmienił się (+ lista plików) / brak stampu
(stary bootstrap sprzed tej funkcji) / brak lokalnej historii git (gdy `--from` to zdalny URL, nie
lokalny klon). Zero kosztu tokenów na nawigację plików — jedno wywołanie tool, agent woła je kiedy
chce sprawdzić stan (np. na początku sesji), nie w pętli.

Gdy pokaże zmiany: `bootstrap-project.sh` ponownie z tymi samymi flagami co poprzednio.

## Slash commands — konwencja nazw


| Prefiks       | Rola                                                 | Przykłady                                                                                                                                          |
| ------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/compact`    | **Cursor only** — alias UI Summarize w tym projekcie | `/compact`                                                                                                                                         |
| `/git-*`      | Start / sync issue / commit / PR                   | `/git-start`, `/git-check`, `/git-commit`, `/git-end`                                                                                               |
| `/review-*`   | Review tylko do odczytu, raport                      | `/review-backend`, `/review-frontend`, `/review-architecture`, `/review-ui`, `/review-edge`, `/review-tests`, `/review-bugbot`, `/review-security` |
| `/subagent-*` | Praca w dwóch oknach (wymiana raportów)              | `/subagent-backend`, `/subagent-frontend`                                                                                                          |




### `/compact` (wyłącznie Cursor)

Skill: `templates/cursor/skills/compact/SKILL.md` → **tylko** `.cursor/skills/compact/`.

Bootstrap **nie** kopiuje tego do Claude / Codex. Nie nadpisuje ani nie „tłumaczy” ich wbudowanego `/compact`.

- **Po co:** w Cursorze jedna komenda `/compact` zamiast szukania UI **Summarize**.
- **Nie** jest wspólną konwencją kita cross-tool.
- **Nie** mylić z `/handoff` (plik + nowy chat).

```text
/compact
```



### `/git-start`, `/git-check`, `/git-commit`, `/git-end` + Superpowers + Autopilot

Wymaga `gh` + `git`. Konwencja: `feat/42-add-cart-coupon`. Pełne zasady: `.cursor/rules/git-branch-pr.mdc`.

#### Podział ról (czytelnie)


| Krok                     | Narzędzie                                                                  | Uwagi                                        |
| ------------------------ | -------------------------------------------------------------------------- | -------------------------------------------- |
| Scope / TDD              | Matt `/grill-me`, `/tdd`                                                   | `/grill-me` tylko przy niejasnym scope; nie mieszać z Superpowers TDD |
| Issue + branch           | `/git-start` (kit)                                                         | Numeracja issue, Conventional name           |
| Sync issue ↔ diff        | `/git-check` (kit)                                                         | Gdy tytuł/body rozjechały się z plikami      |
| Commit(y)                | `/git-commit` (kit)                                                        | Conventional; `--one` / `--split` / `--dry-run` |
| Izolacja (opc.)          | Superpowers `using-git-worktrees`                                          | Na branchu z `/git-start`, nie zamiast niego |
| Review przed pushem      | `/review-bugbot` + **minimalny** stack (`/review-backend` i/lub `/review-frontend`) | Nie wszystkie `/review-*` naraz; format: Severity\|Location\|Finding\|Fix |
| Push + PR                | `/git-end` **lub** Superpowers `finishing-a-development-branch` → opcja PR | Jedno z dwóch. `/git-end` = push + PR (`Closes #N`); **bez** merge; brudne tree → najpierw `/git-commit` |
| CI / komentarze aż green | **Autopilot**                                                              | Po istniejącym PR; bez auto-merge            |
| Merge                    | Ty / `gh pr merge`                                                         | Gdy green → GitHub zamyka issue (`Closes #N`) |


```text
Krótko:   /git-start → kod → [/git-check] → /git-commit → /review-bugbot → /git-end → [Autopilot]
Długo:    [/grill-me] → /git-start → worktree → kod → [/git-check] → /git-commit → finishing| /git-end → Autopilot → merge
```


| Komenda kit  | Co robi                                                                                 |
| ------------ | --------------------------------------------------------------------------------------- |
| `/git-start` | `#N` / opis / **puste = auto-diff** / `--help` (ręcznie: `gh issue create` / `develop`) |
| `/git-check` | Dopasuj tytuł (EN) i body (język MCP) issue do realnego diffa; `--dry-run`              |
| `/git-commit` | Conventional Commit(s) z diffa; `--one` (jeden) / `--split` / `--dry-run`; odpala pre-commit |
| `/git-end`   | Push + PR z `Closes #N` w body; `--help`; alias `/git-pr`. **Nie** merguje i **nie** zamyka issue od razu — issue zamyka się **po merge** PR |
| `/compact`   | **Cursor only** — skrót czatu (alias UI Summarize); nie Claude/Codex                     |


```text
/git-start --help
/git-start feat add cart coupon
/git-start fix #108 login returns 500
/git-start                    # auto z lokalnego diffa
# … praca zmieniła scope …
/git-check
/git-commit                   # lub --one / --split / --dry-run
# … review …
/git-end --help
/git-end
```

Ręczny odpowiednik:

```bash
gh issue create --title "Add cart coupon" --body "…"
gh issue develop 42 --name feat/42-add-cart-coupon --base dev --checkout
# … praca …
git push -u origin HEAD
gh pr create --base dev --title "feat: add cart coupon" --body "Closes #42"
```

UI: GitHub Issue → Development → **Create a branch** (potem nazwij spójnie `typ/N-slug`).


| Slash                                | Plik szablonu                                    |
| ------------------------------------ | ------------------------------------------------ |
| `/git-start`                         | `templates/shared/agents/git-start.md`           |
| `/git-check`                         | `templates/shared/agents/git-check.md`           |
| `/git-commit`                        | `templates/shared/agents/git-commit.md`          |
| `/git-end`                           | `templates/shared/agents/git-end.md`             |
| `/compact` (Cursor)                  | `templates/cursor/skills/compact/SKILL.md`       |
| `/review-architecture`               | `templates/shared/agents/review-architecture.md` |
| `/review-backend`                    | `templates/shared/agents/review-backend.md`      |
| `/review-frontend`                   | `templates/shared/agents/review-frontend.md`     |
| `/review-ui`                         | `templates/shared/agents/review-ui.md`           |
| `/review-edge`                       | `templates/shared/agents/review-edge.md`         |
| `/review-tests`                      | `templates/shared/agents/review-tests.md`        |
| `/review-bugbot`                     | `templates/shared/agents/review-bugbot.md` (manualny odpowiednik natywnego Cursor BugBot — stosuje reguły z `BUGBOT.md` ręcznie, dla klientów bez tej usługi) |
| `/cleanup`                           | `templates/shared/agents/cleanup.md` (znajdź i usuń zbędne scratch/testowe pliki zostawione po weryfikacji — pyta o potwierdzenie) |
| `/subagent-backend`                  | `templates/shared/agents/subagent-backend.md`    |
| `/subagent-frontend`                 | `templates/shared/agents/subagent-frontend.md`   |
| `/teacher-backend`                   | `templates/shared/agents/teacher-backend.md`     |
| `/teacher-frontend`                  | `templates/shared/agents/teacher-frontend.md`    |
| `/teacher-architecture`              | `templates/shared/agents/teacher-architecture.md` |
| `/review-security`                   | skille Cursor (user/global), nie ten kit         |

### `/teacher-*` — tryb nauki (przed kodem, nie po)

`/review-*` sprawdza **gotowy diff** i zwraca tabelę findingów. `/teacher-*` działa **zanim** napiszesz kod: bierze Twoją koncepcję (albo bieżący diff, gdy nie podasz argumentu), tłumaczy o co w problemie naprawdę chodzi, pokazuje max 3 opcje z kosztami, wskazuje **jedną** rekomendację i zostawia Ci zadanie do zrobienia samodzielnie.

| Komenda | Zakres |
| --- | --- |
| `/teacher-backend` | Django/DRF (opc. FastAPI, Flask+Pydantic): warstwy, modele, migracje, transakcje, Celery, ACL, pytest, uv/ruff |
| `/teacher-frontend` | React, React Native/Expo Router (opc. Angular): stan serwera vs klienta, granice komponentów, re-rendery, web/native, typy TS, RTL/Playwright |
| `/teacher-architecture` | granice FE/BE, kontrakt API, kiedy **nie** dzielić, infra (Postgres/Redis/Celery/S3), Docker+Taskfile, odwracalność decyzji, ADR |

Kontrakt tych agentów: `readonly` — **nie edytują plików**, nie dają gotowca do wklejenia (szkic ≤ 20 linii), nazywają wzorce po imieniu i mówią wprost, gdy koncepcja jest zła. Czytają `get_bundle` + `get_overlay`, więc uczą na Twoim stacku i Twoim kodzie, nie na `Foo/Bar`.

```
/teacher-backend czy walidację ceny dać do serializera czy do serwisu
/teacher-frontend                 # bez argumentu → uczy o tym, co masz w git diff
/teacher-architecture czy dodać Redisa pod cache koszyka
```


Bootstrap (`--clients`) kopiuje/renderuje shared agents do natywnych ścieżek każdego klienta. Format i mechanizm różnią się per klient:

- **Cursor**: `.cursor/agents/` — natywne slash commands, działa 1:1.
- **Claude Code**: `.claude/agents/` (subagenty, wywołanie przez Task/Agent tool) **oraz** `.claude/commands/` (prawdziwe slash commands `/git-start` itd. — `$ARGUMENTS` wstrzyknięty automatycznie przy kopiowaniu).
- **Codex**: `templates/codex/agents/*.toml` (ręczny, curated) → `.codex/agents/`; agenci bez ręcznego TOML są auto-renderowani z `templates/shared/agents/*.md` (`scripts/render_agent_commands.py codex`) — pełna lista `/git-*`, `/review-*`, `/subagent-*` trafia do `.codex/agents/`, curated ma pierwszeństwo nad auto.
- **Kiro**: `.kiro/agents/` — kopiowane 1:1, format niezweryfikowany na żywym Kiro.
- **VS Code/Copilot**: `scripts/render_agent_commands.py vscode` → `.github/prompts/*.prompt.md` (wywołanie `/nazwa` w Copilot Chat).
- **Kilo**: `scripts/render_agent_commands.py kilo` → `.kilocode/workflows/*.md` (wywołanie `/nazwa`, `$ARGUMENTS` wspierane).
- **Antigravity**: `scripts/render_agent_commands.py antigravity` → `.agents/workflows/*.md` (wywołanie `/nazwa`; limit 12 000 znaków/plik, kit przycina jeśli trzeba).
- **opencode**: `scripts/render_agent_commands.py opencode` → `.opencode/command/*.md` (wywołanie `/nazwa`, `$ARGUMENTS` wspierane).

Formaty VS Code/Kilo/Antigravity/opencode oparte o publiczną dokumentację tych klientów (sierpień 2026) — nie testowane na żywych instalacjach; jeśli coś nie zadziała, zgłoś różnicę i popraw `scripts/render_agent_commands.py`.

Po skopiowaniu/wyrenderowaniu **zrestartuj** okno IDE — agenty/komendy ładują się przy starcie.

### Wywołanie

```text
/git-start feat #42 cart coupon   # lub bez # — utworzy issue
/git-check                        # gdy diff rozjechał się z opisem issue
/git-commit                       # Conventional Commit(s)
/review-backend przejrzyj zmiany w backend/apps/products/
/git-end
```

```text
/subagent-backend przejrzyj zmiany…   # potem wklej raport do /subagent-frontend w drugim oknie
```



## Cursor Hooks — bezpieczeństwo

| Hook | Zachowanie |
|------|------------|
| `gate-destructive.sh` | **deny** force na `main`/`master`/`dev`: `--force` / `-f` / `--force-with-lease` **oraz** plus-refspec (`git push origin +main`, `+main:main`, …); także `git reset --hard`, agresywny `git clean -f`. **ask** force/`+ref` na feature, zwykły push na chronione, `commit --no-verify`, `rm -rf` |
| `gate-push.sh` | **ask** przed zwykłym `git push` (przypomnienie `/review-bugbot`); bypass `SKIP_PUSH_REVIEW=1` |

`gate-destructive` ma `failClosed: true` — padnięty skrypt (brak JSON) blokuje akcję.  
`invoke-hook.js` po wypisaniu JSON z `permission` **zawsze kończy exit 0** (niezerowy exit ukrywa payload przy failClosed).

**Hooks — wykrywanie OS (Bash wszędzie, bez hardcodu Windows w trackowanym JSON):**

| Plik | Rola |
|------|------|
| `templates/cursor/hooks.json` | `node .cursor/hooks/invoke-hook.js <script>` (ten sam na wszystkich OS) |
| `invoke-hook.js` | Windows → `Git/bin/bash.exe --noprofile --norc`; Linux/macOS → `bash --noprofile --norc`; `windowsHide` |

Sama ścieżka `.sh` w `hooks.json` → Cursor na Windows robi `bash --login -i` i zostawia konsolę.  
Terminal IDE (Git Bash) bez zmian — to tylko spawn hooków.

Szablon: `templates/cursor/hooks/gate-destructive.sh` (bootstrap → `.cursor/hooks/`).  
Regresja plus-refspec / `-f`: `bash tests/test_gate_destructive.sh` — odpalane też przez CI
(`tests/test_shell_suites.py` wciąga suity powłoki do `unittest discover`).

## Code review (Bugbot + GitHub)

Moduł MCP: `core:code-review` (bundle `devops` lub `architecture`).

**Minimalny zestaw przed pushem** (nie odpalaj całego wachlarza):

| Zmiana | Minimum |
|--------|---------|
| Drobna | `/review-bugbot` |
| Backend / Frontend | Bugbot + `/review-backend` lub `/review-frontend` |
| API + UI | Bugbot + BE+FE **lub** para `/subagent-*` |
| Auth / płatności | `/review-security` |
| Dowód „działa” | `/review-tests` (komendy, nie styl) |

Bugbot = blocking/security. Stack `/review-*` = konwencje z MCP (`Severity | Location | Finding | Fix`).  
Przy `codegen: orval` w overlay — po zmianie API regeneruj klienta.


| Warstwa            | Plik / akcja                                                                |
| ------------------ | --------------------------------------------------------------------------- |
| Lokalnie           | `/review-bugbot`, `/review-security`, `/review-backend`…                    |
| Przed push         | `.cursor/hooks/gate-push.sh` + `gate-destructive.sh`                        |
| Na PR              | Bugbot (GitHub integration)                                                 |
| Reguły             | `.cursor/BUGBOT.md`                                                         |
| CI (ten kit)       | `.github/workflows/ci.yml` — unittest (w tym suity powłoki) + smoke FastMCP |
| Hook regresja      | `tests/test_gate_destructive.sh` (force / `+ref` / `-f`)                    |
| Suity powłoki w CI | `tests/test_shell_suites.py` — jedyny adapter `*.sh` → `unittest discover`  |



## Zależności Python (pin majora)

```toml
mcp>=1.0.0,<2      # FastMCP (1.x); mcp 2.0 usuwa mcp.server.fastmcp
pyyaml>=6.0,<7
```

`uvx` resolvuje zależności od zera (nie bierze lokalnego `uv.lock`) — upper bound chroni konsumentów przed breaking major.

## Skills / pluginy zewnętrzne (poza tym kitem)

Trzy warstwy — nie bundluj Matt/Superpowers w `guides-mcp`:


| Warstwa   | Przykłady                                                 | Gdzie                                     | Rola                         |
| --------- | --------------------------------------------------------- | ----------------------------------------- | ---------------------------- |
| Fundament | Context7, `project-guides`, `/review-*`, `/git-*`, Cursor `/compact` | MCP + agents/skills z bootstrap | stack, git, skrót czatu (Cursor) |
| Proces    | [mattpocock/skills](https://github.com/mattpocock/skills) | `npx skills@latest add mattpocock/skills` | `/grill-me`, `/tdd`          |
| Meta      | superpowers, caveman, Autopilot                                      | user / plugin Cursor                      | worktree, finishing, CI loop |


Priorytet w `AGENTS.md`: użytkownik → overlay+MCP → review kita → Matt → Superpowers.  
TDD: jeden path na feature (preferuj Matt). Setup Matt: po instalacji uruchom `/setup-matt-pocock-skills`.

Context7 (docs Django/Expo): globalnie `npx ctx7 setup --cursor`.

## Subagenty — szczegóły

Każdy plik agentów jest **cienkim wrapperem**: przy starcie woła `get_bundle` / `get_overlay` z MCP `project-guides`. Wiedza merytoryczna żyje w `modules/`.

Praca w dwóch oknach: `/subagent-backend` ↔ `/subagent-frontend` — sekcja „Raport do przekazania” na końcu odpowiedzi.