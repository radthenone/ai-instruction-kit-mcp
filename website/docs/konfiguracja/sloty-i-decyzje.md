# Sloty i decyzje

**Slot** to nazwany punkt, w którym technologia może się różnić. **Decyzja** wybiera jedną technologię dla jednego slotu. Decyzje zapisujesz w Profilu w bloku `decisions:`:

```yaml title=".ai/project.profile.yaml"
decisions:
  database: postgres      # → infra:database:postgres
  cache: redis            # → infra:cache:redis
  queue: redis            # → infra:queue:redis (lub rabbitmq)
  storage: s3             # → infra:storage:s3
  tasks: celery           # → infra:tasks:celery
  search: postgres        # → infra:search:postgres (lub meilisearch)
  auth: jwt               # → capability:auth:jwt (wariant)
```

## Dozwolone wartości

| Slot | Wartości | Moduł |
|---|---|---|
| `database` | `postgres` | `infra:database:postgres` |
| `cache` | `redis` | `infra:cache:redis` |
| `queue` | `redis`, `rabbitmq` | `infra:queue:redis`, `infra:queue:rabbitmq` |
| `storage` | `s3`, `minio`, `aws` | `infra:storage:s3` (wszystkie trzy) |
| `search` | `postgres`, `meilisearch` | `infra:search:postgres`, `infra:search:meilisearch` |
| `tasks` | `celery` | `infra:tasks:celery` |
| `auth` | `custom` (domyślnie), `allauth`, `jwt` | wariant `capability:auth` |

Moduły infra trafiają automatycznie do bundli `infra` i `devops`.

## Auth: wariant, nie substytucja

`decisions.auth` dokłada moduł wariantu zaraz po `capability:auth`. Ogólny moduł zostaje. Dlatego:

- `custom` (domyślnie): brak wymuszonego pakietu, opisz wybór w overlayu,
- `allauth`: django-allauth w trybie headless,
- `jwt`: djangorestframework-simplejwt.

Kodegen działa inaczej: `codegen` **podmienia** moduł ogólny na wariant. Zob. [Język i codegen](jezyk-i-codegen.md).

## Nieznana decyzja

Literówka (`postgress`) albo technologia bez modułu nie wywraca serwera. Trafia do sekcji „Nierozpoznane decyzje” w narzędziu `get_index`. Zob. [ADR-0004](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0004-unknown-decisions-are-reported-not-fatal.md).

## Dodanie nowej technologii

Nie trzeba pisać Pythona ([ADR-0001](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0001-mappings-live-in-the-manifest.md)). Potrzebne są trzy kroki w repo kita:

1. napisz plik modułu, np. `modules/infra/queue/kafka.md`,
2. zarejestruj go w `manifest.yaml` w sekcji `modules:`,
3. dopisz wartość w `manifest.yaml` w `mappings.slots.queue.kafka`.

## Tryb lekki na VPS

Gdy host to VPS, `get_bundle` dokleja automatycznie moduł `infra:vps-lightweight` do każdego bundla. Zob. [Profil hosta](../hosty/profil-hosta.md).
