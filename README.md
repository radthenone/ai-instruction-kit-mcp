# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają **kategorię** (`--preset`) + opcjonalnie overlay / fork.

**Gdzie czytać / zmieniać konfigurację:**


| Co                                           | Gdzie pisać                                             |
| -------------------------------------------- | ------------------------------------------------------- |
| Argumenty MCP (`--preset`, `--language`, `--clients`, `--workspace`, …) | ten README (sekcja niżej) + szablony `templates/*/mcp*` |
| Lista kategorii i fork                       | [`profiles/README.md`](profiles/README.md)              |
| Kanon agentów / reguł (niezależny od IDE)    | [`templates/shared/`](templates/shared/README.md)       |
| Multi-client design                          | [design](docs/superpowers/specs/2026-08-05-multi-client-templates-design.md) |
| Szczegóły jednego produktu                   | `.ai/project.md` w **repo aplikacji** (`codegen:` tu)  |
| Zmiana zestawu modułów vs kategoria          | `.ai/project.profile.yaml` + `--profile` (fork)         |
| Docelowy kontrakt `--profile` / stack / `--overlays` / `--codegen` | [design overlays](docs/superpowers/specs/2026-08-05-mcp-profile-architecture-overlays-design.md) (**CLI stack jeszcze nie**) |
| Cursor `/compact` (alias Summarize)          | `templates/cursor/skills/compact/` → `.cursor/skills/` (nie Claude/Codex) |


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
| `--clients LIST`   | nie       | Metadane IDE: `all` \| `cursor` \| `claude` \| `codex` \| `vscode` \| `kiro` \| `kilo` \| `antigravity` (lista; alias `copilot`→`vscode`). **Nie** zmienia treści bundle | mcp.json / bootstrap `--clients` (default `all`); env `GUIDES_CLIENTS`; tool `get_clients` |
| `--workspace PATH` | zalecane  | Root aplikacji — stąd auto `.ai/project.md`                                                                                                        | mcp.json; Cursor/VS: `${workspaceFolder}`                |
| `--overlay PATH`   | nie       | Extra MD (można wielokrotnie)                                                                                                                      | mcp.json — rzadko; zwykle wystarczy workspace            |
| `--profile PATH`   | nie       | Lokalny fork YAML zamiast `--preset`                                                                                                               | mcp.json + plik w aplikacji                              |


Albo `--profile`, albo `--preset` — nie oba naraz. Bootstrap bez `--preset` w CLI i tak zapisuje `_base` w mcp.json. Bootstrap zapisuje też `--language` (domyślnie `pl`) oraz `--clients` (domyślnie `all`).

**Język:** MCP tool `get_language`. Priorytet: `--language` / `GUIDES_LANGUAGE` → `language:` w YAML profilu → `pl`. Moduł w bundle: `core:language-pl` albo `core:language-en`.

**Klienci AI:** MCP tool `get_clients` — tylko metadane instalacji; treść `get_bundle` jest identyczna dla każdego klienta.

**Codegen (Orval) — dziś w overlay, nie w CLI:** w `.ai/project.md` / `templates/extras.md` ustaw `codegen: orval` \| `manual` \| `none`. Reviewery FE/BE honorują to (przy `orval` wymagają regeneracji klienta po zmianie API). Docelowo flaga MCP `--codegen` — zob. design overlays.

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

Zapisuje m.in. MCP per klient (`--preset`, `--language`, `--clients`, `--workspace`), agents z `templates/shared/agents`, skill Cursor `/compact`, hooki `gate-*` (Cursor). Wymaga **Python 3** (`python3` albo `python` z major==3).

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


Zmienna dla `--workspace`:


| Klient          | Zmienna                                     |
| --------------- | ------------------------------------------- |
| Cursor, VS Code, Kiro, Kilo, Antigravity | `${workspaceFolder}`             |
| Claude Code     | `${CLAUDE_PROJECT_DIR:-.}`                  |
| Codex CLI       | ścieżka absolutna (brak stabilnej zmiennej) |




## Katalog modułów

```text
modules/
  core/              repo-first, workflow, typing, code-review, language-*
  architecture/      platforms, CI/CD, API, security, testing, i18n, …
  stacks/
    django-drf/      (+ django/, fastapi/, flask/ layouts)
    expo-router/
    frontend/        warianty Expo/React (macierz web/mobile — design)
  capabilities/      auth, files, payments, …
  domains/           shop
  patterns/          capability-provider, providers-and-settings, gateway…
  infra/             database, cache, queue, storage, tasks
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
```

Moduły infra trafiają automatycznie do bundle `infra` i `devops`.

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
| `/subagent-backend`                  | `templates/shared/agents/subagent-backend.md`    |
| `/subagent-frontend`                 | `templates/shared/agents/subagent-frontend.md`   |
| `/review-bugbot`, `/review-security` | skille Cursor (user/global), nie ten kit         |


Bootstrap (`--clients`) kopiuje shared agents do natywnych ścieżek (`.cursor/agents/`, `.claude/agents/`, …). Codex TOML: `templates/codex/agents/*.toml` → `.codex/agents/`.

Po skopiowaniu **zrestartuj** okno Cursor — agenty ładują się przy starcie.

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
Regresja plus-refspec / `-f`: `bash tests/test_gate_destructive.sh`.

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


| Warstwa      | Plik / akcja                                             |
| ------------ | -------------------------------------------------------- |
| Lokalnie     | `/review-bugbot`, `/review-security`, `/review-backend`… |
| Przed push   | `.cursor/hooks/gate-push.sh` + `gate-destructive.sh`     |
| Na PR        | Bugbot (GitHub integration)                              |
| Reguły       | `.cursor/BUGBOT.md`                                      |
| CI (ten kit) | `.github/workflows/ci.yml` — unittest + smoke FastMCP    |
| Hook regresja | `tests/test_gate_destructive.sh` (force / `+ref` / `-f`) |



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