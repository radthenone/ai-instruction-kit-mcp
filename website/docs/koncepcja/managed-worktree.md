# Managed Worktree

Zwykły `git worktree add` tworzy katalog bez plików, których nie ma w gicie: konfiguracji MCP, `.env`, zależności. Agent w takim worktree jest ślepy. **Managed Worktree** to worktree zsynchronizowane metodą kita. Przenosi to, czego potrzebuje, z głównego checkoutu.

## Komendy

```bash title="Git Bash · bash"
node .ai/worktree.mjs add ../moja-appka-feat --detach <commit>   # nowy worktree z synchronizacją
node .ai/worktree.mjs remove ../moja-appka-feat                   # sprzątanie
```

## Co jest przenoszone

Bez sekcji `worktree:` w Profilu skrypt kopiuje istniejące wpisy:

- pliki MCP i stampy kita (`.mcp.json`, `.codex/config.toml`, `.ai/.kit-bootstrap.json`, …),
- `.env`,
- `.claude/settings.local.json`.

## Konfiguracja w Profilu

```yaml title=".ai/project.profile.yaml (przykład)"
worktree:
  copy: [.env]                 # kopiowane z głównego checkoutu, bez nadpisywania istniejących
  link: [frontend/node_modules] # symlink do głównego checkoutu, tylko do odczytu
  setup: [task install:backend] # komendy po copy/link, sprawdzane przez server-guard
  venv: auto                    # auto | overlay | none
```

## Automatyczna synchronizacja

`kit-ai install` i `kit-ai reload` dopisują blok kita do hooka gita `post-checkout`. Każdy nowy worktree, także zakładany z terminala, Orci albo przez agenta, dostaje `copy`, `link` i overlay venv. Cudzy hook zostaje. Pole `setup:` uruchamia się tylko przy `node .ai/worktree.mjs add`.

## Python: overlay venv

Dla Pythona `venv: auto` tworzy lekki overlay na bazie głównego `.venv`. Ma ograniczenia:

- testy i komendy uruchamiaj przez `python -m …` albo `uv run --no-sync python -m …`. Overlay nie ma console scripts w `bin/`,
- metadane i entry pointy pochodzą z głównego venv.

## Zasady

- **Linkowane zależności są tylko do odczytu.** Postinstall w worktree zmieniłby środowisko głównego checkoutu.
- **Konfiguracje MCP w worktree wskazują główny checkout.** To zamierzone.
- **Guard serwerowy działa w worktree**, gdy projekt commituje pliki hooków kita (np. `.claude/hooks/`). Sprawdź: `git ls-files .claude/hooks`.

Metoda jest opisana w [ADR-0014](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0014-the-kit-owns-the-worktree-method-not-the-decision-to-isolate.md). Kit posiada metodę synchronizacji, a nie decyzję o izolacji. Czy użyć worktree, decydujesz ty albo Superpowers.
