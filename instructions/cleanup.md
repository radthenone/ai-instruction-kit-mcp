# `/cleanup` — sieć bezpieczeństwa na śmieci po weryfikacji

> Prywatne notatki z użycia. Źródło: `.claude/commands/cleanup.md`.

**Robi:** skanuje `git status`, szuka plików stworzonych **tylko po to, żeby
coś sprawdzić** (jednorazowe skrypty, ad-hoc testy, dumpy), pokazuje listę
z uzasadnieniem, pyta, usuwa zaakceptowane.

| Wywołanie | Co się dzieje |
|---|---|
| `/cleanup` | skan + propozycja + pytanie o potwierdzenie |
| `/cleanup --dry-run` | tylko lista, bez usuwania i bez pytania |
| `/cleanup --yes` | usuń bez dodatkowego pytania (już potwierdziłem w tej wiadomości) |

**Kiedy:** po debugowaniu, **przed** [git-commit](git-commit.md).

## Dlaczego to nie jest to samo, co auto-sprzątanie

`AGENTS.md` mówi, że agent kasuje **swoje własne** scratch pliki z **bieżącej**
sesji sam, bez pytania. `/cleanup` jest siecią na to, co i tak zostało — po
poprzedniej sesji, po innym agencie, po mnie. **Dlatego tu zawsze jest lista
i pytanie:** nie wiadomo, kto i po co dany plik stworzył.

## Klasyfikacja — musi trafić w **dwa** sygnały, nie w jeden

Plik jest kandydatem, gdy spełnia co najmniej **dwa** z:

- nazwa sugeruje jednorazowość: `tmp_*`, `scratch*`, `debug_*`, `check_*.py`,
  `try_*.sh`, `poc_*`, `test123.py`
- leży poza normalną strukturą testów projektu
- **nic go nie importuje** (sprawdzone grepem)
- powstał w bieżącej sesji i służył do zweryfikowania czegoś, co już
  zweryfikowano
- duplikuje istniejący test w oficjalnym katalogu, tylko gorzej

To „conajmniej dwa" jest ważne. Sama nazwa nie wystarcza — plik `debug_utils.py`
może być produkcyjny.

## Czego nie ruszy nigdy

- plików **trackowanych** w gicie (bez mojej wyraźnej zgody)
- `node_modules/`, `.venv/`, `dist/`, `build/`
- build/cache z `.gitignore` — „to nie jego sprawa"
- **`.env`, klucze, credentials** — to zawsze eskalacja do mnie, nigdy
  auto-cleanup

Usuwa pojedynczo (`rm` / `git rm`), **nigdy `rm -rf` katalogu**.

**Pułapka:** `/cleanup` patrzy głównie na **untracked**. Śmieci, które przypadkiem
zacommitowałem, przejdą przez sito.
