# Code review

Przed `git push` na branch z featurem — **minimalny zestaw**, nie wszystkie `@KIT_CMD_PREFIX@review-*`:

| Zmiana | Minimum przed pushem |
|--------|----------------------|
| Drobna (1–2 pliki, bez API/auth) | `@KIT_CMD_PREFIX@review-bugbot` |
| Backend | `@KIT_CMD_PREFIX@review-bugbot` + `@KIT_CMD_PREFIX@review-backend` |
| Frontend | `@KIT_CMD_PREFIX@review-bugbot` + `@KIT_CMD_PREFIX@review-frontend` |
| API + UI | Bugbot + BE + FE **albo** para `@KIT_CMD_PREFIX@subagent-*` (nie oba naraz pełne) |
| Auth / ACL / płatności | `@KIT_CMD_PREFIX@review-security` (+ Bugbot) |
| Duży refactor / brzegi | + `@KIT_CMD_PREFIX@review-edge` (opcjonalnie) |
| „Zrobione, działa” | + `@KIT_CMD_PREFIX@review-tests` (dowód komend, nie styl) |
| Architektura / monorepo layout | + `@KIT_CMD_PREFIX@review-architecture` gdy dotyczy |

**Nie** odpalaj całego wachlarza „na wszelki wypadek”.

Kolejność:

1. Minimalny zestaw jak wyżej.
2. Napraw `high` / uzasadnione `medium`.
3. Po pushu — Bugbot na GitHub (auto lub `cursor review`).

### Bugbot vs stack

- **Bugbot** — blocking, sekrety, bezpieczeństwo.
- **`@KIT_CMD_PREFIX@review-backend|frontend|…`** — konwencje domeny z MCP; bez dublowania Bugbota.

### Format findings (agenci stack)

`Severity | Location | Finding | Fix` — bez eseju.

### Orval

Gdy profil ma `codegen: orval` (MCP `get_codegen`; bez pary backend + klient efektywny to `none`): po zmianie API regeneruj klienta i commituj. Przy `manual`/`none` nie wymagaj Orval.

Guardy (allow/deny, nigdy ask — ADR 0006):

- `git-guard.mjs` — deny force i push na main/master/dev, `reset --hard`, `clean -f`, `branch -D`, `checkout .`.
- `sensitive-files-guard.mjs` — deny odczyt/zapis sekretów, deny ręczna edycja lockfile.

Reguły Bugbota: `.cursor/BUGBOT.md`. Workflow: MCP `get_bundle` → `devops` / `core:code-review`.
