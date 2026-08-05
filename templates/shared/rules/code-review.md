# Code review

Przed `git push` na branch z featurem — **minimalny zestaw**, nie wszystkie `/review-*`:

| Zmiana | Minimum przed pushem |
|--------|----------------------|
| Drobna (1–2 pliki, bez API/auth) | `/review-bugbot` |
| Backend | `/review-bugbot` + `/review-backend` |
| Frontend | `/review-bugbot` + `/review-frontend` |
| API + UI | Bugbot + BE + FE **albo** para `/subagent-*` (nie oba naraz pełne) |
| Auth / ACL / płatności | `/review-security` (+ Bugbot) |
| Duży refactor / brzegi | + `/review-edge` (opcjonalnie) |
| „Zrobione, działa” | + `/review-tests` (dowód komend, nie styl) |
| Architektura / monorepo layout | + `/review-architecture` gdy dotyczy |

**Nie** odpalaj całego wachlarza „na wszelki wypadek”.

Kolejność:

1. Minimalny zestaw jak wyżej.
2. Napraw `high` / uzasadnione `medium`.
3. Po pushu — Bugbot na GitHub (auto lub `cursor review`).

### Bugbot vs stack

- **Bugbot** — blocking, sekrety, bezpieczeństwo.
- **`/review-backend|frontend|…`** — konwencje domeny z MCP; bez dublowania Bugbota.

### Format findings (agenci stack)

`Severity | Location | Finding | Fix` — bez eseju.

### Orval

Gdy overlay ma `codegen: orval` (lub REST FE bez wpisu): po zmianie API regeneruj klienta i commituj. Przy `manual`/`none` nie wymagaj Orval.

Hooki:

- `gate-push.sh` — ask przed push (`SKIP_PUSH_REVIEW=1` świadomie).
- `gate-destructive.sh` — deny force na main/master/dev, `reset --hard`.

Reguły Bugbota: `.cursor/BUGBOT.md`. Workflow: MCP `get_bundle` → `devops` / `core:code-review`.
