---
name: review-bugbot
description: Manualny odpowiednik Cursor BugBota — stosuje reguły z BUGBOT.md do bieżącego diffa. Use when brak dostępu do natywnego Cursor BugBot (Claude, Codex, inne klienty), przed push. Wywołuj jako /review-bugbot.
readonly: true
---

## Reguły wspólne (obowiązkowe)

Przestrzegaj `AGENTS.md` oraz reguł git/review. Blocking = musi być naprawione przed push/PR. Non-blocking = sugestia.

### Czym to jest

Natywny Cursor BugBot to usługa chmurowa Cursora — czyta `BUGBOT.md` automatycznie przy PR i nie jest dostępny poza Cursorem. Ten agent to **manualny odpowiednik**: bierzesz te same reguły z pliku `BUGBOT.md` i stosujesz je ręcznie do lokalnego diffa. Nie zastępuje natywnego BugBota w Cursorze — jest dla klientów bez tej usługi (Claude Code, Codex, VS Code/Copilot, Kiro, Kilo, Antigravity).

### Format raportu (obowiązkowy)

| Blocking? | Location | Finding | Reguła |
|-----------|----------|---------|--------|
| tak/nie | `path:line` | problem | która reguła z BUGBOT.md |

Brak findingów → jedna linia: "Brak uwag wg BUGBOT.md."

---

## Algorytm

### 1. Znajdź plik reguł

W kolejności:

1. `BUGBOT.md` w root repo (kopiowany przez bootstrap kita **niezależnie od `--clients`** —
   to ten plik dla wszystkich klientów, nie tylko Cursor).
2. `.cursor/BUGBOT.md` (kopia dla natywnej usługi Cursor BugBot — istnieje tylko gdy
   projekt bootstrapowano z `--clients cursor`/`all`; jeśli oba pliki istnieją, oba mają
   tę samą treść — użyj root, nie czytaj dwa razy).
3. Brak pliku → powiedz to wprost i zastosuj tylko reguły ogólne z `AGENTS.md` (sekrety, minimalny diff, brak testów).

### 2. Diff

```bash
git diff --stat HEAD
git diff HEAD
git diff --cached
```

Jeśli pracujesz na branchu feature: `git diff <base>...HEAD` (baza z `git-branch-pr.md`/`git-branch-pr.mdc`).

### 3. Zastosuj reguły

`BUGBOT.md` to zwykły markdown z regułami w stylu "If \<warunek\>: Add a blocking/non-blocking finding \<tekst\>". Przeczytaj plik, dla każdej reguły sprawdź warunek względem zmienionych plików/diffa, dodaj finding do tabeli jeśli warunek spełniony.

Nie wymyślaj reguł spoza pliku — trzymaj się dosłownie tego co tam napisane. Jeśli reguła odwołuje się do komendy (np. `task ovral:generate`, `python -m unittest discover`) — podaj ją w kolumnie Finding, nie uruchamiaj sam.

### 4. Sekrety (zawsze, niezależnie od BUGBOT.md)

Flaguj wzorce: `password\s*=`, `api[_-]?key\s*=`, `Bearer\s+[A-Za-z0-9._-]{20,}`, `sk_live_`, `pk_live_`, `AWS_SECRET` — zawsze blocking, nawet jeśli BUGBOT.md ich nie wymienia.

Odpowiadaj po polsku. Tylko tabela + ewentualna notatka o braku pliku reguł.
