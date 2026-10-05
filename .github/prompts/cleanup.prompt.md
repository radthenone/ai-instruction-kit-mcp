---
mode: "agent"
description: "Znajdź i usuń zbędne pliki tymczasowe/testowe stworzone podczas weryfikacji (scratch scripts, ad-hoc testy, tmp dumps), które zostały w repo po zakończeniu pracy. Use when zakończono debugowanie/weryfikację i podejrzewasz śmieci w working tree, przed `/git-commit`. Wywołuj jako /cleanup."
---

## Reguły wspólne

Przestrzegaj `AGENTS.md` — sekcja „Auto-sprzątanie": własne scratch pliki z **bieżącej** sesji agent usuwa sam, bez pytania, zaraz po użyciu. `/cleanup` to sieć bezpieczeństwa na to, co i tak zostało — dlatego **tu** zawsze pokazujesz listę i pytasz o potwierdzenie (nie wiesz z pewnością, kto i po co stworzył dany plik).

# /cleanup — sprzątanie zaległości

Szukasz plików, które ktoś (Ty w poprzedniej sesji, inny agent, user) stworzył **tylko po to, by coś sprawdzić** — jednorazowe skrypty, ad-hoc testy, dumpy — i które nie są częścią właściwej zmiany, a zostały w repo.

## `--help` / `help` / `-h`

```markdown
# /cleanup — pomoc

## Co robi
Skanuje `git status` (untracked + staged) i szuka plików pasujących do wzorców "scratch/tymczasowe", pokazuje listę z uzasadnieniem, pyta o potwierdzenie, usuwa zaakceptowane.

## Wywołania
| Komenda | Efekt |
|---------|--------|
| `/cleanup` | Skan + propozycja + pytanie o potwierdzenie |
| `/cleanup --dry-run` | Tylko lista, bez usuwania i bez pytania |
| `/cleanup --yes` | Usuń bez dodatkowego pytania (user już potwierdził w tej samej wiadomości) |
| `/cleanup --help` | Ta pomoc |
```

## Algorytm

### 1. Zbierz kandydatów

```bash
git status --porcelain
git status --porcelain --ignored
```

Interesują Cię głównie **untracked** pliki (`??`) — tracked pliki nigdy nie usuwaj tą komendą.

### 2. Klasyfikuj po sygnałach (nie po samej nazwie)

Plik jest kandydatem, gdy spełnia **conajmniej dwa** z:

- Nazwa/ścieżka sugeruje jednorazowość: `test_tmp*`, `tmp_*`, `scratch*`, `debug_*`, `*_debug.*`, `check_*.py`, `try_*.sh`, `sandbox*`, `poc_*`, liczby/hashe w nazwie bez znaczenia (`test123.py`).
- Leży poza normalną strukturą testów projektu (nie w katalogu testów wskazanym w `AGENTS.md` / repo — np. luźny plik w root albo w `src/` obok modułu, którego nie importuje nic poza nim samym).
- Nie jest importowany/referencjonowany przez żaden inny plik (sprawdź grep).
- Powstał w bieżącej sesji (widoczny w Twojej własnej historii tool-calli, jeśli ją pamiętasz) i służył wyłącznie do zweryfikowania czegoś, co już zweryfikowano.
- Duplikuje istniejący test w oficjalnym katalogu testów (ten sam scenariusz, gorsza jakość).

**Nigdy** nie kwalifikuj: plików trackowanych w git, plików z `.gitignore` które wyglądają na build/cache (to nie Twoja sprawa), plików, których nazwa sugeruje że user je stworzył ręcznie, niczego z katalogów `node_modules/`, `.venv/`, `dist/`, `build/`.

### 3. Pokaż plan

```markdown
## /cleanup — propozycja

| Plik | Powód |
|------|-------|
| `scratch_check.py` | ad-hoc skrypt, nic go nie importuje, powstał podczas weryfikacji w tej sesji |

Brak kandydatów → "Nic do posprzątania — working tree czysty z podejrzanych plików."
```

### 4. Potwierdzenie i usunięcie

- `--dry-run` → zatrzymaj się tu, nie usuwaj.
- Bez `--yes` → poczekaj na jawne potwierdzenie usera (lista + "usuń" / "tak" / numer(y) do wykluczenia).
- Usuwaj tylko zaakceptowane pozycje, pojedynczo (`rm`/`git rm` — jeśli plik jednak trackowany, użyj `git rm`), nie `rm -rf` katalogów.

### 5. Raport

```markdown
## /cleanup OK
- Usunięto: N plików (lista)
- Pominięto (user odrzucił): lista
- Working tree: czysty / zostały tracked zmiany do commita
```

## Zakazy

- Usuwanie plików trackowanych bez wyraźnej zgody.
- Usuwanie bez pokazania listy i uzasadnienia (poza `--yes` po wcześniejszym pokazaniu w tej samej rozmowie).
- Zgadywanie po samej nazwie bez drugiego sygnału (patrz sekcja 2).
- Ruszanie `.env`, kluczy, credentiali — to nie jest "zbędny plik", to zawsze eskalacja do usera, nigdy auto-cleanup.
