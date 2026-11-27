# Guardy: pozostałe i szczegóły

## git-guard

Blokuje (`deny`):

- `git reset --hard` i `git clean -f`,
- force push i zwykły push na `main`, `master`, `dev` (także `--force-with-lease` i plus-refspec),
- `git branch -D`,
- `git checkout .` i `git checkout --`,
- rekursywne `rm` na szerokiej ścieżce: `~`, `/`, `..`, katalogi domowe,
- mutację i przekierowanie do `~/.ssh`, `/etc`, `C:\Windows`, `Program Files`, `~/.claude/settings*.json`.

Reszta przechodzi (`allow`): `git stash`, `git restore`, `find -delete`, `rm -rf` w repo.

## sensitive-files-guard

Blokuje odczyt i zapis sekretów w narzędziach plikowych:

- pliki `.env*` poza `.env.example`, `.env.sample`, `.env.template`,
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `.netrc`, `credentials.json`,
- `.git/objects`, `.git/refs`, `.git/hooks`.

Blokuje też ręczną edycję lockfile: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`, `uv.lock`, `poetry.lock`, `Cargo.lock`. Odczyt lockfile jest wolny.

W Bashu blokuje **oczywisty** odczyt sekretu: komendę czytającą (`cat`, `head`, `tail`, `grep`, `sed`, `awk`, `base64` i podobne) z argumentem będącym ścieżką sekretu. Przechodzą `cp .env.example .env`, `ls -la .env` i `git check-ignore .env`. Parser jest tekstowy, nie AST. Pełniejszej ochrony wymagałaby piaskownica, której kit nie udaje.

## bash-guard (Claude, Windows)

Blokuje `pwsh`, `powershell` i `cmd` uruchamiane z narzędzia Bash. Agent na Windows używa Git Bash. Narzędzie PowerShell nie jest blokowane.

## subagent-remote-guard (Claude)

Na każdym hoście blokuje narzędzia zdalne (`mcp__claude-code-remote__*`), gdy wywołuje je subagent. Powód: dialog zaufania zatrzymywał noc `/kit-ai:night-run`, a `archive_session` mógł zniszczyć sesję. Sesja główna nie jest objęta tą regułą.

## linters-guard (Claude)

Po `Edit` i `Write` uruchamia formatowanie i lint edytowanego pliku: ruff, prettier, eslint, shellcheck, hadolint, yamllint. Działa tylko wtedy, gdy repo ma konfigurację danego narzędzia. Wynik wraca do modelu jako dodatkowy kontekst. **Nigdy nie blokuje.**

## rtk-check (Claude)

Przy starcie sesji sprawdza, czy `rtk` jest w PATH i czy działa jego hook. Gdy nie, wypisuje instrukcję `rtk init -g --auto-patch`. Kit nie zmienia nic w `~/.claude`.

## retro-session-end (Claude)

Po zakończeniu sesji uruchamia `kit-ai retro scan --session <id>`, który zapisuje wpisy do cache. Zawsze kończy się kodem 0 i nie blokuje zamknięcia sesji. Zob. [Retro](../diagnostyka/retro.md).

## kit-doctor-reminder

Przy starcie sesji przypomina o otwartej partii doctora. `kit-ai reload` zapisuje zgłoszenia do `.ai/.kit-doctor.json`. Dopóki plik istnieje, agent dostaje raz na sesję jedną linię z poleceniem trybu C. Bez pliku jest cisza. Zob. [Doctor](../diagnostyka/doctor.md).

## host-profile (moduł współdzielony)

Wspólna detekcja hosta `vps` albo `local` dla hooków JS. Używa jej server-guard i language-reminder. Test pilnuje, że wynik jest taki sam jak w Pythonie. Hook nie wywołuje `kit-ai host`. Zob. [Profil hosta](../hosty/profil-hosta.md).

## Hooki poza Claude

- **Copilot**: `rtk-rewrite.json` przepisuje komendy na `rtk …`. `kit-guards.json` uruchamia git-guard, server-guard i sensitive-files-guard.
- **Antigravity**: `.agents/hooks.json` z nazwanym hookiem `kit-guards`. Plik jest wspólny z użytkownikiem, więc kit scala tylko swój klucz.
- **Codex**: `.codex/hooks.json`. Bootstrap nadpisuje ten plik, więc własne wpisy dopisz po każdym reloadzie.
- **OpenCode**: plugin `.opencode/plugins/kit-guards.js`. Awaria guarda albo timeout 10 sekund oznacza `deny`.

## Antigravity: szczegóły

| Klient | Wywołanie | Kontrakt |
|---|---|---|
| Antigravity | `node -e "<launcher>" <guard>.mjs --to antigravity` | launcher szuka `hooks/invoke-hook.js` albo `.agents/hooks/invoke-hook.js` od katalogu roboczego w górę. Brak pliku daje `deny` z powodem. Wyjście: `{ decision, reason }` |

Komenda hooka startuje z katalogu zależnego od hosta (w worktree T3 i adapterze ACP nie musi to być `.agents/`), dlatego launcher szuka adaptera sam. W worktree `.agents/hooks*` musi istnieć: przy zacommitowanych hookach robi to git, w pozostałych repo `worktree.copy` z Profilu.

Matchery w `.agents/hooks.json` (nazwany hook `kit-guards`, PreToolUse):

| Matcher | Guardy |
|---|---|
| `run_command` | git-guard i server-guard (bez sensitive-files-guard, zob. niżej) |
| `call_mcp_tool\|^mcp_` | server-guard |
| `^(view_file\|write_to_file\|replace_file_content\|multi_replace_file_content\|edit_file)$` | sensitive-files-guard |

Adapter sprowadza narzędzia runtime do nazw, które znają guardy. Brak pola, którego guard potrzebuje, daje `deny`. Sprawdzone na `agy` 1.3.0: `allow` nie omija polityki uprawnień Antigravity, a `deny` działa też z `--dangerously-skip-permissions`.

**Znana luka: komendy powłoki.** `run_command` nie przechodzi przez sensitive-files-guard, więc odczyt sekretu komendą powłoki (np. `cat .env`) **nie jest blokowany** w Antigravity. To świadomy zakres: sensitive-files-guard pilnuje w Antigravity tylko narzędzi plikowych. Pozostali klienci blokują też oczywisty odczyt sekretu przez Bash.

Znana luka: `grep_search`, `find_by_name` i `list_dir` nie są mapowane, więc sensitive-files-guard ich nie widzi. Tak samo `view_file_outline` i `view_code_item`, których argumentów nie dało się podejrzeć w `agy` 1.3.0. Matcher plikowy jest zakotwiczony `^(...)$`, więc ich nie łapie.
