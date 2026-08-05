# Profile / presety

Kanoniczna lista kategorii. **Pełna tabela flag MCP** (`--preset`, `--workspace`, `--language`, `--profile`, planowane `--tag`) → [README główny](../README.md#konfiguracja-projektu--argumenty-guides-mcp).

| Plik | Rola |
|------|------|
| `_base.yaml` | Fundament stacku (Django+Expo, patterns) — **domyślny**, nie musisz podawać w CLI; `language: pl` |
| `shop.yaml` | **Kategoria** e-commerce (auth, shop, payments, infra) |
| inne `*.yaml` | Kolejne **kategorie** (np. `blog`) — nie nazwy produktów |

## Język

| Mechanizm | Priorytet |
|-----------|-----------|
| `--language pl\|en` / env `GUIDES_LANGUAGE` | najwyższy (CLI MCP) |
| `language:` w YAML profilu / `extends` | średni |
| domyślnie | `pl` |

Tytuły issue/PR/branch: zawsze EN. Proza (body, docstringi, commity, czat): wybrany język. Tool: `get_language`.

## Warstwy — co pisać gdzie

| Potrzeba | Mechanizm | Plik / flaga |
|----------|-----------|--------------|
| Nowy typ produktu (blog, CRM…) | Nowa kategoria w kicie | `profiles/<nazwa>.yaml` + `--preset <nazwa>` |
| Ten sam shop, inne fakty (jubiler, porty) | Overlay | `.ai/project.md` + `--workspace` |
| Ten sam shop, inny zestaw modułów | Fork | `.ai/project.profile.yaml` + `--profile` (bez `--preset`) |
| Ten sam shop, powtarzalny wariant MD w wielu repo | Tagi / facety | **planowane** — zob. README; na razie overlay |

Nie twórz profilu o nazwie konkretnego produktu — produkt = overlay w repo aplikacji (`.ai/project.md`).

> Docelowy kontrakt (`--profile` / `--overlays` / stack CLI):  
> [design](../docs/superpowers/specs/2026-08-05-mcp-profile-architecture-overlays-design.md) — **CLI jeszcze nie**.

## Nowy projekt (zalecane — zero lokalnego profilu)

```bash
# Generyczny — default _base + PL, bez --preset w CLI
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --from /sciezka/do/kita \
  --with-overlay

# Kategoria e-commerce, proza EN
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --preset shop \
  --language en \
  --from /sciezka/do/kita
```

Bootstrap zapisuje flagi w `.cursor/mcp.json`. Opcjonalnie `.ai/project.md`.

## Fork kategorii (modyfikacja vs preset)

Tylko gdy **to repo** nadpisuje `capabilities` / `domains` / `decisions` względem kategorii (nie kopiuj samego `extends` bez zmian):

```yaml
# .ai/project.profile.yaml
name: moj-fork
extends: profiles/shop.yaml
decisions:
  queue: rabbitmq
overlays:
  - .ai/project.md
```

W mcp.json: `--profile ${workspaceFolder}/.ai/project.profile.yaml` **zamiast** `--preset`.

Fork kita (własne MD / nowe kategorie): edytuj `profiles/` i `modules/` w swoim klonie / forkach GitHub, potem `--from` na ten fork.

## Tagi (plan — niezaimplementowane)

Gdy wariant instrukcji powtarza się w wielu projektach przy tej samej kategorii, docelowo w YAML kategorii:

```yaml
# szkic — jeszcze nie czytane przez resolver
name: shop
facets:
  fulfillment: [physical, digital]
```

i w mcp.json: `--tag physical` (lub `--facet fulfillment=physical`). Do czasu implementacji: overlay albo fork.

## Sloty `decisions`

| Slot | Wartości | Moduł |
|------|----------|-------|
| `database` | `postgres` | `infra:database:postgres` |
| `cache` | `redis` | `infra:cache:redis` |
| `queue` | `redis`, `rabbitmq` | `infra:queue:*` |
| `storage` | `s3` | `infra:storage:s3` (MinIO, AWS, R2…) |
| `tasks` | `celery` | `infra:tasks:celery` |

Moduły infra dopisywane są automatycznie do bundle `infra` i `devops`.
