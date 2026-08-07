---
description: Domknięcie pracy — push feature branch + Pull Request (Closes #N). Use after review, /git-end. Wywołuj jako /git-end. (Dawniej /git-pr.)
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc`. Chronione: `main` / `master` / `dev`. Kolejność: **push → potem PR**.

# /git-end — push + Pull Request

Jesteś asystentem **końca** pracy na feature branchu (dawniej `/git-pr`). **Nie** piszesz feature’a — review-gate, push, PR.

Wymagane: `gh`, `git`. Język prozy (odpowiedzi, body PR, commit message jeśli tworzysz): MCP `get_language` / `--language`. Tytuł PR zawsze EN.

## `--help` / `help` / `-h`

Gdy user poda help — wypisz i zakończ (bez push/PR):

```markdown
# /git-end — pomoc

Push bieżącego feature brancha + `gh pr create` z `Closes #N`.

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

Target: `dev` jeśli na remote, inaczej default (`main`/`master`).

```bash
gh pr create --base <target> --title "<typ>: <opis>" --body "$(cat <<'EOF'
## Summary
…

## Test plan
- [ ] …

Closes #<N>
EOF
)"
```

Bez `#N`: bez `Closes`. Istniejący PR: `gh pr view --json url -q .url`.

### 4. Raport

```markdown
## /git-end OK
- Branch: …
- PR: <url>
- Base: …
- Closes: #N
- Dalej: Autopilot → merge gdy green
```

## Zakazy

- Nie force na chronione; na feature `--force-with-lease` tylko za zgodą.  
- Nie `gh pr merge` bez wyraźnej prośby + green CI.  
- Nie sekretów w commitach.
