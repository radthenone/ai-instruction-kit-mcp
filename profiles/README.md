# Profile projektów

| Plik | Rola |
|------|------|
| `_base.yaml` | Wspólny preset — stacks Django+Expo, patterns, typing |
| `olivin-app.yaml` | Preset produktu e-commerce (auth, shop, payments, infra) |
| inne `*.yaml` | Kolejne produkty / stacki |

## Nowy projekt (zalecane — zero lokalnego profilu)

W `.cursor/mcp.json`:

```text
--preset _base                 # albo olivin-app / inny produkt
--workspace ${workspaceFolder}
```

Opcjonalnie tylko `.ai/project.md` (overlay). Lokalny `.ai/project.profile.yaml` **nie jest wymagany**.

```bash
./scripts/bootstrap-project.sh /sciezka/do/projektu --preset _base --from /sciezka/do/kita --with-overlay
```

## Kiedy tworzyć lokalny profil

Tylko gdy **to repo** nadpisuje capabilities / domains / decisions względem presetu z kita (nie kopiuj samego `extends` bez zmian):

```yaml
# .ai/project.profile.yaml
name: moj-fork
extends: profiles/_base.yaml
decisions:
  queue: rabbitmq
overlays:
  - .ai/project.md
```

Wtedy w mcp.json: `--profile ${workspaceFolder}/.ai/project.profile.yaml` zamiast `--preset`.

## Sloty `decisions`

| Slot | Wartości | Moduł |
|------|----------|-------|
| `database` | `postgres` | `infra:database:postgres` |
| `cache` | `redis` | `infra:cache:redis` |
| `queue` | `redis`, `rabbitmq` | `infra:queue:*` |
| `storage` | `s3` | `infra:storage:s3` (MinIO, AWS, R2…) |
| `tasks` | `celery` | `infra:tasks:celery` |

Moduły infra dopisywane są automatycznie do bundle `infra` i `devops`.
