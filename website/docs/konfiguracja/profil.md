# Profil projektu

Profil to **jedyna konfiguracja** kita. Leży w repo aplikacji jako `.ai/project.profile.yaml`, jest commitowany i wspólny dla wszystkich maszyn. Kit nie dostarcza gotowych profili.

## Przykład

```yaml title=".ai/project.profile.yaml"
name: moja-appka
language: pl
clients: claude,codex

backend: django          # none | django | django-html | fastapi | flask
web: react               # none | react | react@legacy | angular | angular@rxjs | expo
mobile: none             # none | expo | react-native

codegen: orval           # orval | none | graphql (bez pary backend + klient: zawsze none)

capabilities:
  - auth
  - payments

decisions:
  database: postgres
  auth: jwt

integrations:
  - coderabbit
```

## Klucze

| Klucz | Wartości | Znaczenie |
|---|---|---|
| `name` | tekst | nazwa produktu, widoczna w Brief |
| `language` | `pl` \| `en` | język prozy. Tytuły issue, PR i branchy zawsze po angielsku |
| `clients` | lista albo `all` | klienci, dla których bootstrap zapisuje pliki |
| `backend`, `web`, `mobile` | stack albo `none` | stack per Tier. Zob. [Tiery i stacki](tiery-i-stacki.md) |
| `codegen` | `orval` \| `none` \| `graphql` | generowanie klienta API. Zob. [Język i codegen](jezyk-i-codegen.md) |
| `capabilities` | lista | funkcje produktu: `auth`, `files`, `payments` |
| `decisions` | mapa | technologie w slotach, np. `database: postgres`. Zob. [Sloty i decyzje](sloty-i-decyzje.md) |
| `patterns` | lista | wzorce, np. `capability-provider`, `webhooks` |
| `include` | lista ID modułów | dodatkowe moduły po ID, routing po tagach |
| `integrations` | lista | zewnętrzne narzędzia, zob. niżej |
| `targets`, `agents` | bloki | modele agentów. Zob. [Modele agentów](modele-agentow.md) |
| `worktree` | blok | synchronizacja worktree. Zob. [Managed Worktree](../koncepcja/managed-worktree.md) |
| `server` | blok | konfiguracja server guarda. Zob. [Server guard](../hosty/server-guard.md) |

## Integracje

Lista zewnętrznych narzędzi. Pusta lista oznacza brak integracji. Nieznana nazwa daje ostrzeżenie i jest pomijana.

- `orca`: renderuje `orca.yaml`. Reload usuwa plik, gdy Profil go już nie wymienia.
- `coderabbit`: renderuje `.coderabbit.yaml`, z językiem z `language:`.
- `t3code`: nie tworzy pliku. Włącza kartę transportu T3 Code dla `/kit-ai:night-run`.

## Zmiana Profilu

1. Edytuj `.ai/project.profile.yaml`, albo zrób to przez `/kit-ai:kit-project-edit "…"`, które pokazuje podgląd.
2. Uruchom `kit-ai reload` (albo MCP `reload_workspace(dry_run=False)`).
3. Zrestartuj klienta.

Reload nie rusza `.ai/project.md`.

!!! warning "Stare klucze"
    Klucze `stacks:` i `patterns:` nadal są czytane. Stare `models:` i `t3.targets` przerywają reload z komunikatem o migracji. Przenieś je do bloku `targets:`.

## Błędy składni

Profil z błędem YAML: reload ostrzega i nie zmienia plików integracji ani karty T3. Zdublowany klucz `integrations:` albo nieprawidłowa data zostawiają kartę T3 bez zmian. Bez PyYAML reload nie sprawdzi składni, więc karta T3 też zostaje bez zmian, a pojawia się ostrzeżenie.
