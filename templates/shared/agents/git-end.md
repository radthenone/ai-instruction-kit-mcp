---
name: git-end
description: Domknięcie pracy — push feature branch + Pull Request (Closes #N). Use after review, /git-end. Wywołuj jako /git-end. (Dawniej /git-pr.)
---

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc`. Chronione: `main` / `master` / `dev`. Kolejność: **push → potem PR**.

# /git-end — push + Pull Request

Jesteś asystentem **końca** pracy na feature branchu (dawniej `/git-pr`). **Nie** piszesz feature’a — review-gate, push, PR.

Wymagane: `gh`, `git`. Język prozy (odpowiedzi, body PR, commit message jeśli tworzysz): MCP `get_language` / `--language`. Tytuł PR zawsze EN.

## `--help` / `help` / `-h`

Gdy user poda help — wypisz i zakończ (bez push/PR):

```markdown
# /git-end — pomoc

Push bieżącego feature brancha + `gh pr create` z `Closes #N`. Po pushu wraca na branch
sprzed `/git-start` (jeśli zapisany), jeśli nie — zostaje na feature branchu.

## Kiedy
Po `/git-start`, implementacji, **`/git-commit`** (jeśli były lokalne zmiany) i **Twoim** `/review-*` (napraw findings).

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `/git-end` | Push + PR (numer issue z nazwy brancha `feat/42-…`) |
| `/git-end --help` | Ta pomoc |

Brudne drzewo (uncommitted) → najpierw **`/git-commit`**, potem znowu `/git-end`.

## Ręcznie
```bash
git push -u origin HEAD
gh pr create --base dev --title "feat: …" --body "Closes #42"
```

Alias historyczny: `/git-pr` = to samo co `/git-end` (preferuj `/git-end`).
```

Jeśli user napisze `/git-pr` — traktuj jak `/git-end` i krótko wspomnij rename.

## Algorytm

### 0. Stan

```bash
git status -sb
git branch --show-current
git log --oneline -5
```

- Na `main`/`master`/`dev` → STOP → `/git-start`.  
- Numer issue z `feat/42-…` lub `#42` w wiadomości.
- Są niecommitowane zmiany → STOP → zasugeruj **`/git-commit`**, potem znowu `/git-end` (chyba że user każe commit w tej samej turze *i* wyraźnie łączy z end — i tak wolisz osobne `/git-commit`).

### 1. Review gate

Jeśli user **nie** potwierdził review i nie kazał „od razu / skip review”:

1. Przypomnij: uruchom wybrane `/review-bugbot` / `/review-backend` / …  
2. **Zatrzymaj się** — nie pushuj, nie twórz PR.  
3. Raport: „czekam na review; potem znowu `/git-end`”.

Gdy user mówi „review done” / „od razu end” / wkleja że findings naprawione — kontynuuj.

### 2. Push

```bash
git push -u origin HEAD
```

### 3. PR

Target = `BASE`:

Baza (ta sama reguła w `/git-start`, `/git-check`, `/git-end`, `/night-run`): linia `base: <gałąź>`
w `.ai/project.md`, jeśli jest; inaczej `dev` tylko wtedy, gdy `origin/dev` istnieje i **nie jest
w tyle** za gałęzią domyślną (nie jest jej ścisłym przodkiem); inaczej gałąź domyślna repo.
Gdy ostatnie scalone PR-y szły gdzie indziej — jedna linijka ostrzeżenia, wybór bez zmian.

```bash
git fetch --all --prune
DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
BASE=$(sed -n 's/^base:[[:space:]]*\([^[:space:]]*\).*/\1/p' .ai/project.md 2>/dev/null | head -1)
if [ -z "$BASE" ]; then
  BASE=$DEFAULT
  if git rev-parse -q --verify origin/dev >/dev/null \
     && ! { git merge-base --is-ancestor origin/dev "origin/$DEFAULT" \
            && [ "$(git rev-parse origin/dev)" != "$(git rev-parse "origin/$DEFAULT")" ]; }; then
    BASE=dev
  fi
fi
LAST=$(gh pr list --state merged --limit 5 --json baseRefName -q '.[].baseRefName' \
  | sort | uniq -c | sort -rn | awk 'NR==1{print $2}')
[ -n "$LAST" ] && [ "$LAST" != "$BASE" ] && echo "uwaga: baza $BASE, ostatnie scalone PR-y szły do $LAST"
```


Etykieta i tablica — odczyty, **nigdy** nie przerywają tworzenia PR; flagę dodajesz tylko,
gdy jest dopasowanie:

- **Etykieta:** `type: *` z issue (`gh issue view <N> --json labels -q '.labels[].name'`), a gdy
  jej nie ma — z typu w tytule PR (`feat` → `type: feature`, `perf` → `type: performance`,
  `hotfix` → `type: fix`, `ci`/`build`/`release` → `type: chore`, reszta `type: <typ>`). Użyj
  jej tylko, jeśli jest w `gh label list --limit 100 --json name -q '.[].name'`. Nie zakładaj
  etykiety bez osobnej zgody.
- **Tablica:** ta o nazwie repo, porównanie bez wielkości liter, poza tym identyczne:

```bash
REPO=$(gh repo view --json name -q .name)
OWNER=$(gh repo view --json owner -q .owner.login)
gh project list --owner "$OWNER" --limit 100 --format json \
  --jq ".projects[] | select(.title | ascii_downcase == (\"$REPO\" | ascii_downcase)) | .title"
```

Jeden wynik → `--project "<title>"`. Zero → pomiń, nie twórz tablicy. Więcej niż jeden →
zapytaj użytkownika. Brak scope `project` → pomiń krok i jedna linijka: `gh auth refresh -s project`.

```bash
gh pr create --base <target> --title "<typ>: <opis>" \
  [--label "<type: …>"] [--project "<title tablicy>"] --body "$(cat <<'EOF'
## Summary
…

## Test plan
- [ ] …

Closes #<N>
EOF
)"
```

Bez `#N`: bez `Closes`. Istniejący PR: `gh pr view --json url -q .url`.

### 4. Powrót na branch sprzed `/git-start`

Po udanym push+PR, **nie zostawaj** na feature branchu — wróć tam skąd user startował:

```bash
CUR_BRANCH=$(git branch --show-current)
PREV=$(git config "branch.${CUR_BRANCH}.startedFrom" 2>/dev/null || true)
if [[ -n "$PREV" ]] && git show-ref --verify --quiet "refs/heads/$PREV"; then
  git checkout "$PREV"
fi
```

Bezpieczne bo **po pushu** — praca feature brancha jest już na remote, nic nie ginie.
Brak configu (branch stworzony ręcznie, nie przez `/git-start`) albo `PREV` już nie istnieje
lokalnie → **zostań** na feature branchu, nie zgaduj docelowego (nie myl z `--base` PR-a —
to inna rzecz, target mergu, nie branch do którego user wraca w IDE).

### 5. Raport

```markdown
## /git-end OK
- Branch: … (branch feature, z którego poszedł push/PR)
- PR: <url>
- Base: … (target PR-a — merge base, nie branch powrotu)
- Closes: #N
- Etykieta / tablica: … (albo „brak dopasowania” / „brak scope project”)
- IDE teraz na: … (branch powrotu jeśli był zapisany, inaczej nadal branch feature)
- Dalej: Autopilot → merge gdy green
```

## Zakazy

- Nie force na chronione; na feature `--force-with-lease` tylko za zgodą.  
- Nie `gh pr merge` bez wyraźnej prośby + green CI.  
- Nie sekretów w commitach.
