# Profile projektów

| Plik | Rola |
|------|------|
| `_base.yaml` | Wspólny preset — stacks, patterns, domyślne bundle overrides |
| `olivin-app.yaml` | olivin-app — monorepo e-commerce (extends `_base`) |

## Nowy projekt

1. Skopiuj `templates/project.profile.yaml` do `.ai/project.profile.yaml` w repo
2. Opcjonalnie: skopiuj `olivin-app.yaml` → `profiles/moj-projekt.yaml`, dopasuj `capabilities`, `domains`, `decisions`
3. W profilu projektu:

```yaml
# .ai/project.profile.yaml
name: moj-projekt
extends: profiles/_base.yaml   # lub profiles/moj-projekt.yaml
capabilities: []
domains: []
decisions: {}
overlays:
  - .ai/project.md
```

## Sloty `decisions`

| Slot | Wartości | Moduł |
|------|----------|-------|
| `database` | `postgres` | `infra:database:postgres` |
| `cache` | `redis` | `infra:cache:redis` |
| `queue` | `redis`, `rabbitmq` | `infra:queue:*` |
| `storage` | `s3` | `infra:storage:s3` (MinIO, AWS, R2…) |
| `tasks` | `celery` | `infra:tasks:celery` |

Moduły infra dopisywane są automatycznie do bundle `infra` i `devops`.
