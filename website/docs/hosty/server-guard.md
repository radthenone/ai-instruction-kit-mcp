# Server guard

Server guard to twardy hook, który na **VPS** odrzuca tylko komendy mogące zawiesić serwer albo uderzyć w inne usługi na nim. Reszta pracy przechodzi: edycja, git, lint, typecheck, testy.

Powstał po incydencie z 2026-10-15: restart VPS po `uv run` bez `--no-sync`. Sama reguła tekstowa nie wystarczała, bo subagent nocny nie czyta overlayu tak uważnie jak sesja interaktywna ([ADR-0009](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0009-server-guard-denies-heavy-commands-on-vps.md)).

## Kiedy jest aktywny

Decyzja zapada w momencie wywołania, nie przy instalacji. Profil i `.claude/settings.json` są wspólne dla PC i VPS, więc guard jest ten sam, a działa różnie zależnie od hosta.

Kolejność decyzji:

1. `server.guard: off` w Profilu daje allow.
2. Zmienna `KIT_HOST_PROFILE` wymusza `vps` albo `local`.
3. Heurystyka hosta: Linux, bez CI, bez WSL, CPU ≤ 2, RAM ≤ 8 GB, swap 0, wirtualizacja albo brak desktopu. Wtedy guard jest aktywny.
4. W pozostałych przypadkach: allow.

Aktywny jest na małym linuksowym VPS albo kontenerze serwerowym. Nieaktywny na Windows (Git Bash, PowerShell), macOS, WSL, Codespaces, devcontainerze i w CI. Nic nie ustawia się per projekt.

## Domyślne deny kita

Precedencja: `server.allow` > `server.deny` > allow kita > deny kita.

| Kategoria | Deny | Dozwolone świadomie | Dlaczego i alternatywa |
|---|---|---|---|
| Kontenery | `docker`, `docker compose`, `podman`, także `stop`, `rm`, `down`, `prune` | `ps`, `images`, `inspect`, `logs` bez `-f`, `version`, `info` | kontenery budujesz i uruchamiasz w CI, na hoście działają cudze |
| Paczki | `uv sync`, `uv add`, `uv lock`, `uv run` bez `--no-sync`, `pip install`, `npm install`, `pnpm install`, `yarn install`, `bun install` | `uv run --no-sync …`, `uv lock --no-build`, `npm install --package-lock-only --ignore-scripts` | instalacja kompiluje zależności natywne. Lockfile zmienia się na PC albo w CI |
| Inne ekosystemy | `cargo install`, `go install`, `apt install`, `corepack enable` | `cargo check` | instalacja na serwerze zmienia zależności |
| CLI instalujące paczki | `shadcn init`, `shadcn add`, `expo install` | | CLI samo dopisuje zależności |
| Buildy | `next build`, `vite build`, `webpack`, `cargo build`, `expo export`, `turbo run build` | `tsc --noEmit`, `turbo run lint`, `turbo run typecheck` | buildy produkcyjne tylko w CI |
| Launchery | `npx`, `bunx`, `pnpm dlx`, `yarn dlx`, `uvx` pobierające z sieci | `npx --no <bin>`, `bunx --no-install <bin>`, `uvx --offline …` | pobieranie z sieci na VPS |
| Przeglądarki i e2e | `playwright`, `cypress`, `maestro` | | przeglądarka to setki MB na instancję |
| Równoległość | `pytest -n`, `--numprocesses` | `pytest` bez xdist | xdist mnoży procesy na słabym CPU |

## Lockfile-only

Aktualizacja samego lockfile jest dozwolona, bo nic nie instaluje:

- `uv lock --no-build`,
- `uv add` albo `uv remove` z `<pkg> --no-sync --no-build`,
- `npm install --package-lock-only --ignore-scripts`,
- `pnpm install --lockfile-only --ignore-scripts`,
- `bun install`, `add`, `remove` z `--lockfile-only --ignore-scripts`.

`pnpm add` i Yarn pozostają zablokowane. Gdy paczka wymaga builda, ticket dostaje `needs-local` z komentarzem. Uwaga: `--no-build` w uv nie zatrzymuje budowania samego projektu.

## Obejścia, które guard też łapie

- każdy segment po `&&`, `||`, `;`, `|`, `&` osobno, także wewnątrz `bash -c` i `$( … )`,
- prefiksy `sudo`, `env`, `nice`, `timeout`, `nohup`, `xargs`, `eval` i ścieżkę binarki,
- launchery: `uv run X`, `npx X`, `python -m X`, `pnpm dlx X`.

Separatory w cudzysłowach i treść heredoca to dane, nie komendy. Body PR przekazane przez heredoc przechodzi.

## Wrappery: rtk, Taskfile, skrypty

Guard widzi tekst komendy, więc kit przed jej oceną zdejmuje `rtk`. `rtk next build` jest oceniane jak `next build`.

Przy `kit-ai reload` kit rozwija też zadania z `Taskfile.yml` i skrypty z `package.json`. Zadanie, którego komendy pasują do deny, dostaje deny z łańcuchem w powodzie, np. `bun run build → turbo run build → next build`. Po zmianie `Taskfile.yml` albo `package.json` uruchom `kit-ai reload`, bo guard działa na starej liście.

## Konfiguracja w Profilu

```yaml title=".ai/project.profile.yaml"
server:
  guard: auto        # auto (domyślnie) | off
  deny:              # dodatki projektu, których automat nie wykryje
    - "bunx eas-cli"
  allow:             # wyjątki projektu, wygrywają z deny projektu i listy kita
    - "task lints:backend:ruff:check"
```

Nie wyłączaj guarda przez `server.guard: off` w Profilu, jeśli repo trafia na VPS. Profil jest commitowany, więc wyłączyłbyś guard także na serwerze.

## Ręczne sprawdzenie

```bash title="bash"
echo '{"tool_input":{"command":"docker compose up"}}' | KIT_HOST_PROFILE=vps node .claude/hooks/server-guard.mjs
```

Wynik powinien być `deny`.

## Czego guard nie złapie

Agent może napisać własny skrypt i go uruchomić. Zalecenia dla hosta: [Linux VPS](linux-vps.md).
