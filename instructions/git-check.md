# `/git-check` — dopasuj issue do tego, co naprawdę zrobiłem

> Prywatne notatki z użycia. Źródło: `.claude/commands/git-check.md`.
> Część osi czasu: [git-start](git-start.md) → kod → [git-commit](git-commit.md) →
> `/git-check` → `/review-*` → [git-end](git-end.md).

**Robi:** porównuje diff brancha z opisem issue i **aktualizuje** tytuł (EN)
i body, gdy się rozjechały.
**Nie robi:** commita, pusha, PR-a. **Nie tworzy** nowego issue — brak issue to
STOP i odesłanie do [git-start](git-start.md).

| Wywołanie | Co się dzieje |
|---|---|
| `/git-check` | issue z nazwy brancha `typ/N-…` + diff vs baza |
| `/git-check #42` | wymuś issue #42 |
| `/git-check --dry-run` | propozycja bez `gh issue edit` |

**Kiedy tego naprawdę używam:** gdy zakres w trakcie pracy się przesunął.
Zacząłem od „dodaj filtr", skończyłem na „dodaj filtr + popraw paginację" —
issue dalej mówi tylko o filtrze, a PR będzie się do niego odwoływał przez
`Closes`. `/git-check` przed [git-end](git-end.md) naprawia ten rozjazd.

**Do zapamiętania:**

- Opisuje **tylko to, co widać w diffie**. Nie dopisuje scope z głowy.
- Nie rusza labeli, assignee ani milestone, chyba że wyraźnie poproszę.
- Jak tytuł i body już pasują — pisze „OK, bez zmian" i nic nie edytuje.
