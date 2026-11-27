# Jak działa kit

Kit to **centralne repo instrukcji** i **serwer MCP**. Projekt zapisuje swoje wybory w Profilu i dodaje Overlay. Agenci czytają gotowe Bundle na żywo. Treść modułów nie jest kopiowana do projektu, więc nie starzeje się w repo. Serwer ze zdalnego źródła może jednak czytać starszą kopię z cache `uv`, zob. [Aktualizacja](../start/aktualizacja.md). Agenci, komendy i skille są kopiowane przy bootstrapie, więc po aktualizacji kita wymagają `kit-ai reload`.

## Trzy poziomy

| Poziom | Co to jest | Gdzie leży |
|---|---|---|
| **Kit** | moduły instrukcji (`modules/`), manifest (`manifest.yaml`), serwer MCP (`src/guides/`) | repo kita, cache `uv` |
| **Profil** | wybory projektu: język, klienci, Tiery, Decyzje | `.ai/project.profile.yaml` w repo aplikacji |
| **Overlay** | fakty tylko tego repo: ścieżki, porty, komendy | `.ai/project.md` w repo aplikacji |

## Co dostaje agent

1. **Brief**: krótka orientacja w instrukcjach serwera MCP i w sekcji `kit:brief` pliku `AGENTS.md`. Zawiera reguły znane przed pierwszą akcją i wskaźnik do `get_overlay`.
2. **Bundle** (`get_bundle`): uporządkowany zestaw modułów dla danego rodzaju pracy, np. `backend` albo `frontend`. Składany z Tierów z Profilu.
3. **Overlay** (`get_overlay`): reguły jednego repo. Pobierany na żądanie, nigdy nie wklejany do briefu.

## Co kopiuje bootstrap, a czego nie

`kit-ai install` i `kit-ai reload` zapisują do projektu pliki zgodne z Profilem: konfigurację klientów, agentów, komendy, skille, hooki guardów, `BUGBOT.md`.

Treści modułów **nie** kopiuje. Czyta je serwer MCP na żywo.

Wyjątkiem są **Brief Rules**, czyli kilka reguł: klasyfikacja zadań, `get_overlay` przed edycją, format docstringów, zakaz instalacji na VPS. Są renderowane z jednego szablonu do trzech nośników: hooka Claude, instrukcji MCP i `AGENTS.md`. Zob. [ADR-0010](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0010-brief-as-artifact.md).

## Kit Root i Workspace

- **Kit Root** to katalog z manifestem i modułami. W dev jest to klon gita, w produkcji katalog danych w pakiecie.
- **Workspace** to katalog repo aplikacji. Tu leżą Overlay i stamp bootstrapu. Nigdy nie jest to Kit Root.

## Dwie drogi, dwa skutki

| Droga | Kiedy | Skutek |
|---|---|---|
| **Serwowanie na żywo** (MCP) | `get_bundle`, `get_overlay`, `get_module` | zawsze aktualna treść kita, bez kopiowania |
| **Bootstrap** (kopiowanie) | `kit-ai install`, `kit-ai reload` | pliki klientów, agenci i hooki zgodne z Profilem |

## Bezpieczeństwo w tym modelu

Guardy są w repo i blokują niebezpieczne akcje agenta: destrukcyjne komendy gita, odczyt sekretów, ciężkie komendy na VPS. Polityka ma jedno źródło w `templates/shared/guards/` i jest tłumaczona na dialekt każdego klienta. Guard odpowiada zawsze `allow` albo `deny`, nigdy `ask`. Zob. [Guardy: przegląd](../guardy/przeglad.md).

## Dalej

- [Warstwy AI](warstwy-ai.md): które narzędzie do czego.
- [Przepływ zmiany](przeplyw-zmiany.md): jedna zmiana od issue do PR.
- [Glosariusz](glosariusz.md): nazwy używane na tej stronie w jednym miejscu.
