# `/teacher-agent` — nauczyciel obsługi agentów

Data: 2026-08-11
Status: częściowo zrealizowany (#16)

> **Stan implementacji.** W #16 weszły: `/teacher-agent`, moduł `core:agent-ops-canon`
> i wpis w manifeście — czyli D1 (zakres wyłącznie meta) i D2 (setup jako punkt
> wyjścia). **Nie weszły** D3 (zakładanie issue w tle) ani moduł `core:gap-triage`:
> istnieją wyłącznie po to, żeby karmić `/audit` i komendę nocną, a tych nie ma
> i nie są zaplanowane. Sekcje o `core:gap-triage` czytaj jako projekt na przyszłość,
> nie jako opis repo.

## Problem

Kit uczy **domeny** (`/teacher-architecture`, `/teacher-frontend`, `/teacher-backend`) i pilnuje **procesu** (`/git-*`, `/review-*`). Nie uczy niczego o **obsłudze samych agentów**: kiedy sięgnąć po skilla, jak podzielić pracę na worktree, kiedy delegować do subagenta, jak sformułować zadanie tak, żeby wynik dało się przyjąć.

Ta wiedza siedzi dziś w zewnętrznych bibliotekach skilli (superpowers, mattpocock/skills), które żyją własnym cyklem wydawniczym. Kit ich nie kopiuje — **korzysta z nich**. Brakuje warstwy, która tłumaczy, *jak* z nich korzystać w kontekście tego setupu.

Druga luka: setup rośnie z każdym projektem, ale nikt nie pilnuje, czy nie zostaje w tyle za tym, co pojawia się na zewnątrz.

## Zakres

**W zakresie:** `/teacher-agent` + dwa moduły wiedzy + rejestracja w manifeście.

**Poza zakresem** (osobne specy, w tej kolejności):

1. `/audit` — skan repo z propozycjami issue zatwierdzanymi pojedynczo
2. komenda nocna — autonomiczne drenowanie kolejki `ready-for-agent`

Uwaga do (2): silnik już istnieje i nie należy go pisać od nowa. Claude Code ma wbudowane `/batch` („execute in parallel across 5–30 isolated worktree agents that each open a PR"), `/goal` (warunek zatrzymania oceniany przez osobnego sędziego, nie przez samoocenę agenta) oraz `/loop` i `/schedule`. Rola komendy nocnej to **opakowanie**: kolejka `ready-for-agent`, konwencja branchy z `/git-start`, twarde granice (bez merge, limit PR-ów) i raport rano.

Te trzy składają się w jeden łańcuch i dlatego dzielą moduł `core:gap-triage`:

```text
/audit  →  issue: ready-for-agent  →  [noc]  →  PR-y rano  →  /review-*
```

`/teacher-agent` wpina się w ten łańcuch od strony setupu: luki, które wykryje, trafiają do tej samej kolejki, w tym samym formacie.

## Decyzje

### D1. Zakres nauczania: wyłącznie meta

`/teacher-agent` uczy obsługi agentów. Pytania o React, Django czy granice architektury **odsyła** do istniejących `/teacher-*`. Powód: duplikacja treści między nauczycielami rozjeżdża się szybciej, niż ktokolwiek ją naprawia.

Tematy:

1. **Skille** — czym jest skill, priorytet procesowych przed implementacyjnymi (`brainstorming` przed budowaniem, `systematic-debugging` przed fixem), kiedy mattpocock (`tdd`, `prototype`, `research`, `codebase-design`, `grilling`) a kiedy superpowers.
2. **Izolacja pracy** — worktree jako miejsce na jeden problem: jeden worktree = jeden branch = jedno zadanie. Jak dzielić zadania na rozłączne katalogi (nie rozłączne linie w tym samym pliku), żeby równolegli agenci nie deptali sobie po plikach. Kiedy worktree to narzut i wystarczy zwykły branch.
3. **Delegacja** — subagent vs praca inline. Fan-out ma sens przy 2+ zadaniach bez wspólnego stanu; każdy spawn startuje na zimno i re-derywuje kontekst, więc dla zadania zależnego od bieżącej rozmowy jest stratą.
4. **Autonomia: kiedy przestać i kiedy wrócić** — dwa różne wymiary, mylone ze sobą. `/goal` odpowiada na „kiedy przestać" (Stop hook, warunek oceniany przez **osobnego sędziego**, nie przez samoocenę agenta); `/loop` i `/schedule` na „kiedy wrócić"; `/batch` rozbija jedną dużą zmianę na 5–30 agentów w worktree, z których każdy otwiera PR. Czym różni się `/batch` od `dispatching-parallel-agents`, i dlaczego `/batch` omija `/git-start`.
5. **Prompt** — kryterium ukończenia, zakres plików, wymagany dowód. Dlaczego „popraw to" produkuje śmieci.
6. **Grillowanie i review** — `grilling` jako stress-test planu **przed** kodem; przyjmowanie review bez potakiwania.
7. **Ten kit** — jak `/git-start` → `/git-commit` → `/review-*` → `/git-end` składa się w jeden flow i gdzie w nim siedzą `/teacher-*`.

### D2. Setup to punkt wyjścia, nie sufit

Agent czyta realny setup (`.claude/agents`, `.claude/commands`, `.claude/skills`, `~/.agents/skills`, `.mcp.json`, hooki w `settings*.json`) i uczy na tym, co user faktycznie ma — ale **nie traktuje go jako jedynej słusznej drogi**. Zestawia go z bieżącym stanem świata zewnętrznego i nazywa różnicę.

Reguły oceny źródeł: nowy moduł `core:agent-ops-canon` (odpowiednik `core:engineering-canon`, ta sama filozofia — mechanizm ponad autorytet).

### D3. Luki setupu → issue automatycznie, w tle

Wykryta luka nie przerywa lekcji. Agent spawnuje subagenta, który zakłada issue; lekcja leci dalej. Na końcu odpowiedzi sekcja **„Założyłem w tle"** z numerami.

**To świadomy wyjątek** od zasady „nauczyciel nie edytuje", którą trzymają pozostałe `/teacher-*`. Uzasadnienie: bez trwałego zapisu obserwacja ginie wraz z sesją, a setup ma rosnąć przez lata. Wyjątek jest ograniczony — patrz D4 i D5.

### D4. Waga i gotowość to dwie różne osie

| Oś | Nośnik | Wartości |
|----|--------|----------|
| **Waga** | prefiks w tytule + sekcja w body | `Blokujące` / `Warte roboty` / kosmetyka (**nie zgłaszana wcale**) |
| **Gotowość** | etykiety z `docs/agents/triage-labels.md` | `ready-for-agent` / `ready-for-human` / `needs-triage` |

Testy wagi:

| Poziom | Test | Skutek |
|--------|------|--------|
| Blokujące | psuje się teraz albo psuje cudzą pracę — brak testu na ścieżce krytycznej, niespójność manifestu, zepsuty gate w CI | issue **+ branch + commity** |
| Warte roboty | koszt rośnie z czasem, ale nic dziś nie płonie | issue, bez brancha |
| Kosmetyka | preferencja stylu | nic |

**Żadnych nowych etykiet.** Repo ma już słownik — `core:gap-triage` z niego korzysta, nie wymyśla własnego.

### D5. Wykonanie delegowane, nigdy własny git

`/teacher-agent` (i później `/audit`) **nie wołają `git` ani `gh` z ręki**. Delegują do `/git-start` (issue + `gh issue develop` + branch + checkout), `/git-commit`, `/git-end`. Operacje na trackerze wg `docs/agents/issue-tracker.md`.

Nazewnictwo dziedziczone z `/git-start`: branch `typ/N-slug`, tytuł issue i nazwa brancha **po angielsku**, body w języku z `get_language()` (domyślnie PL).

Podział pracy przy luce `Blokujące`: subagent w tle woła `/git-start` (issue + branch), implementuje zmianę **w tym branchu**, woła `/git-commit`. **PR-a nie wystawia** — `/git-end` zostaje decyzją usera po obejrzeniu brancha. Branch nigdy nie jest tworzony z brudnego drzewa roboczego; jeśli tree jest brudne, subagent zakłada samo issue i zapisuje to w sekcji „Założyłem w tle".

### D6. Anty-spam

Bez tych ograniczeń automat zasypie tracker:

- dedupe przed założeniem: `gh issue list --state open` (wg `docs/agents/issue-tracker.md`), porównanie po temacie
- **max 5 propozycji na sesję**, posortowane wagą; reszta jako zdanie „jest tego więcej"
- nigdy issue na coś, co jest przedmiotem otwartego PR

## Architektura

Źródłem prawdy jest `templates/shared/agents/`. Katalogi `.claude/agents/`, `.claude/commands/` i `.cursor/agents/` to **kopie generowane** przez `scripts/render_agent_commands.py` — pilnuje tego `tests/test_generated_artifacts.py`.

| Plik | Rola | Nowy? |
|------|------|-------|
| `templates/shared/agents/teacher-agent.md` | agent — jedyne miejsce do edycji treści | tak |
| `modules/core/agent-ops-canon.md` | kanon źródeł o obsłudze agentów | tak |
| `modules/core/gap-triage.md` | skala wagi, format propozycji, anty-spam, mapowanie na etykiety | tak |
| `manifest.yaml` | wpisy `core:agent-ops-canon`, `core:gap-triage`, tagi `[core, teaching]` | edycja |
| `.claude/{agents,commands}/teacher-agent.md`, `.cursor/agents/teacher-agent.md` | kopie | render |

Zero nowej mechaniki — wszystko wchodzi w istniejący pipeline.

### `modules/core/agent-ops-canon.md`

Hierarchia źródeł, od najmocniejszego:

1. **Lokalny setup** — jedyne źródło o tym, co user naprawdę ma
2. **Oficjalna dokumentacja Claude Code / Agent SDK** — w wersji, która jest zainstalowana
3. **Repo upstream używanych bibliotek skilli** — README, changelog, treść samych skilli
4. **Praktyka z realną adopcją** — opisy działających setupów, nie zapowiedzi
5. **Reszta sieci** — z jawnym testem: czy to opisuje **mechanizm**, czy tylko obiecuje efekt

Plus reguła nadrzędna, wspólna z `core:engineering-canon`: rekomendacja bez uzasadnienia mechanizmem to opinia.

### `modules/core/gap-triage.md`

Format propozycji, identyczny dla `/teacher-agent` i `/audit`:

```text
[Blokujące] Guard manifest paths in resolver tests
branch: fix/<N>-guard-manifest-paths
Problem: <2 zdania — co i czemu boli>
Dowód: tests/test_resolver.py:88, manifest.yaml:145
```

Sekcja `Dowód` jest obowiązkowa i musi wskazywać `plik:linia`. Luka bez dowodu nie jest zgłaszana — to filtr na halucynacje.

## Format odpowiedzi

Kalka z pozostałych `/teacher-*`, żeby wszystkie zachowywały się tak samo:

1. **O co tak naprawdę pytasz** — przeformułowanie problemu
2. **Model mentalny** — jak patrzy na tę klasę decyzji ktoś doświadczony
3. **Opcje** — max 3, tabelą (kiedy sensowna / czym płacisz), pod tabelą jedna rekomendacja
4. **W Twoim setupie** — konkretnie: które skille, którzy agenci, które komendy
5. **Pułapki** — 2–4, z sygnałem ostrzegawczym
6. **Dowód** — po czym poznasz, że wyszło
7. **Twój ruch** — 1 zadanie + 1 pytanie kontrolne
8. **Założyłem w tle** — issue i branche z tej sesji (sekcja pomijana, gdy pusto)

Bez eseju. Sekcja = kilka zdań albo lista. Język wg `get_language()`, domyślnie PL.

## Testowanie

Nowe pliki wpadają w istniejące gate'y bez pisania nowych testów:

- `tests/test_generated_artifacts.py` — kopie w `.claude/` i `.cursor/` zgadzają się ze źródłem w `templates/shared/agents/`
- `tests/test_manifest_mappings.py` — ścieżki modułów z `manifest.yaml` istnieją

Weryfikacja ręczna po implementacji: odpalić `/teacher-agent` z pytaniem o worktree i sprawdzić, czy (a) czyta realny setup, (b) odsyła domenę do właściwego `/teacher-*`, (c) nie zakłada issue na kosmetykę.

## Ryzyka

| Ryzyko | Ograniczenie |
|--------|--------------|
| Automat zasypuje tracker issue'ami | D6: dedupe, limit 5/sesja, próg wagi |
| Agent halucynuje lukę, której nie ma | obowiązkowa sekcja `Dowód` z `plik:linia` |
| Treść o zewnętrznych bibliotekach starzeje się | `core:agent-ops-canon` każe czytać upstream, nie pamięć modelu |
| Rozjazd z `/audit`, gdy powstanie | wspólny moduł `core:gap-triage` jako jedyne źródło reguł |
| Wyjątek od „nauczyciel nie edytuje" rozlewa się na resztę | wyjątek zapisany tutaj i ograniczony do zakładania issue; edycja kodu tylko przez `/git-*` |

## Migracja przy okazji

`docs/superpowers/{specs,plans}` → `docs/{specs,plans}`. Powód: superpowers i mattpocock/skills to zewnętrzne biblioteki, których kit używa — ich nazwa nie powinna strukturyzować drzewa docs tego repo. Odwołania w `README.md`, `profiles/README.md`, `templates/extras.md`, `templates/shared/rules/use-guides.md` poprawione.
