
# Git i Pull Request (elegancki flow)

Cel: chronione `main` / `master` / `dev` + jasny podział **kto co robi** (kit ≠ Matt ≠ Superpowers ≠ Autopilot).

## Kto za co odpowiada

| Warstwa | Narzędzie | Robi | Nie robi |
|---------|-----------|------|----------|
| **Kit** | `@KIT_CMD_PREFIX@git-start`, `@KIT_CMD_PREFIX@git-check`, `@KIT_CMD_PREFIX@git-commit`, `@KIT_CMD_PREFIX@git-end`, ta reguła | Issue + sync + commit(y) + push/PR + metoda Managed Worktree + `Closes #N` | Decyzji o izolacji (worktree opcjonalny), pętli CI |
| **Matt** | `/grill-me`, `/tdd` | Scope, TDD feature | Gita / PR |
| **Superpowers** | `using-git-worktrees`, `finishing-a-development-branch` | Izolacja worktree; domknięcie (testy lokalne → opcje merge/PR) | Konwencji `feat/N-slug` (to kit) |
| **Autopilot** | skill Autopilot (Cursor) | Po PR: konflikty → komentarze → CI red → fix → push, aż merge-ready | Merge bez Ciebie; force na chronione |

Nie dubluj: **jeden** TDD path (Matt *albo* Superpowers TDD). Git nazewnictwa zawsze z **kita**.

## Kanoniczny flow (zalecany)

```text
[/grill-me tylko gdy scope niejasny]  →  @KIT_CMD_PREFIX@git-start  →  [worktree opcjonalnie]
        →  implementacja [+/tdd]
        →  [@KIT_CMD_PREFIX@git-check] → @KIT_CMD_PREFIX@git-commit
        →  @KIT_CMD_PREFIX@review-bugbot  (+ minimalny @KIT_CMD_PREFIX@review-* stack — nie wszystkie)
        →  @KIT_CMD_PREFIX@git-end   LUB   Superpowers finishing → „Push and create PR”
        →  Autopilot (CI/komentarze na PR)
        →  merge gdy green (Ty / gh — nie Autopilot sam)
```

**`/grill-me`:** tylko przy niejasnym scope / trade-offach. Oczywisty fix → pomiń.

**Review przed pushem:** zawsze Bugbot; + `@KIT_CMD_PREFIX@review-backend` i/lub `@KIT_CMD_PREFIX@review-frontend` wg diffu; `@KIT_CMD_PREFIX@review-edge|ui|architecture|tests` tylko gdy potrzeba (zob. `code-review`).

**Krótka ścieżka** (mały fix, bez izolacji):  
`@KIT_CMD_PREFIX@git-start` → kod → `@KIT_CMD_PREFIX@git-commit` → `@KIT_CMD_PREFIX@review-bugbot` → `@KIT_CMD_PREFIX@git-end` → (opc.) Autopilot.

**Długa / równoległa** (kolega-style):  
`@KIT_CMD_PREFIX@git-start` (ustala `feat/N-slug`) → Superpowers **worktree** na tym branchu → kod → `@KIT_CMD_PREFIX@git-commit` → finishing lub `@KIT_CMD_PREFIX@git-end` → **Autopilot**.

## Slash kit

| Komenda | Rola |
|---------|------|
| `@KIT_CMD_PREFIX@git-start` | `#N` / opis / **puste = auto-diff** / **`--help`** → issue + branch |
| `@KIT_CMD_PREFIX@git-check` | Dopasuj tytuł/body issue do realnego diffa; **`--dry-run`** / **`--help`** |
| `@KIT_CMD_PREFIX@git-commit` | Conventional Commit(s) z lokalnego diffa; **`--one`** / **`--split`** / **`--dry-run`** |
| `@KIT_CMD_PREFIX@git-end` | Push + PR (`Closes #N`); **`--help`**; alias `git-pr` |

Tytuły issue/PR/branch: **zawsze EN**. Body / commity / docstringi: język MCP (`get_language`, `--language pl|en`).

```text
@KIT_CMD_PREFIX@git-start feat add cart coupon
@KIT_CMD_PREFIX@git-start fix #108 login crash
@KIT_CMD_PREFIX@git-check
@KIT_CMD_PREFIX@git-commit
@KIT_CMD_PREFIX@git-end
```

## Superpowers — kiedy i jak

### Managed Worktree (`.ai/worktree.mjs`)

Izolacja jest opcjonalna (kit nie decyduje za Ciebie). Użyj gdy: drugi temat równolegle, brudny główny checkout, Cloud/best-of-n, procedura `@KIT_CMD_PREFIX@headless` lub `@KIT_CMD_PREFIX@night-run`, chcesz izolacji jak u „kolegi”.

Każdy worktree agenta lub procedury kita to Managed Worktree zbudowany metodą kita:
1. Najpierw **`@KIT_CMD_PREFIX@git-start`** (albo już masz branch `feat/N-…`) — konwencja nazwy zawsze z kita.  
2. Utworzenie: preferuj `node .ai/worktree.mjs add [<ścieżka>] <branch>` (albo `add <ścieżka> --detach <ref>`) — nie gołym `git worktree add`. Skrypt przenosi pliki z `.gitignore` (w tym konfiguracje MCP, `.env`) i konfiguruje zależności (overlay venv).  
   Jeśli worktree powstało poza tą komendą (narzędzie natywne klienta, Superpowers `using-git-worktrees`, człowiek), **od razu po utworzeniu** wykonaj: `node .ai/worktree.mjs sync [<ścieżka>]`.  
3. Koduj w worktree.
4. Po merge PR (albo przy porzuceniu) usuń worktree: `node .ai/worktree.mjs remove <ścieżka>`.

**Nie** wymagaj worktree na każdym drobnym PR.

### Finishing (`finishing-a-development-branch`)

Gdy implementacja + **lokalne testy** OK: skill pyta merge / **PR** / zostaw / discard.

- Wybór **PR** ≈ `@KIT_CMD_PREFIX@git-end` (push + create). Preferuj tytuł/`Closes #N` zgodne z konwencją kita.  
- Jeśli finishing już zrobił PR — **nie** odpalaj drugiego `@KIT_CMD_PREFIX@git-end`; idź w Autopilot.

## Autopilot — pętla po PR

Gdy PR istnieje i CI/review blokuje merge:

1. Odśwież stan (`gh pr view`, `gh pr checks`).  
2. Konflikty → komentarze (Bugbot itd.) → CI — w tej kolejności.  
3. Fix → push na **feature branch** (nie force na main/dev).  
4. Nie merge’uj sam; zgłoś „merge-ready”.

Wywołanie: skill Autopilot / „doprowadź ten PR do green”.

## Kolejność — mity

| Mit | Prawda |
|-----|--------|
| PR przed pushem | Najpierw push, potem PR |
| Worktree = obowiązek | Izolacja opcjonalna; każdy worktree agenta lub procedury kita to Managed Worktree (add / sync / remove) |
| `@KIT_CMD_PREFIX@git-start` = cały pipeline | Tylko issue + branch |
| Autopilot = Matt | Autopilot = CI/PR loop; Matt = proces feature |

## Chronione branche

`main`, `master`, `dev` — tylko przez PR. Baza: linia `base: <gałąź>` w `.ai/project.md`; bez niej `dev` tylko gdy nie jest w tyle za
default branchem, inaczej default branch (blok w `@KIT_CMD_PREFIX@git-start`).

## Nazewnictwo

- z issue: `<typ>/<N>-<slug>` → `feat/42-add-cart-coupon`  
- bez: `<typ>/<slug>` → `chore/bump-ruff`  

Typy: `feat`, `fix`, `hotfix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`, `style`, `build`, `release`.  
Unikaj: `feature/`, `bugfix/`.

Ręcznie: `gh issue develop N --name feat/N-slug --base dev --checkout`.

## Zasady twarde

1. Chroniona gałąź + praca → `@KIT_CMD_PREFIX@git-start` zanim edycje.  
2. Jeden temat = jeden branch = jeden PR.  
3. Przed pierwszym pushem: `@KIT_CMD_PREFIX@review-bugbot` (+ minimalny stack review).  
4. Merge tylko przy green CI + required reviews.  
5. Autopilot / finishing respektują chronione branche (zero force na main/dev).  
6. Nie `--no-verify` bez powodu.  
7. Niska pewność (auth/billing/ACL/migracje) → agent **pyta**, nie zgaduje.

## Definition of Done

- [ ] Branch zgodny z konwencją (+ issue gdy jest)  
- [ ] Zmiany zacommitowane (`@KIT_CMD_PREFIX@git-commit` gdy trzeba)  
- [ ] Review lokalny przed pushem  
- [ ] PR otwarty (`@KIT_CMD_PREFIX@git-end` lub finishing)  
- [ ] CI + komentarze ogarnięte (Autopilot gdy trzeba)  
- [ ] Merge przez PR — nie bezpośredni push na bazę
