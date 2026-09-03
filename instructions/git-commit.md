# `/git-commit` — Conventional Commits z lokalnego diffa

> Prywatne notatki z użycia. Źródło: `.claude/commands/git-commit.md`.
> Część osi czasu: [git-start](git-start.md) → kod → [git-commit](git-commit.md) →
> [[git-check]](git-check.md) → `/review-*` → [git-end](git-end.md).

**Robi:** czyta staged + unstaged + untracked, planuje commit(y), robi `git add`
po ścieżkach i commituje.
**Nie robi:** pusha, PR-a, edycji issue.

| Wywołanie | Co się dzieje |
|---|---|
| `/git-commit` | auto: jeden commit albo kilka logicznych (max ~5) |
| `/git-commit --one` | wymuś jeden commit na wszystko |
| `/git-commit --split` | wymuś podział po obszarach |
| `/git-commit --dry-run` | pokaż plan (pliki + message), nic nie zapisuj |

**Do zapamiętania:**

- **Typ zawsze EN** (`feat`/`fix`/`docs`/`chore`/`test`/`refactor`/`ci`/`build`),
  treść w języku MCP.
- **Bez `Closes #N` w commitach.** To idzie do body PR-a w [git-end](git-end.md).
- Odpalają się hooki `pre-commit`. `--no-verify` **tylko** na moje wyraźne
  żądanie — sam z siebie nie użyje.
- Po nieudanym pre-commit: naprawia i robi **nowy** commit, nie amenduje.
- Na `master` z zamiarem commita feature'a → STOP i odesłanie do [git-start](git-start.md).
- Sekretów (`.env`, klucze, credentials) nie commituje — pomija i ostrzega.

**Pułapka:** `Closes #N` w commicie zamiast w PR. GitHub zamknie issue przy mergu
commita, nie PR-a — mylące w historii. Kit celowo tego nie robi.
