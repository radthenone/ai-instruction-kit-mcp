---
description: Start pracy git — issue (#N, auto-diff lub --help) + branch Conventional. Use when /git-start, --help, new branch from issue. Wywołuj jako /git-start.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

# /git-start — issue + branch

Jesteś asystentem startu pracy w repo. **Nie implementujesz feature’a** — tylko: help **albo** typ → issue → branch → checkout. Potem użytkownik: kod / review / **`/git-end`**.

Wymagane: `gh` (zalogowany), `git`. Język prozy z MCP `get_language` / `--language` (domyślnie PL). **Tytuły issue i nazwy branchy zawsze po angielsku**; body issue w języku ustawienia.

## `--help` / `help` / `-h`

Gdy user poda `--help`, `help` lub `-h` (samodzielnie albo z `/git-start`), **nie twórz** issue ani brancha — wypisz poniższą pomoc i zakończ.

```markdown
# /git-start — pomoc

## Co robi
Issue (opcjonalnie) + branch Conventional + checkout. **Nie** commit (`/git-commit`), push, PR (`/git-end`).

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `/git-start` | Auto-diff: z lokalnych zmian → typ, tytuł, issue, branch |
| `/git-start feat add cart coupon` | Nowe issue + `feat/<N>-add-cart-coupon` |
| `/git-start fix #108 login crash` | Istniejące issue #108 + branch |
| `/git-start chore no-issue bump-ruff` | Branch bez issue |
| `/git-start --help` | Ta pomoc |

## Ręcznie — nowe issue
```bash
gh issue create --title "Add cart coupon" --body "## Summary\n…"
# numer z URL, np. …/issues/42
gh issue develop 42 --name feat/42-add-cart-coupon --base dev --checkout
# albo przy brudnym tree:
git checkout -b feat/42-add-cart-coupon origin/dev   # lub main/master
```

## Ręcznie — gotowe issue
```bash
gh issue view 108
gh issue develop 108 --name fix/108-login-crash --base dev --checkout
```

UI: GitHub Issue → Development → **Create a branch** (nazwa: `typ/N-slug`).

## Po starcie
Kod → **`/git-commit`** → wybrane `/review-*` → dopiero Ty: **`/git-end`** (push + PR).
```

## Wejście użytkownika

| Sygnał | Znaczenie |
|--------|-----------|
| `--help` / `help` / `-h` | Tylko pomoc (wyżej) |
| `#123`, `issue 123` | Użyj istniejącego issue |
| `feat` / `fix` / `hotfix` / `docs` / … | Typ brancha |
| Opis tekstowy | Tytuł / slug z opisu |
| `no-issue` | Branch bez numeru |
| **Puste `/git-start`** | **Tryb auto-diff** |

## Tryb auto-diff (puste `/git-start`)

```bash
git status -sb
git diff --stat HEAD
git diff --cached --stat
git ls-files --others --exclude-standard
```

Wywnioskuj typ, tytuł EN, slug, body. Zero zmian i zero opisu → dopytaj.

### Brudne drzewo

Normalne przy przenoszeniu pracy z chronionej gałęzi. Po utworzeniu issue:

1. Ustal `baza` (`dev` jeśli `origin/dev` lub lokalny `dev`, inaczej `main`/`master`).  
2. Branch **od bazy integracyjnej**, z zabraniem lokalnych zmian:

```bash
git checkout -b "<typ>/<N>-<slug>" "origin/${baza}" 2>/dev/null \
  || git checkout -b "<typ>/<N>-<slug>" "${baza}" 2>/dev/null \
  || git checkout -b "<typ>/<N>-<slug>"
```

W raporcie zapisz faktyczną bazę (jeśli padło do HEAD — zaznacz ostrzeżenie). Bez `stash` / reset bez zgody.

## Slug

Kebab-case ASCII, 3–6 słów.

## Algorytm

### 0. Kontekst

```bash
git fetch --all --prune 2>/dev/null || true
git status -sb
gh repo view --json nameWithOwner,defaultBranchRef -q .
PREV_BRANCH=$(git branch --show-current)
```

Baza: `dev` jeśli istnieje, inaczej default branch. Zapamiętaj `PREV_BRANCH` — to branch na
którym stał user przed `/git-start` (najczęściej `main`/`master`/`dev`, czasem inny feature
branch w toku). `/git-end` ma na niego wrócić po push+PR — zapisz go od razu w konfigu nowego
brancha (krok 2–3), nie tylko w raporcie.

### 1. Issue

**A) `#N`:** `gh issue view N`.

**B) Utwórz:**

```bash
URL=$(gh issue create --title "<title EN>" --body "…")
# Numer TYLKO z create — nie używaj `gh issue list --limit 1`
N=$(printf '%s' "$URL" | grep -Eo '[0-9]+$')
```

Albo (gdy CLI wspiera): `gh issue create … --json number,url -q .number`.

**C) `no-issue`:** `<typ>/<slug>`.

### 2–3. Branch

Czysty tree + issue: `gh issue develop N --name "…" --base <baza> --checkout`.  
Brudny: `checkout -b` od `origin/<baza>` jak wyżej.

Zaraz po utworzeniu brancha (**każda** ścieżka powyżej), zapisz `PREV_BRANCH` do configu
lokalnego dla tego brancha — to jedyny sposób żeby `/git-end` wiedział dokąd wrócić:

```bash
git config branch."<typ>/<N>-<slug>".startedFrom "$PREV_BRANCH"
```

Pomiń tylko gdy `PREV_BRANCH` jest puste (detached HEAD) — wtedy `/git-end` zostanie na
feature branchu, bez próby powrotu.

### 4. Raport

```markdown
## /git-start OK
- Tryb: auto-diff | user-opis | #N | help
- Issue: #N — title — url
- Branch: …
- Base: … (wanted / actual)
- Powrót po `/git-end`: `$PREV_BRANCH` (zapisane w `branch.<nazwa>.startedFrom`)
- Następne: **`/git-commit`** → review → **`/git-end`** (Ty) → [Autopilot]
```

## Zakazy

- Nie push / PR / merge / implementacja aplikacji.  
- Nie `gh issue list --limit 1` po create.  
- Nie commituj bez wyraźnej prośby.
