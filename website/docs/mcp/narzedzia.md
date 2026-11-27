# Narzędzia MCP

Serwer `kit-ai-mcp` udostępnia narzędzia, które agent wywołuje sam. Większość tylko czyta. Trzy zapisują do projektu, więc domyślnie działają w trybie **dry run**.

## Odczyt

| Narzędzie | Parametry | Co zwraca |
|---|---|---|
| `get_bundle` | `name` | treść bundla: `backend`, `frontend`, `architecture`, `infra`, `devops`, `payments`, `full` |
| `list_bundles` | | nazwy bundli i ich zakres |
| `get_module` | `module_id` | treść jednego modułu, np. `infra:queue:redis` |
| `list_modules` | | lista modułów z opisami |
| `get_overlay` | | `.ai/project.md` tego repo |
| `get_index` | | stan projektu: profil, moduły, nierozpoznane decyzje, host |
| `get_language` | | język z Profilu |
| `get_codegen` | | tryb codegenu z Profilu |
| `get_clients` | | klienci i ich pliki konfiguracji |
| `get_council` | | opis rady delegatów (`review-council`) |
| `list_questions` | | katalog pytań o projekt z warunkami na bieżącym Profilu |
| `check_kit_status` | | czy kit zmienił się od ostatniego bootstrapu |

## Zapis (dry run domyślnie)

| Narzędzie | Parametry | Co robi |
|---|---|---|
| `reload_workspace` | `dry_run=True` | odświeża pliki kita z Profilu. Dry run pokazuje plan |
| `bootstrap_workspace` | `clients`, `language`, `with_overlay`, `keep_unselected_clients`, `dry_run=True` | instalacja w workspace. Wymaga `--workspace` |
| `ensure_labels` | `dry_run=True` | zakłada brakujące etykiety GitHuba. Istniejących nie zmienia |

`dry_run=True` nic nie zapisuje. Raport pokazuje pliki nowe, nadpisane i usunięte. Zapis wymaga jawnego `dry_run=False`.

!!! warning "Narzędzia MCP nie są pilnowane hookami"
    Hooki kita (`PreToolUse`) łapią `Bash`, `PowerShell` i narzędzia plikowe, a nie nazwy narzędzi MCP. Jedyną ochroną przed zapisem przez MCP jest domyślny `dry_run=True`. Nie zmieniaj go na `False` bez przeczytania planu.

## Typowy start agenta

1. `check_kit_status`: czy kit jest aktualny.
2. `get_overlay`: fakty tego repo. Obowiązkowo przed pierwszą edycją.
3. `get_bundle` dla obszaru pracy, np. `backend`.
4. Dopiero potem edycja kodu.

Ta kolejność wynika z Brief Rules. Zob. [Jak działa kit](../koncepcja/jak-dziala-kit.md).

## Jak wywołać

Agent wywołuje narzędzia sam. Ty możesz poprosić wprost:

```text
get_bundle("backend")
reload_workspace()                  # dry run
reload_workspace(dry_run=False)     # zapis
```

Konfiguracja serwera (argumenty i zmienne środowiskowe): [Konfiguracja serwera MCP](konfiguracja-serwera.md).
