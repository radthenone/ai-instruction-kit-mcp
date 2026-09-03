# `/git-end` — push + PR (dawniej `/git-pr`)

> Prywatne notatki z użycia. Źródło: `.claude/commands/git-end.md`.
> Część osi czasu: [git-start](git-start.md) → kod → [git-commit](git-commit.md) →
> [[git-check]](git-check.md) → `/review-*` → `/git-end`.

**Robi:** bramka review → `git push -u origin HEAD` → `gh pr create` z
`Closes #N` → **powrót na branch sprzed `/git-start`**.
**Nie robi:** nie pisze feature'a, nie mergeuje.

**Kolejność jest sztywna: push → dopiero potem PR.**

**Bramka review.** Jeśli nie potwierdzę, że review był, **zatrzymuje się** —
nie pushuje. Odblokowuje to: „review done", „od razu end", albo wklejenie, że
findingi naprawione.

**Brudne drzewo → STOP** i odesłanie do [git-commit](git-commit.md). Potem znowu `/git-end`.

**Ręcznie:**

```bash
git push -u origin HEAD
gh pr create --base master --title "feat: ..." --body "Closes #42"
```

**Do zapamiętania:**

- Po pushu wraca na branch, z którego startowałem (`branch.<n>.startedFrom`).
  Bezpieczne, bo praca jest już na remote. Brak configu → zostaje na feature.
- **Dwie różne rzeczy, których nie wolno mylić:** `--base` PR-a to target
  mergu; branch powrotu to to, na czym zostaje moje IDE.
- `/git-pr` to alias historyczny — działa, ale wolę `/git-end`.
- `gh pr merge` **nie** odpali bez mojej wyraźnej prośby i zielonego CI.

**Pułapka:** `/git-end` z brudnym drzewem. Nie pushuje. To nie jest błąd, to bramka.
