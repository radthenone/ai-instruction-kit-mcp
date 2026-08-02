# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają **kategorię** (`--preset`) + opcjonalnie overlay / fork.

**Gdzie czytać / zmieniać konfigurację:**

| Co | Gdzie pisać |
|----|-------------|
| Argumenty MCP (`--preset`, `--workspace`, …) | ten README (sekcja niżej) + szablony `templates/*/mcp*` |
| Lista kategorii i fork | [`profiles/README.md`](profiles/README.md) |
| Szczegóły jednego produktu | `.ai/project.md` w **repo aplikacji** |
| Zmiana zestawu modułów vs kategoria | `.ai/project.profile.yaml` + `--profile` (fork) |

## Konfiguracja projektu — argumenty `guides-mcp`

Wszystkie flagi serwera MCP wpisujesz w `args` klienta (Cursor: `.cursor/mcp.json`). Kolejność: najpierw `--from` / nazwa pakietu (`guides-mcp`), potem flagi poniżej.

### Warstwy (co gdzie należy)

| Warstwa | Mechanizm | Przykład |
|---------|-----------|----------|
| Fundament stacku | `--preset _base` (default bootstrapu) | Django+Expo, typing |
| Kategoria domeny | `--preset shop` | auth + shop + payments |
| Powtarzalny wariant kategorii | `--tag` / facety (**planowane**, niezaimplementowane) | `physical`, `digital` |
| Fakty jednego repo | `.ai/project.md` + `--workspace` | jubiler, porty, Taskfile |
| Inny zestaw modułów niż kategoria | `--profile` + lokalny YAML | queue: rabbitmq |

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
        "--workspace", "${workspaceFolder}"
      ]
    }
  }
}
```

| Flaga | Wymagana? | Rola | Gdzie / jak zmieniać |
|-------|-----------|------|----------------------|
| `--from SOURCE` | tak (uvx) | Źródło kita: `git+https://…` albo absolutna ścieżka lokalna | `.cursor/mcp.json` (i odpowiedniki innych klientów) |
| `--preset NAME` | tak\* | Kategoria z `profiles/NAME.yaml` (`_base`, `shop`, …) | mcp.json; lista: MCP `list_presets` / `profiles/` |
| `--workspace PATH` | zalecane | Root aplikacji — stąd auto `.ai/project.md` | mcp.json; Cursor/VS: `${workspaceFolder}` |
| `--overlay PATH` | nie | Extra MD (można wielokrotnie) | mcp.json — rzadko; zwykle wystarczy workspace |
| `--profile PATH` | nie | Lokalny fork YAML zamiast `--preset` | mcp.json + plik w aplikacji |

\*Albo `--profile`, albo `--preset` — nie oba naraz. Bootstrap bez `--preset` w CLI i tak zapisuje `_base` w mcp.json.

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

Szczegóły: [`profiles/README.md`](profiles/README.md).

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
# Generyczny — default _base (nie podawaj --preset)
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp \
  --with-overlay

# Kategoria e-commerce
./scripts/bootstrap-project.sh /sciezka/do/olivin-app \
  --preset shop \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp
```

Dev lokalny: `"--from", "/absolutna/sciezka/do/ai-instruction-kit-mcp"`.

## MCP w innych klientach (Claude Code, Codex CLI, GitHub Copilot)

Każdy klient ma **własny plik i własny format** rejestracji MCP — nie da się skopiować `.cursor/mcp.json` 1:1.

| Klient | Plik | Klucz top-level | Szablon w tym repo |
|--------|------|------------------|---------------------|
| Cursor | `.cursor/mcp.json` | `mcpServers` | `templates/cursor/mcp.json` |
| Claude Code | `.mcp.json` (root repo aplikacji) | `mcpServers` | `templates/claude/mcp.json` |
| Codex CLI | `.codex/config.toml` | `[mcp_servers.x]` (TOML) | `templates/codex/config.toml` |
| GitHub Copilot (VS Code) | `.vscode/mcp.json` | `servers` (**nie** `mcpServers`) | `templates/vscode/mcp.json` |

Zmienna dla `--workspace`:

| Klient | Zmienna |
|--------|---------|
| Cursor, VS Code | `${workspaceFolder}` |
| Claude Code | `${CLAUDE_PROJECT_DIR:-.}` |
| Codex CLI | ścieżka absolutna (brak stabilnej zmiennej) |

## Katalog modułów

```text
modules/
  core/              repo-first, workflow, typing (TS + Python)
  architecture/      platforms (BE/web/mobile), CI/CD, API contract, UI/UX
  stacks/
    django-drf/
    expo-router/     structure, mobile-native, web-target
  capabilities/      auth, files, payments, payments-expo-stripe
  domains/           shop
  patterns/          capability-provider, providers-and-settings, gateway…
  infra/             database, cache, queue, storage, tasks
profiles/
  _base.yaml         fundament stacku (default)
  shop.yaml          kategoria e-commerce
  *.yaml             kolejne kategorie (blog, …) — nie nazwy produktów
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

| Bundle | Zastosowanie |
|--------|--------------|
| `backend` | Django, DRF, capabilities BE |
| `frontend` | Expo, UI/UX |
| `shop` | products, orders, cart |
| `payments` | Stripe, webhooks |
| `architecture` | monorepo, kontrakt API, capability-provider |
| `infra` | postgres, redis, queue, s3, celery |
| `devops` | CI/CD + infra |
| `full` | wszystko + infra |

## Bootstrap w projekcie docelowym

W **repo aplikacji** uruchom `scripts/bootstrap-project.sh` albo skopiuj z `templates/`:

| Plik | Rola | Wymagany? |
|------|------|-----------|
| `.cursor/mcp.json` | uvx → `--preset` + `--workspace` | tak |
| `.ai/project.md` | Overlay — Taskfile, Docker, porty | zalecany |
| `.ai/project.profile.yaml` | Lokalne nadpisania presetu | **nie** (tylko fork) |
| `.cursor/rules/use-guides.mdc` | Bootstrap MCP | tak |
| `.cursor/rules/code-review.mdc` | Review przed pushem | tak |
| `.cursor/BUGBOT.md` | Reguły Bugbota | tak |
| `.cursor/hooks.json` + `hooks/*.sh` | Review + blokady destrukcyjne | tak |
| `AGENTS.md` | Cienki — odsyła do MCP | tak |
| `.cursor/agents/*.md` | Subagenty `/review-*`, `/subagent-*` | zalecany |

W projekcie docelowym **nie** duplikuj `modules/` — wystarczy preset + opcjonalny overlay.

## Slash commands — konwencja nazw

| Prefiks | Rola | Przykłady |
|---------|------|-----------|
| `/review-*` | Review tylko do odczytu, raport | `/review-backend`, `/review-frontend`, `/review-architecture`, `/review-ui`, `/review-edge`, `/review-tests`, `/review-bugbot`, `/review-security` |
| `/subagent-*` | Praca w dwóch oknach (wymiana raportów) | `/subagent-backend`, `/subagent-frontend` |

| Slash | Plik szablonu |
|-------|----------------|
| `/review-architecture` | `templates/claude/agents/review-architecture.md` |
| `/review-backend` | `templates/claude/agents/review-backend.md` |
| `/review-frontend` | `templates/claude/agents/review-frontend.md` |
| `/review-ui` | `templates/claude/agents/review-ui.md` |
| `/review-edge` | `templates/claude/agents/review-edge.md` |
| `/review-tests` | `templates/claude/agents/review-tests.md` |
| `/subagent-backend` | `templates/claude/agents/subagent-backend.md` |
| `/subagent-frontend` | `templates/claude/agents/subagent-frontend.md` |
| `/review-bugbot`, `/review-security` | skille Cursor (user/global), nie ten kit |

Szablony skopiuj do `<projekt>/.cursor/agents/` (Cursor) i opcjonalnie `.claude/agents/`. Codex: `templates/codex/agents/*.toml` → `.codex/agents/`.

Po skopiowaniu **zrestartuj** okno Cursor — agenty ładują się przy starcie.

### Wywołanie

```text
/review-backend przejrzyj zmiany w backend/apps/products/
```

```text
/subagent-backend przejrzyj zmiany…   # potem wklej raport do /subagent-frontend w drugim oknie
```

## Cursor Hooks — bezpieczeństwo

| Hook | Zachowanie |
|------|------------|
| `gate-destructive.sh` | **deny** `git push --force` na main/master, `git reset --hard`, agresywny `git clean -f`; **ask** force na feature, push na main, `commit --no-verify`, `rm -rf` | 
| `gate-push.sh` | **ask** przed zwykłym `git push` (przypomnienie `/review-bugbot`); bypass `SKIP_PUSH_REVIEW=1` |

`gate-destructive` ma `failClosed: true` — padnięty skrypt blokuje akcję.

## Code review (Bugbot + GitHub)

Moduł MCP: `core:code-review` (bundle `devops` lub `architecture`).

| Warstwa | Plik / akcja |
|---------|----------------|
| Lokalnie | `/review-bugbot`, `/review-security`, `/review-backend`… |
| Przed push | `.cursor/hooks/gate-push.sh` + `gate-destructive.sh` |
| Na PR | Bugbot (GitHub integration) |
| Reguły | `.cursor/BUGBOT.md` |
| CI (ten kit) | `.github/workflows/ci.yml` — unittest + smoke FastMCP |

## Zależności Python (pin majora)

```toml
mcp>=1.0.0,<2      # FastMCP (1.x); mcp 2.0 usuwa mcp.server.fastmcp
pyyaml>=6.0,<7
```

`uvx` resolvuje zależności od zera (nie bierze lokalnego `uv.lock`) — upper bound chroni konsumentów przed breaking major.

## Skills / pluginy zewnętrzne (poza tym kitem)

Trzy warstwy — nie bundluj Matt/Superpowers w `guides-mcp`:

| Warstwa | Przykłady | Gdzie | Rola |
|---------|-----------|--------|------|
| Fundament | Context7, `project-guides`, `/review-*` | MCP projektu + agents z bootstrap | stack i review |
| Proces | [mattpocock/skills](https://github.com/mattpocock/skills) | `npx skills@latest add mattpocock/skills` | `/grill-me`, `/tdd` |
| Meta | superpowers, caveman | user / plugin Cursor | brainstorm, debug, finishing |

Priorytet w `AGENTS.md`: użytkownik → overlay+MCP → review kita → Matt → Superpowers.  
TDD: jeden path na feature (preferuj Matt). Setup Matt: po instalacji uruchom `/setup-matt-pocock-skills`.

Context7 (docs Django/Expo): globalnie `npx ctx7 setup --cursor`.

## Subagenty — szczegóły

Każdy plik agentów jest **cienkim wrapperem**: przy starcie woła `get_bundle` / `get_overlay` z MCP `project-guides`. Wiedza merytoryczna żyje w `modules/`.

Praca w dwóch oknach: `/subagent-backend` ↔ `/subagent-frontend` — sekcja „Raport do przekazania” na końcu odpowiedzi.
