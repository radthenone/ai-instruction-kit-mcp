# Guardy: przegląd

**Guard** to hook, który agent uruchamia przed akcją. Odpowiada `allow` albo `deny` z powodem. Bootstrap kopiuje guardy do katalogu hooków wybranego klienta. Polityka ma **jedno źródło**: `templates/shared/guards/`.

## Zasady

- **Zero `ask`** ([ADR-0006](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0006-guards-never-ask.md)). Guard nigdy nie pyta człowieka. W trybie automatycznym `ask` blokowałby jak prompt, więc bramka, która pyta, nie byłaby automatyczna. Model dostaje powód odmowy i sam wybiera bezpieczną alternatywę.
- **Fail-closed**: padnięty guard albo nieczytelny payload daje `deny`. Wyjątek: w Copilocie timeout hooka przepuszcza wywołanie.
- **Poza repo** pilnowane są tylko katalogi systemowe i sekrety. Resztę pilnuje natywna zgoda klienta.
- **Zwykła praca w repo nie jest blokowana**, także `rm -rf` w repo. Git odzyska tylko pliki śledzone i zacommitowane. Nieśledzone pliki i niezacommitowane zmiany po takim usunięciu przepadają.

## Które guardy działają u którego klienta

| Guard | Co robi | Claude | Cursor | OpenCode | Codex | Copilot | Antigravity |
|---|---|---|---|---|---|---|---|
| `git-guard` | destrukcyjne komendy git, push na chronione gałęzie | tak | tak | tak | tak | tak | tak |
| `sensitive-files-guard` | odczyt i zapis sekretów, ręczna edycja lockfile | tak | tak | tak | tak | tak | tylko narzędzia plikowe |
| `server-guard` | ciężkie komendy na VPS | tak | tak | tak | tak | tak | tak |
| `bash-guard` | blokuje `pwsh`, `powershell`, `cmd` w Bashu (Windows) | tak | | | | | |
| `linters-guard` | lint po edycji, wynik wraca do modelu | tak | | | | | |
| `rtk-check` | przypomina o `rtk`, gdy go brak | tak | | | | | |
| `subagent-remote-guard` | blokuje zdalne narzędzia w subagentach | tak | | | | | |
| `retro-session-end` | analiza sesji po jej zakończeniu | tak | | | | | |

Szczegóły każdego guarda: [Guardy: pozostałe i szczegóły](pozostale.md). Serwerowy jest opisany osobno: [Server guard](../hosty/server-guard.md).

## Adapter dla każdego klienta

Skrypty polityki mówią jednym dialektem: kontraktem Claude Code. Każdy klient ma inny kształt wejścia i wyjścia. Różnicę tłumaczy `invoke-hook.js`, jedyne miejsce w kicie, które wie o różnicach między klientami.

| Klient | Wywołanie |
|---|---|
| Claude Code | `node .claude/hooks/<guard>.mjs`, bez adaptera |
| Cursor | `node .cursor/hooks/invoke-hook.js <guard>.mjs --to cursor` |
| OpenCode | plugin `.opencode/plugins/kit-guards.js`, który woła adapter |
| Codex | `node …/.codex/hooks/invoke-hook.js <guard>.mjs --to codex` |
| Copilot (VS Code i CLI) | `node .github/hooks/invoke-hook.js <guard>.mjs --to copilot` |
| Antigravity | launcher `node -e …`, który szuka `invoke-hook.js` w katalogach nad sobą |

## Znane luki

Guardy są tekstowe, nie piaskownicą. Na części klientów nie wszystkie narzędzia są mapowane:

- **OpenCode, Codex**: `grep` i `glob` nie są pilnowane.
- **Copilot**: `grep_search` i `file_search` nie są mapowane, więc sensitive-files-guard ich nie widzi.
- **Antigravity**: `grep_search`, `find_by_name` i `list_dir` nie są mapowane.
- **Bash**: sensitive-files-guard blokuje **oczywiste** odczyty sekretów, np. `cat .env`. Nie blokuje `python -c "open('.env')"`.

Te luki są opisane świadomie. Nie łataj ich doklejaniem wzorców bez dowodu, że są potrzebne.
