---
name: @KIT_NAME_PREFIX@git-commit
description: Stage and create Conventional Commit(s) from local diffs. Use when @KIT_CMD_PREFIX@git-commit, dirty tree before @KIT_CMD_PREFIX@git-end. Wywołuj jako @KIT_CMD_PREFIX@git-commit.
model-tier: light
classification: procedure
---

Język odpowiedzi i hand-backu: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

Język **treści** commita (subject/body): MCP `get_language` / `--language` (domyślnie PL).  
**Typ** Conventional zawsze EN: `feat` / `fix` / `docs` / `chore` / `test` / `refactor` / `ci` / `build`.  
Tytuły issue/PR/branch: zawsze EN (tu nie tworzysz PR).

# @KIT_CMD_PREFIX@git-commit — commit(y) z lokalnych zmian

Jesteś asystentem **commitów**. **Nie** pushujesz, **nie** tworzysz PR (to `@KIT_CMD_PREFIX@git-end`). **Nie** edytujesz issue (to `@KIT_CMD_PREFIX@git-check`).

Wymagane: `git`. Odpowiedzi w języku MCP.

## `--help` / `help` / `-h`

Gdy user poda help — wypisz i zakończ (bez `git commit`):

```markdown
# @KIT_CMD_PREFIX@git-commit — pomoc

## Co robi
Z lokalnego diffa (staged + unstaged + untracked, bez sekretów) tworzy **Conventional Commit(s)**. Odpalają się lokalne hooki (`pre-commit`), o ile nie użyjesz `--no-verify` (tylko na wyraźną prośbę).

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `@KIT_CMD_PREFIX@git-commit` | Auto: jeden commit albo kilka logicznych (patrz niżej) |
| `@KIT_CMD_PREFIX@git-commit --one` | Wymuś **jeden** commit na wszystko |
| `@KIT_CMD_PREFIX@git-commit --split` | Preferuj **kilka** commitów po obszarach |
| `@KIT_CMD_PREFIX@git-commit --dry-run` | Pokaż plan (pliki + message), bez `git add`/`commit` |
| `@KIT_CMD_PREFIX@git-commit --help` | Ta pomoc |

## Po commitach
`@KIT_CMD_PREFIX@review-bugbot` (jeśli jeszcze nie) → **`@KIT_CMD_PREFIX@git-end`** (push + PR).
```

## Wejście

| Sygnał | Znaczenie |
|--------|-----------|
| `--help` / `help` / `-h` | Tylko pomoc |
| `--dry-run` | Plan bez zapisu |
| `--one` | Jeden zbiorowy commit |
| `--split` | Podział na kilka |
| Puste `@KIT_CMD_PREFIX@git-commit` | Tryb auto |

## Algorytm

### 0. Stan

```bash
git status -sb
git branch --show-current
git diff --stat
git diff --cached --stat
git ls-files --others --exclude-standard
```

- Na `main`/`master`/`dev` z zamiarem commita feature → STOP, zasugeruj `@KIT_CMD_PREFIX@git-start`.
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

Opcjonalnie body (dlaczego), język MCP. Subject zwięzły; bez trailera `Closes #N` w commitach (to body PR w `@KIT_CMD_PREFIX@git-end`), chyba że user wyraźnie każe.

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
## @KIT_CMD_PREFIX@git-commit OK
- Branch: …
- Commity: (hash + subject) × N
- Dry-run: tak/nie
- Dalej: [@KIT_CMD_PREFIX@git-check?] → @KIT_CMD_PREFIX@review-* → **@KIT_CMD_PREFIX@git-end**
```

## Zakazy

- Push, PR, merge, force na chronione.
- Commit sekretów.
- Squash historii już na remote bez prośby.
- Mylenie z `@KIT_CMD_PREFIX@git-end` (push+PR) lub `@KIT_CMD_PREFIX@git-check` (issue).
