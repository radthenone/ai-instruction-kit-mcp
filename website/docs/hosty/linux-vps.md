# Linux (serwer VPS)

Na VPS agent pracuje w **trybie lekkim**. Mały serwer (np. 1 vCPU, 4,5 GB RAM, bez swapu, LXC) nie zniesie `docker compose up`, dev serwera ani e2e obok działającej usługi. Reguły wynikają z profilu hosta, a twardą blokadę zapewnia server guard.

## Instalacja

Te same komendy co na Windows, w `bash`:

```bash title="bash"
uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
cd ~/projects/moja-appka
kit-ai install
```

Wymagania są takie same: `uv`, `git`, `bash`, `node`, `python3`.

## Profil hosta

VPS wykrywany jest automatycznie: Linux, bez CI, bez WSL, z małymi zasobami. Sprawdź `kit-ai host`, który wypisze `vps` albo `local`.

Gdy heurystyka się pomyli, wymuś profil **na tej maszynie**:

Na VPS, którego heurystyka nie rozpoznała:

```bash title="~/.profile albo ~/.bashrc (VPS)"
export KIT_HOST_PROFILE=vps
```

Na PC, który heurystyka uznała za VPS:

```bash title="~/.profile albo ~/.bashrc (PC)"
export KIT_HOST_PROFILE=local
```

Ustaw tylko jedną z tych wartości. Druga linia nadpisałaby pierwszą.

Nie wpisuj tego do repo. Profil w repo jest wspólny dla wszystkich maszyn.

## Co się zmienia na VPS

- `get_bundle` dokleja `infra:vps-lightweight` do każdego bundla.
- Server guard jest aktywny. Zob. [Server guard](server-guard.md).
- Reload zapisuje `env.UV_NO_SYNC="1"` do `.claude/settings.local.json`, ale tylko na hoście VPS. Komendy `uv run` bez `--no-sync` wtedy przechodzą tylko w tym trybie.
- OpenCode nie ma pliku env per maszyna. Zmienną `UV_NO_SYNC=1` ustaw w powłoce serwera, np. w `~/.profile`.

## Co wolno, a czego nie

| Wolno | Nie wolno |
|---|---|
| edycja, git, lint, typecheck | `docker`, `podman` |
| testy jednostkowe | instalacja paczek: `uv sync`, `npm install`, `pip install` |
| `tsc --noEmit`, `turbo run lint` | buildy: `next build`, `vite build` |
| `uv lock --no-build`, `npm install --package-lock-only --ignore-scripts` | `npx` i `uvx` pobierające z sieci |
| | e2e: `playwright`, `cypress`, `maestro` |

Pełna weryfikacja (kontenery, migracje, integracje, e2e, build) należy do CI. Na VPS przechodzą szybkie bramki: lint, typecheck i testy jednostkowe.

## Worktree na VPS

Worktree tworzysz tak samo: `node .ai/worktree.mjs add …`. Pole `setup:` przechodzi przez server guard, więc niebezpieczne komendy są pomijane. Zob. [Managed Worktree](../koncepcja/managed-worktree.md).

## Zalecenia dla hosta

Guard tekstowy nie złapie wszystkiego. Agent może napisać własny skrypt i go uruchomić. Dlatego po stronie hosta:

- wyłącz plugin Playwright MCP na serwerze. Guard blokuje narzędzia, ale proces MCP i tak startuje,
- użytkownik agenta nie należy do grupy `docker` i nie ma sudo bez hasła,
- ustaw limit pamięci na sesję agenta, jeśli host na to pozwala.

## Night-run na VPS

Kroki odrzucone przez guard idą jako „tylko CI”. Brak checków CI oznacza brak merge. Zob. [Praca nocna i headless](../komendy/praca-nocna-i-headless.md).
