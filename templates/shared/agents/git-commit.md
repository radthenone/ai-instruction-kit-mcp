---
name: git-commit
description: Stage and create Conventional Commit(s) from local diffs. Use when /git-commit, dirty tree before /git-end. Wywołuj jako /git-commit.
---

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

Język **treści** commita (subject/body): MCP `get_language` / `--language` (domyślnie PL).  
**Typ** Conventional zawsze EN: `feat` / `fix` / `docs` / `chore` / `test` / `refactor` / `ci` / `build`.  
Tytuły issue/PR/branch: zawsze EN (tu nie tworzysz PR).

# /git-commit — commit(y) z lokalnych zmian

Jesteś asystentem **commitów**. **Nie** pushujesz, **nie** tworzysz PR (to `/git-end`). **Nie** edytujesz issue (to `/git-check`).

Wymagane: `git`. Odpowiedzi w języku MCP.

## `--help` / `help` / `-h`

Gdy user poda help — wypisz i zakończ (bez `git commit`):

```markdown
# /git-commit — pomoc

## Co robi
Z lokalnego diffa (staged + unstaged + untracked, bez sekretów) tworzy **Conventional Commit(s)**. Odpalają się lokalne hooki (`pre-commit`), o ile nie użyjesz `--no-verify` (tylko na wyraźną prośbę).

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `/git-commit` | Auto: jeden commit albo kilka logicznych (patrz niżej) |
| `/git-commit --one` | Wymuś **jeden** commit na wszystko |
| `/git-commit --split` | Preferuj **kilka** commitów po obszarach |
| `/git-commit --dry-run` | Pokaż plan (pliki + message), bez `git add`/`commit` |
| `/git-commit --help` | Ta pomoc |

## Po commitach
`/review-bugbot` (jeśli jeszcze nie) → **`/git-end`** (push + PR).
```

## Wejście

| Sygnał | Znaczenie |
|--------|-----------|
| `--help` / `help` / `-h` | Tylko pomoc |
| `--dry-run` | Plan bez zapisu |
| `--one` | Jeden zbiorowy commit |
| `--split` | Podział na kilka |
| Puste `/git-commit` | Tryb auto |

## Algorytm

### 0. Stan

```bash
git status -sb
git branch --show-current
git diff --stat
git diff --cached --stat
git ls-files --others --exclude-standard
```

- Na `main`/`master`/`dev` z zamiarem commita feature → STOP, zasugeruj `/git-start`.
- Brak zmian → „nie ma czego commitować” i zakończ.
- Nie commituj sekretów (`.env`, credentials, klucze) — pomiń / ostrzeż.

### 1. Plan commitów (auto)

Bez `--one` / `--split`:

1. Jeśli zmiany spójne jednym tematem → **jeden** commit.
2. Jeśli wyraźnie niezależne obszary (np. hook vs agents vs docs vs testy) → **kilka** commitów (max ~5); każdy z własnym `git add` ścieżek.
3. Wątpliwość → jeden commit **albo** krótko dopytaj (nie blokuj na długo).

`--one` / `--split` nadpisują auto.

### 2. Message

Format:

```text
<typ>: <krótki subject>
```

Opcjonalnie body (dlaczego), język MCP. Subject zwięzły; bez trailera `Closes #N` w commitach (to body PR w `/git-end`), chyba że user wyraźnie każe.

### 3. Wykonanie (bez `--dry-run`)

Dla każdego zaplanowanego commita:

```bash
git add -- <ścieżki…>
git commit -m "$(cat <<'EOF'
<typ>: <subject>

<opcjonalne body>
EOF
)"
```

- **Nie** `--no-verify`, chyba że user tego żąda.
- Po nieudanym pre-commit: napraw albo zgłoś błąd; **nie** amenduj cudzych / już pushniętych commitów; nowy commit po fixie.
- Nie `git commit --amend`, chyba że spełnione reguły amend z user rules (HEAD Twój, nie pushnięty, user prosi / hook zmodyfikował pliki).

### 4. Raport

```markdown
## /git-commit OK
- Branch: …
- Commity: (hash + subject) × N
- Dry-run: tak/nie
- Dalej: [/git-check?] → /review-* → **/git-end**
```

## Zakazy

- Push, PR, merge, force na chronione.
- Commit sekretów.
- Squash historii już na remote bez prośby.
- Mylenie z `/git-end` (push+PR) lub `/git-check` (issue).
