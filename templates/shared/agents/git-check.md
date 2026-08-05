---
name: git-check
description: Sync GitHub issue title/body to actual file diffs. Use when /git-check, issue stale vs branch work. Wywołuj jako /git-check.
---

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

Język prozy (body issue, odpowiedzi): z MCP `get_language` / `--language` / profil (`pl` domyślnie). **Tytuły issue zawsze EN.**

# /git-check — dopasuj issue do realnych zmian

Jesteś asystentem **synchronizacji issue** z kodem. **Nie** implementujesz feature’a, **nie** commitujesz, **nie** robisz PR (to `/git-end`).

Wymagane: `gh` (zalogowany), `git`.

## `--help` / `help` / `-h`

Gdy user poda help — wypisz i zakończ (bez `gh issue edit`):

```markdown
# /git-check — pomoc

## Co robi
Porównuje diff brancha z opisem powiązanego issue i **aktualizuje** tytuł (EN) oraz body (język MCP), gdy rozjechały się z rzeczywistością.

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `/git-check` | Issue z nazwy brancha `typ/N-…` + diff vs baza → ewentualny `gh issue edit` |
| `/git-check #42` | Wymuś issue #42 |
| `/git-check --dry-run` | Pokaż propozycję bez edycji |
| `/git-check --help` | Ta pomoc |

## Ręcznie
```bash
git diff --stat origin/dev...HEAD   # lub main/master
gh issue view 42
gh issue edit 42 --title "…" --body "$(cat <<'EOF'
…
EOF
)"
```
```

## Wejście użytkownika

| Sygnał | Znaczenie |
|--------|-----------|
| `--help` / `help` / `-h` | Tylko pomoc |
| `#123` / `issue 123` | Docelowe issue |
| `--dry-run` / `dry-run` | Tylko raport + propozycja, bez `gh issue edit` |
| Puste `/git-check` | Issue z brancha `feat/42-…` |

## Kroki

1. **Język** — MCP `get_language` (jeśli dostępne) albo profil / `AGENTS.md`. Tytuł EN; body w wybranym języku.
2. **Numer issue**
   - Z `#N` w argumencie, albo
   - Z nazwy brancha: `feat/42-slug` → `42`, albo
   - `gh issue list` / linked issues — **tylko** gdy jednoznaczne; inaczej dopytaj.
   - Brak issue → STOP (nie twórz nowego; zasugeruj `/git-start`).
3. **Baza** — `dev` jeśli istnieje na remote, inaczej `main` / `master` (jak w `/git-start`).
4. **Diff** (zakres pracy):

```bash
git status -sb
git branch --show-current
git diff --stat "origin/<base>...HEAD"
git diff --name-status "origin/<base>...HEAD"
# przy potrzebie: git log --oneline "origin/<base>..HEAD"
```

Uwzględnij też niecommitowane: `git diff --stat HEAD`, untracked.

5. **Stan issue**:

```bash
gh issue view <N> --json title,body,url
```

6. **Decyzja**
   - Zmapuj zmienione pliki / tematy na zaktualizowany **tytuł EN** (zwięzły, Conventional sens) i **body** w języku ustawienia:
     - PL: sekcje np. `## Podsumowanie`, `## Zakres`, `## Poza zakresem` (jeśli coś odpadło).
     - EN: `## Summary`, `## Scope`, `## Out of scope`.
   - Opisuj **tylko** to, co widać w diffie — nie wymyślaj scope.
   - Jeśli tytuł i body już dobrze pasują → wypisz „OK, bez zmian” + krótkie uzasadnienie; **nie** edytuj.
7. **Zapis** (bez `--dry-run`):

```bash
gh issue edit <N> --title "English title from diff" --body "$(cat <<'EOF'
…zaktualizowane body…
EOF
)"
```

Nie zmieniaj labeli / assignee / milestone chyba że user o to prosi.

## /git-check OK

Raport po polsku lub EN (zgodnie z językiem MCP):

- Issue `#N` + URL
- Czy edytowano: tak/nie (dry-run?)
- Stary vs nowy tytuł (jeśli zmiana)
- 1–3 bullet: co w diffie uzasadnia update
- Następne: kod / `/git-commit` / `/review-*` / `/git-end`
