# Instruction Kit — MCP z instrukcjami projektów

Centralne repo instrukcji Markdown i serwer MCP `kit-ai-mcp`. Projekt wybiera Stack **per Tier** (`backend` / `web` / `mobile` w `.ai/project.profile.yaml`) i dodaje overlay (`.ai/project.md`). Agenci czytają bundle na żywo przez MCP, więc treść instrukcji nie jest kopiowana do projektu i nie starzeje się.

**Dokumentacja:** <https://radthenone.github.io/ai-instruction-kit-mcp/> (źródło: [`website/docs/`](website/docs/)). README zawiera tylko start i mapę. Szczegóły są w dokumentacji.

## Szybki start

### Krok 1 — Instalacja

```bash
uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
cd /m/projects/moja-appka                  # repo aplikacji
kit-ai install
```

Bez `@` instalujesz gałąź domyślną (`master`). Nowsze, jeszcze nie wydane zmiany są na `dev`, wtedy dopisz ref, np. `…/ai-instruction-kit-mcp@dev`.

**Wymagania:** `uv` w `PATH`, `bash` (Windows: Git for Windows), `node` (hooki), `python3`, `gh` (procedury issue i PR), opcjonalnie `npx`.

### Krok 2 — Konfiguracja

Zrestartuj IDE / CLI, potem w kliencie AI:

```text
/kit-ai:kit-project-begin      # pierwszy raz: pytania o Stack, karta Profilu i .ai/project.md
/kit-ai:kit-project-edit "…"   # później: jedna zmiana, np. "zmień web na angular"
```

### Krok 3 — Update

```bash
uv tool upgrade guides-mcp                 # nowa wersja kita
kit-ai reload                              # odśwież pliki kita w projekcie
kit-ai status                              # w agencie: check_kit_status
kit-ai doctor                              # ścieżki i komendy w regułach vs repo
```

Pozostałe komendy CLI: `kit-ai remove [--dry-run]`, `kit-ai labels [--apply]`, `kit-ai host`, `kit-ai night-ctx`, `kit-ai retro scan|report`, `kit-ai issue stats`, `kit-ai pr stats`.

## Mapa dokumentacji

| Dział | Co tam jest |
| --- | --- |
| [Start](website/docs/start/) | instalacja (Windows i Linux), pierwsza konfiguracja, aktualizacja, narzędzia zewnętrzne (Superpowers, skille Matta, Context7, rtk) |
| [Koncepcja](website/docs/koncepcja/) | jak działa kit, warstwy AI, przepływ zmiany, Managed Worktree, glosariusz, ADR-y |
| [Konfiguracja](website/docs/konfiguracja/) | Profil, Tiery i stacki, overlay, moduły i bundle, sloty, klienci, język i codegen, modele agentów, pliki w projekcie |
| [Hosty](website/docs/hosty/) | profil hosta `local` / `vps`, Windows, Linux VPS, server guard |
| [Komendy](website/docs/komendy/) | `git-*`, `review-*`, `create-task`, `kit-project-*`, `night-run`, `headless`, `teacher-*` |
| [MCP](website/docs/mcp/) | narzędzia serwera, argumenty i zmienne środowiskowe |
| [Guardy](website/docs/guardy/) | git-guard, sensitive-files-guard, server-guard i adaptery klientów |
| [Diagnostyka](website/docs/diagnostyka/) | doctor, retro, rozwiązywanie problemów, FAQ |
| [Dla autorów kita](website/docs/autorzy/) | architektura repo, dodawanie modułu i agenta, testy i CI |

Podgląd lokalny: `cd website && uvx zensical serve -o`. Build: `uvx zensical build -s`.

## Brief projektu i instrukcje MCP ([ADR-0010](docs/adr/0010-brief-as-artifact.md))

Serwer MCP `kit-ai-mcp` przy handshake'u przekazuje klientowi instrukcje serwera z **Briefem projektu** i mapą narzędzi. Ten sam brief trafia przy `kit-ai reload` do bloku `<!-- kit:brief -->` w `AGENTS.md`.

- Overlay nie jest wklejany do briefu ani instrukcji MCP. Fakty repo agent pobiera na żądanie przez `get_overlay()`, przed pierwszą edycją kodu.
- Reguły briefu mają jedno źródło: szablon `templates/shared/rules/brief-rules.md`, renderowany do hooka Claude, instrukcji MCP i bloku `<!-- kit:brief-rules -->` w `AGENTS.md`. Żaden plik nie zawiera ręcznej kopii reguł.

## Repo kita

```text
src/guides/     serwer MCP i CLI kit-ai
modules/        treść instrukcji (Module ID → plik)
templates/      szablony klientów; templates/shared/ to wspólne źródło agentów, skilli i guardów
manifest.yaml   rejestr modułów, Tierów, bundli i mapowań (ADR-0001)
website/        strona dokumentacji (Zensical); nie jest kopiowana do projektów
docs/           adr/, agents/, specs/, plans/
```

Słownik pojęć: [`CONTEXT.md`](CONTEXT.md). Decyzje: [`docs/adr/`](docs/adr/). Zasady pracy agentów w tym repo: [`AGENTS.md`](AGENTS.md).

Testy: `uv run python -m unittest discover -s tests` (pełna suita ~15–20 min, uruchamia ją CI). Lokalnie wybrany moduł: `uv run python -m unittest discover -s tests -p test_<moduł>.py` albo `uv run --no-sync python scripts/test_changed.py`.
