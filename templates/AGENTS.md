# AGENTS.md

## Warstwy AI (nie mieszaj)

| Warstwa | Co | Gdzie | Po co |
|---------|-----|------|--------|
| **1. Fundament** | instruction-kit MCP `project-guides` | `.cursor/mcp.json` (`--preset` + `--workspace`), `.ai/project.md`, `.cursor/agents` | Stack, bundles, overlay, `/review-*` |
| **2. Proces** | [mattpocock/skills](https://github.com/mattpocock/skills) | skills w repo lub globalnie (`npx skills add`) | `/grill-me`, `/tdd`, PRD — *zanim* i *jak* budujesz |
| **3. Meta** | superpowers (i podobne) | user / plugin Cursor | brainstorm, debug, finishing branch |

Instruction-kit = prawda o **Waszym** stacku. Matt = bramki procesu. Superpowers = sposób prowadzenia sesji — **nie** zamiennik kita.

## Instruction-kit (MCP)

Przed pracą nad kodem:

| Obszar | Akcja |
|--------|-------|
| Backend | MCP `get_bundle` → `backend` |
| Frontend | MCP `get_bundle` → `frontend` |
| Architektura / infra | MCP `get_bundle` → `architecture` |
| Unikalne dla repo | MCP `get_overlay` lub `.ai/project.md` |
| Docs bibliotek | Context7 (globalnie) |

Wybór modułów: `--preset` w `.cursor/mcp.json` (`_base` albo preset produktu, np. `olivin-app`).  
Lokalny `.ai/project.profile.yaml` **tylko** przy forku (nadpisania capabilities/decisions).

## Priorytet źródeł

1. Polecenie użytkownika  
2. `.ai/project.md` (overlay) + bundle MCP  
3. `/review-*` / hooki przed pushem  
4. Matt (`/grill-me`, `/tdd`…) — proces feature  
5. Superpowers — gdy skill sam pasuje (brainstorm / debug / finishing)  
6. Ten plik  

Konflikt TDD: na feature używaj **albo** Matt `/tdd`, **albo** superpowers TDD — nie obu naraz. Domyślnie: Matt na nowe feature’e; Superpowers na debug / domykanie brancha.

## Flow jednej zmiany

1. (Opcjonalnie) `/grill-me` — doprecyzuj scope  
2. MCP `get_bundle` + `get_overlay` — reguły stacku  
3. Implementacja (+ opcjonalnie `/tdd`)  
4. `/review-backend` lub `/review-frontend`  
5. `/review-bugbot` → push  

## Język

Odpowiedzi po polsku. Kod po angielsku. Docstringi po polsku.

## Slash commands

| Prefiks | Przykłady | Źródło |
|---------|-----------|--------|
| `/review-*` | `/review-backend`, `/review-bugbot` | kit + Cursor |
| `/subagent-*` | `/subagent-backend` | kit |
| `/grill-me`, `/tdd`, … | proces | mattpocock (jeśli zainstalowane) |

## Code review

Przed `git push`: `/review-bugbot` (auth/płatności: `/review-security`).  
Hooki: `gate-push.sh` (ask), `gate-destructive.sh` (deny force na main / reset --hard).  
Bootstrap: `scripts/bootstrap-project.sh`.
