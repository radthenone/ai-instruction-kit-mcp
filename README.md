# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają moduły przez `.ai/project.profile.yaml`.

## Uruchomienie (uvx — bez lokalnego klona)

```json
{
  "mcpServers": {
    "project-guides": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git",
        "guides-mcp",
        "--profile", "${workspaceFolder}/.ai/project.profile.yaml"
      ]
    }
  }
}
```

**Wybór modułów** = `.ai/project.profile.yaml` w projekcie (extends `profiles/<nazwa-projektu>.yaml`).

Dev lokalny (przed pushem na GitHub):

```json
"--from", "M:/projects/ai-instruction-kit-mcp"
```

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
  *.yaml             presety projektów (np. e-commerce)
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

W **repo aplikacji** (nie w instruction-kit) skopiuj z `templates/`:

| Plik | Rola |
|------|------|
| `.ai/project.profile.yaml` | `extends: profiles/<preset>.yaml` z tego kita |
| `.ai/project.md` | Overlay — Taskfile, Docker, porty |
| `.cursor/mcp.json` | uvx → instruction-kit |
| `.cursor/rules/use-guides.mdc` | Bootstrap MCP |
| `.cursor/rules/code-review.mdc` | Przypomnienie o review przed pushem |
| `.cursor/BUGBOT.md` | Reguły Bugbota (z `templates/cursor/BUGBOT.md`, dostosuj) |
| `.cursor/hooks.json` + `.cursor/hooks/gate-push.sh` | Przypomnienie przy `git push` |
| `AGENTS.md` | Cienki — odsyła do MCP i overlay |

Opcjonalnie: `.git/hooks/pre-push` z `templates/git-hooks/pre-push`.

W projekcie docelowym **nie** duplikuj modułów z `modules/` — wystarczy profil + overlay + `.cursor/`.

## Code review (Bugbot + GitHub)

Moduł MCP: `core:code-review` (bundle `devops` lub `architecture`).

| Warstwa | Plik / akcja |
|---------|----------------|
| Lokalnie | `/review-bugbot`, `/review-security` w Cursor |
| Przed push | `.cursor/hooks/gate-push.sh` |
| Na PR | Bugbot (GitHub integration) |
| Reguły | `.cursor/BUGBOT.md` |
| CI | `arch:ci-cd` — testy + typy + opcjonalnie check Bugbota |

Szablony: `templates/cursor/`, `templates/git-hooks/`.

## Context7

Docs Django/Expo/Stripe — globalnie `npx ctx7 setup --cursor`, osobno od instruction-kit.
