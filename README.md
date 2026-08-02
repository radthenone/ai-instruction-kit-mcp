# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają stack przez **preset** (w kicie) albo lokalny profil.

## Uruchomienie (zalecane — bez `.ai/project.profile.yaml`)

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

| Flaga | Rola |
|-------|------|
| `--preset NAME` | Preset z kita (`profiles/NAME.yaml`) — **nie wymaga** lokalnego profilu. Szablon = `_base`; produkt e-commerce = `olivin-app` |
| `--workspace PATH` | Root repo aplikacji (tu szukane jest `.ai/project.md`) |
| `--overlay PATH` | Dodatkowy overlay (wielokrotnie) |
| `--profile PATH` | Lokalny `.ai/project.profile.yaml` — **tylko** gdy naprawdę nadpisujesz capabilities/decisions |

Opcjonalnie w projekcie: samo `.ai/project.md` (Taskfile, porty, ścieżki) — ładowane automatycznie z `--workspace`.

Lokalny profil twórz **tylko** gdy projekt różni się od presetu:

```yaml
# .ai/project.profile.yaml (opcjonalne — fork)
name: moj-fork
extends: profiles/_base.yaml   # lub profiles/olivin-app.yaml
decisions:
  queue: rabbitmq
```

Dev lokalny (przed pushem na GitHub):

```json
"--from", "/absolutna/sciezka/do/ai-instruction-kit-mcp"
```

Bootstrap:

```bash
# Nowy / generyczny projekt
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --preset _base \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp \
  --with-overlay

# Produkt e-commerce (preset w kicie)
./scripts/bootstrap-project.sh /sciezka/do/olivin-app \
  --preset olivin-app \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp
```

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
  _base.yaml         wspólny preset (extends w profilach projektów)
  *.yaml             presety projektów (np. olivin-app)
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
