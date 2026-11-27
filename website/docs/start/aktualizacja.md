# Aktualizacja kita

Aktualizacja to dwa kroki: nowa wersja narzędzia i odświeżenie plików w projekcie.

```bash title="Git Bash · bash"
uv tool upgrade guides-mcp      # nowa wersja kita
kit-ai reload                   # odśwież pliki kita w projekcie
```

Inny ref, np. `dev`: `uv tool install --force git+https://github.com/radthenone/ai-instruction-kit-mcp@dev`, a potem `kit-ai reload`.

## Kiedy aktualizować

Narzędzie MCP `check_kit_status` porównuje commit kita zapisany przy bootstrapie (`.ai/.kit-bootstrap.json`) z aktualnym. Mówi, co się zmieniło, które pliki bootstrap wciągnie sam, a które trzeba przenieść ręcznie.

## Co `reload` nadpisuje

| Co | Przy `kit-ai reload` |
|---|---|
| agenci, komendy, skille, hooki klientów | **zawsze nadpisane** świeżą kopią. Traktuj jak wygenerowany kod |
| konfiguracje MCP (`.mcp.json`, `.codex/config.toml`, …) | nadpisane, ale scalane: Twoje serwery zostają |
| `BUGBOT.md` | renderowany z szablonu. Blok `<!-- project:rules -->` przechodzi bez zmian |
| `AGENTS.md`, `.ai/project.md` | kopiowane **tylko gdy ich brak**. Zmiany kita w tych plikach przenosisz ręcznie |
| `modules/*.md` (treść instrukcji) | **nie są kopiowane**. MCP czyta je z klona kita przy każdym `get_bundle` |

## Gdy masz pracę w toku

Bootstrap nadpisuje `.claude/{agents,commands,hooks}/`, `.codex/`, `.github/prompts/`, `copilot-instructions.md` i pliki MCP. Jeśli edytowałeś je ręcznie, najpierw sprawdź `git diff`.

Plan bez zapisu (dry run) z poziomu agenta:

```text
reload_workspace()                  # dry run: lista plików nowych, nadpisanych, usuniętych
reload_workspace(dry_run=False)     # odświeżenie z Profilu
```

## Lokalny klon kita

Serwer MCP ze **zdalnego** źródła (`git+https://…`) czyta moduły z kopii w cache `uv`, która zmienia się dopiero po zmianie wersji. Przy **lokalnym klonie** bootstrap generuje `uv run --project <klon>`, więc edycja `modules/` albo `src/guides/` działa po restarcie klienta.

Objaw nieaktualnego cache: edytujesz `modules/…`, restartujesz klienta, a `get_bundle` zwraca starą treść, bez żadnego komunikatu. Rozwiązanie: lokalny klon albo nowa wersja narzędzia.

## Migracja z `project-guides`

Serwer MCP nazywał się `project-guides`, teraz nazywa się `kit-ai-mcp`. Ponowne `kit-ai install` albo `kit-ai reload` podmienia wpis kita w konfiguracji klienta i usuwa stary wpis. Cudzych serwerów nie rusza. Nazwy narzędzi zmieniają się na `mcp__kit-ai-mcp__…`, więc zaktualizuj też uprawnienia w `.claude/settings.local.json`, jeśli tam je masz.
