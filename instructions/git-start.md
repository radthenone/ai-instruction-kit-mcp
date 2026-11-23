# `@KIT_CMD_PREFIX@git-start` — issue + branch + checkout

> Prywatne notatki z użycia. Źródło: `.claude/commands/git-start.md`.
> Część osi czasu: [git-start](git-start.md) → kod → [git-commit](git-commit.md) →
> [[git-check]](git-check.md) → `@KIT_CMD_PREFIX@review-*` → [git-end](git-end.md).

**Robi:** typ → issue (opcjonalnie) → branch `typ/N-slug` → checkout.
**Nie robi:** commita, pusha, PR-a. Nie implementuje feature'a.

| Wywołanie | Co się dzieje |
|---|---|
| `@KIT_CMD_PREFIX@git-start` | auto-diff: z lokalnych zmian zgaduje typ, tytuł, robi issue i branch |
| `@KIT_CMD_PREFIX@git-start feat add cart coupon` | nowe issue + `feat/<N>-add-cart-coupon` |
| `@KIT_CMD_PREFIX@git-start fix #108 login crash` | bierze istniejące #108, robi branch |
| `@KIT_CMD_PREFIX@git-start chore no-issue bump-ruff` | branch bez issue |
| `@KIT_CMD_PREFIX@git-start --help` | pomoc |

**Ręcznie, gdyby `gh` nie działał:**

```bash
gh issue create --title "Add cart coupon" --body "## Summary ..."
gh issue develop 42 --name feat/42-add-cart-coupon --base dev --checkout
# brudne drzewo → zamiast issue develop:
git checkout --no-track -b feat/42-add-cart-coupon origin/dev
```

`--no-track`, bo inaczej branch śledzi `origin/dev` i Sync w IDE wypycha go prosto na `dev`.

**Do zapamiętania:**

- **Tytuł issue i nazwa brancha zawsze EN.** Body issue w języku z MCP (u mnie PL).
- Baza: `dev` jeśli istnieje na remote, inaczej `main`/`master`. W tym repo to
  **`master`** — `dev` nie ma.
- Zapisuje `branch.<nazwa>.startedFrom` w configu gita. Dzięki temu `@KIT_CMD_PREFIX@git-end`
  wie, dokąd wrócić po pushu. Branch stworzony ręcznie tego nie ma — wtedy
  `@KIT_CMD_PREFIX@git-end` zostawi mnie na feature branchu.

**Pułapka:** `@KIT_CMD_PREFIX@git-commit` przed `@KIT_CMD_PREFIX@git-start`. Jestem na `master`, robię zmiany,
wołam `@KIT_CMD_PREFIX@git-commit` — STOP. Kolejność jest odwrotna: branch **przed** pracą.

**Pułapka:** liczenie na `dev`. W tym repo bazą jest `master`. Komendy same to
wykrywają, ale ręczne polecenia z pomocy mają `dev` w przykładach.
