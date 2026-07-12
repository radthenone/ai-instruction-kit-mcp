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
  olivin-app.yaml    e-commerce preset
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

## olivin-app

W repo olivin-app zostaw tylko:

- `.ai/project.profile.yaml` — `extends: profiles/olivin-app.yaml`
- `.ai/project.md` — overlay (Taskfile, Docker, porty)
- `.cursor/mcp.json` — uvx
- `.cursor/rules/use-guides.mdc`
- cienki `AGENTS.md`

Usuń: `docs/ai/*.md`, stare `.cursor/rules/cursor-*.mdc`, długie `.github/instructions/`.

## Context7

Docs Django/Expo/Stripe — globalnie `npx ctx7 setup --cursor`, osobno od instruction-kit.
