# Praca nocna i headless

Za dnia grillujesz issue: kryteria akceptacji, relacje blocked-by. W nocy `/kit-ai:night-run` pracuje sam. Wznawia go heartbeat, a `/goal` jest opcjonalny.

## `night-run`

Procedura na każdy ticket:

1. `git-start` dla issue,
2. test-first,
3. szybkie bramki: lint, typecheck, testy dotknięte zmianą,
4. `git-commit`,
5. review na diffie,
6. `git-end`,
7. CI,
8. merge,
9. jeden raport na PR i zamknięcie issue.

Problem zamiast pytania kończy się komentarzem `needs-human` z pytaniami na issue. Agent idzie dalej.

### Kto jest kim

- **Orchestrator** działa w głównej sesji. Nie czyta kodu. Wybiera tickety i dla każdego uruchamia świeżego subagenta.
- **Subagent ticketu** (`night-run-ticket`) wykonuje jedno issue i oddaje Hand-back.
- **Review** robi osobny świeży subagent na samym `git diff`. Dzięki temu kontekst nie puchnie.

### Gałąź bazowa i kontekst

- Baza to `dev`, jeśli `origin/dev` istnieje i nie jest w tyle za gałęzią domyślną. Inaczej gałąź domyślna repo.
- Plik kontekstu nocy (`~/.cache/night-run-<repo>-<data>/context.md`) to mapa aplikacji, konwencje i pułapki toolchainu. Subagent czyta ten plik zamiast wszystkich ADR-ów. Po każdym tickecie orchestrator dopisuje, co doszło.
- Commit po każdym zielonym kroku.
- Deny guarda (`server-guard:` albo `git-guard:` w powodzie) to reguła, nie awaria. Nie obchodzisz jej i nie liczysz do prób naprawy.

### Bramki i model

- Bramki jakości to kroki `run:` z `.github/workflows/*.yml` i sekcja kontroli z overlayu. Lokalnie tylko szybkie. Pełny zestaw testów zostaje w CI.
- Model subagenta: `model: <nazwa>` w tekście celu. Bez wpisu używany jest model sesji.
- Koszt: po każdym tickecie liczone są tokeny (input, cache_creation, cache_read, output), maksymalny kontekst i czas. Wynik trafia do `NIGHT-RUN REPORT`.

### Przykłady

Bez `/goal`, z wykonawcą headless i wskazanym review:

```text
/kit-ai:night-run #150 #151 /kit-ai:headless opencode --timeout 90 "implementacja i testy" /kit-ai:review-edge /kit-ai:review-bugbot
```

Pod `/goal` sędzia widzi tylko transkrypt, więc warunek musi żądać dowodów w rozmowie:

```text
/goal Wykonaj issue #150–#157 wg /kit-ai:night-run. Koniec, gdy w transkrypcie jest
NIGHT-RUN REPORT, w którym każdy ticket ma: MERGED (wynik gh pr view --json state)
albo needs-human (link do komentarza), albo wpis "night-run halted".
```

Uwagi dopisujesz za warunkiem, np. `#155 bez PDF` albo `model: sonnet`. Polecenia z celu mają pierwszeństwo przed procedurą. W Claude `model:` przyjmuje aliasy (`sonnet`, `opus`, `haiku`, `fable`). Konkretną wersję wybierasz dla całej sesji: `claude --model <id>`.

### Na VPS

Kroki odrzucone przez server guard idą jako „tylko CI”. Brak checków CI oznacza brak merge. Zob. [Server guard](../hosty/server-guard.md).

## `headless`

Z dowolnego klienta kitu (hosta) zlecasz zadanie innemu klientowi, uruchomionemu bez interfejsu (wykonawcy). Host czeka, wrapper sprząta procesy, host streszcza wynik.

```text
/kit-ai:headless <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] [--ctx <katalog>] "<treść>"
```

| Flaga | Znaczenie |
|---|---|
| `--model <id>` | model wykonawcy w jego formacie, np. `haiku` albo `anthropic/claude-haiku-5-5` |
| `--timeout <min>` | jawny twardy limit, bez przedłużania. Po nim drzewo procesów jest zabijane (kod `124`), chyba że wrapper wykrył limit dostawcy: wtedy wynik to `75` i klasa `LIMIT`. Bez flagi termin to 60 min, przedłużany przy postępie do 120 min |
| `--heartbeat <min>` | co ile minut linia stanu w logu, domyślnie 10 |
| `--ctx <katalog>` | katalog nocy, podawany przez `night-run` |

Wykonawca dostaje treść dosłownie, plus stałą stopkę. Stopka wymaga planu 5–10 kroków przy większym zadaniu, test-first z commitem po każdym zielonym kroku, zakazu `git stash`, `git checkout` i `git reset` oraz lokalnych testów tylko dotkniętych zmianą. Na końcu raport z sekcjami `## Zmiany`, `## Testy` i `## Problemy`.

Push i PR robi host przez `git-end`, po review commitów.

### Termin i postęp

Bez `--timeout` termin to 60 minut. Co 10 minut wrapper sprawdza postęp: nowe bajty wyjścia, zmianę `HEAD` albo `git status`, wzrost CPU procesów potomnych. Jeśli był postęp, termin przedłuża się o 10 minut, najwyżej do 120 minut. Brak postępu przy terminie kończy się zrzutem procesów i klasą `HANG`.

Jawny `--timeout` to twardy limit bez przedłużania. Limit dotyczy jednej próby. Po `LIMIT` (kod `75`) albo `HANG` wrapper może uruchomić kolejny model albo zastępcę z nowym limitem, więc całe wywołanie może trwać dłużej. Kod i klasa wyniku pochodzą wtedy z ostatniej próby.

### Pętla

Gdy to samo wywołanie narzędzia powtarza się 5 razy przy niezmienionym repo, wrapper zabija drzewo procesów przed limitem. Raport dostaje wpis `## pętla: <N>× <linia>`. Nie dotyczy wykonawcy `claude`: `claude -p` drukuje tylko finalny tekst, bez wywołań narzędzi, więc wykrywanie pętli jest dla niego wyłączone, a próba trwa do terminu albo `--timeout`.

### Klasy wyniku

| Klasa | Znaczenie |
|---|---|
| `OK` | zakończone bez problemów |
| `LIMIT` | limit dostawcy, kod `75`, pauza |
| `HANG` | brak postępu albo timeout, kod `124` |
| `ERROR` | kod różny od zera albo błąd wywołania |
| `MODEL` | nieznany model |
| `SUSPECT` | exit 0 bez zmian w repo |
| `POLITYKA` | wpis stasha albo commit bez trailera `Co-Authored-By` |

Logi leżą poza projektem, w `~/.cache/kit-ai/headless/<repo>/`. Wiersz wywołania to jedna linia JSON na końcu wyjścia.
