# Overlay zasad (szablon — **docelowy** kontrakt)

> Ten plik jest szablonem pod przyszłe `--overlays`
> (design: `docs/specs/2026-08-05-mcp-profile-architecture-overlays-design.md`).
> **Dziś** w runtime nadal używaj `.ai/project.md` + `--workspace` (albo skopiuj sekcje stąd).

## Codegen (Orval — w profilu projektu)

Ustaw **jedną** wartość w `.ai/project.profile.yaml` — reviewery FE/BE i CI api-contract z niej korzystają:

```text
codegen: orval
```

| Wartość | Kiedy |
|---------|--------|
| `orval` | REST API + FE z wygenerowanym klientem OpenAPI (default) |
| `none` | REST bez Orval — generyczny klient innym narzędziem albo ręczny fetch/typy |
| `graphql` | GraphQL zamiast REST — patrz `arch:api-contract:graphql` |

MCP `get_codegen` czyta ją wyłącznie z profilu (ADR-0007; bez pary backend + klient efektywny codegen to `none`).

Gdy `orval`: po zmianie serializera/viewsetu/schema → `task ovral:generate` (lub task z Taskfile poniżej) → commit wygenerowanych plików.

## Po wdrożeniu CLI

Fakty produktu i lokalne nadpisania reguł kita:

- Porty, Taskfile, Docker
- Odstępstwa od Tierów świadomie zaakceptowane

W mcp.json (po implementacji):

```text
"--overlays", "${workspaceFolder}/.ai/extras.md"
```
