---
description: Autonomiczna praca na liście issue w nocy albo w dzień (samodzielnie, /goal opcjonalny) — orkiestrator, na każdy ticket świeży subagent (git-start → test-first → PR → merge) albo wykonawca /headless, review na diffie (także skille review z argumentów), needs-human zamiast pytań, na końcu NIGHT-RUN REPORT. Użyj TYLKO gdy cel lub użytkownik wprost nazywa /night-run. Wywołuj jako /night-run.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

Język odpowiedzi, prompt dla subagenta i hand-back: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

# /night-run — lista issue bez człowieka

Przerabiasz listę issue z argumentów albo celu (bez listy — kolejkę `ready-for-agent`),
jeden po drugim, aż każde jest **zmergowane** albo ma komentarz **needs-human**. Człowiek
śpi. Issue są wygrillowane za dnia — projekt jest w ich treści, Twoja rola to wykonanie.

## Zasady nadrzędne

- **Jesteś orkiestratorem w głównej sesji, nigdy wykonawcą ticketu.** Ticket robi subagent
  ticketu, review osobny świeży subagent albo skille review z argumentów. Łańcuch prowadzi sesja ticketu.
  Orkiestrator zleca tylko ticket i trzyma jedną linię stanu (`#N: <stan> <PR> <koszt>`). Sam nie czytasz
  kodu i nie odpalasz testów: Twój kontekst ma zostać mały.
- **Komendy kitu uruchamiasz według klienta** (`/git-*`, `/review-*` i inne z argumentów
  lub promptu ticketu), by działały na modelu z frontmattera agenta, nie sesji:
  - **Claude Code:** agent o nazwie komendy jest w `.claude/agents/<nazwa>.md` → **Agent**
    tego typu bez parametru `model` (model bierze się z frontmattera); brak agenta →
    **Skill**. Subagent ticketu uruchamiasz typem `night-run-ticket` (nie `general-purpose`). Subagent uruchamia kolejne komendy-agentów (do 3 poziomów,
    `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), więc `/git-*` zostają wewnątrz subagenta
    ticketu, a orkiestrator nie dostaje z nich tur. Sam `/night-run` działa w głównej
    sesji (w Claude uruchamiany Skillem, nie Agentem): potrzebuje `CronCreate` i watchdoga.
  - **opencode:** komenda `/<nazwa>` z `.opencode/command/` (model z frontmattera, gdy
    Profil ma `models.opencode`); brak `model:` → model sesji.
  - **klienci bez modelu per agent** (Cursor, Codex, VS Code, Kiro, Kilo, Antigravity) →
    bez zmian: inline albo skill na modelu sesji. Dla klientów bez typu agenta (Codex, VS Code, Antigravity, inline): wczytaj `night-run-ticket` (skill albo prompt klienta) i wykonaj go z parametrami zlecenia.
  - **Model komendy z celu** — tylko jawna forma `<komenda>: model <nazwa>` (np.
    `git-start: model haiku`) nadpisuje frontmatter tej komendy tam, gdzie klient ma
    parametr modelu. Samo `model: <nazwa>` ustawia wyłącznie model ticketu (niżej).
  - Brak agenta/komendy (fallback na Skill albo inline) zapisujesz w hand-backu
    i w NIGHT-RUN REPORT.
- Klient bez subagentów → łańcuch inline, ale z tymi samymi regułami z `night-run-ticket`.
- Gdy sesja ma narzędzie `delegate_task` i plik karty (`.ai/night-run-t3.md`, instalowany przy `t3code` w `integrations:` Profilu) istnieje, karta zastępuje transport, nie kroki procedury.
- **Polecenia z tekstu celu mają pierwszeństwo** przed tą procedurą (np. „bez merge, same PR-y”,
  „#155 pomiń PDF”, inny próg dużego ticketu; `watchdog: próg N, życie M` — progi watchdoga, §7;
  `ctx: <sufiks>` — sufiks katalogu CTX nocy, §6).
- **Model ticketu** (`MODEL`) z celu, np. „model: sonnet”; w Claude parametr `model` Agenta
  (tylko aliasy: sonnet/opus/haiku/fable). Brak lub „gdzie uważasz” → model sesji; tańszy tylko
  dla ticketu mechanicznego (≤2 kryteria, 1 aplikacja, bez pieniędzy, płatności
  i współbieżności) — tańszy model robi ~2× więcej tur, więc na większym wychodzi drożej.
  Model i powód per ticket → NIGHT-RUN REPORT.
- **Zero pytań do człowieka.** Nie używasz narzędzi pytających; niepewność → needs-human
  albo decyzja odwracalna (niżej).
- **Nie uruchamiasz** `superpowers:brainstorming`, `superpowers:finishing-a-development-branch`
  ani skilli z `disable-model-invocation` (`grill-with-docs`, `to-spec`, `to-tickets`,
  `implement`…) —
  stają na akceptacji człowieka.
- Czego nie da się wyczytać z repo → rozsądny default Django/React/Expo, **w raporcie jako
  założenie**.

## Argumenty

```text
/night-run #N1 #N2 [implementacja: <wykonawca> <model>, <model>; <wykonawca> <model>] [/headless <wykonawca> [--model …] [--timeout …] [--heartbeat …] "<treść>"] [/review-* …]
```

`/goal` opcjonalny: noc działa sama. Wznawianie nocy = watchdog `.ai/night-run-watchdog.sh`
+ tik `CronCreate` co 4 h (krok 7), nie warunek `/goal`. Domyślnie bez limitu pauz i bez
końca nocy; cel z `pauzy: N` (po N-tej pauzie halt C), `koniec: HH:MM` (teraz ≥ koniec →
halt C) albo `ctx: <sufiks>` (osobny katalog CTX nocy dla równoległych sesji, krok 6) je włącza. Pod `/goal` jego tekst to cel (niżej „Polecenia z tekstu celu”).

- **Składnia `krok: wartość` (`implementacja:`, `review:`, `effort:`), spójna z `<komenda>: model <nazwa>`.**
- **Lista issue** — `#N` przed pierwszym argumentem z `/` lub prefiksem kroku. Brak → kolejka (krok 4).
- **`implementacja: <wykonawca> <model>, <model>; <wykonawca> <model>`** — wykonawca implementacji z łańcuchem modeli albo z wolnego tekstu celu, który nazywa wykonawcę (wolny tekst celu np. „antigravity wykonuje implementację”). Średnik rozdziela wykonawców, przecinek modele jednego wykonawcy; `@poziom` (np. `@high`) kit tłumaczy na nazwę/parametr danego transportu. Każdy wskazany wykonawca jest sprawdzany raz na starcie nocy przeciw `clients:` w `.ai/project.profile.yaml`: wykonawca spoza `clients:` → `needs-human na starcie nocy` — żaden ticket nie startuje, NIGHT-RUN REPORT z `needs-human: nieznany wykonawca <nazwa>`, koniec.
- **Brak wskazania i jawne `/headless` → bez zmian:** brak wskazania wykonawcy oznacza implementację bezpośrednią w subagencie ticketu (kroki 2–3 bez `/headless`); jawne `/headless <wykonawca> [flagi] "<treść>"` to wywołanie wrappera `.ai/headless.mjs`.
- **`/headless <wykonawca> [flagi] "<treść>"`** — implementację ticketu robi wykonawca
  headless (`EXEC`, `FLAGI`, `TREŚĆ`). Argument kończy zamykający cudzysłów treści
  (cudzysłów obowiązkowy); treść i flagi wrappera przekazujesz bez zmian (`--timeout`
  domyślnie 60 min — większy ticket potrzebuje więcej). Wariant w `night-run-ticket`.
  `EXEC` sprawdzasz raz na starcie nocy, przed pierwszym ticketem:
  - klient bez `/headless` (brak skilla/komendy `headless` albo `.ai/headless.mjs`) →
    fallback: implementacja subagentem jak bez argumentu, w raporcie
    `wykonawca: subagent (brak /headless)`;
  - wykonawca spoza `clients:` w `.ai/project.profile.yaml` albo równy hostowi (klient tej
    sesji) → nieznany wykonawca → needs-human na starcie nocy — żaden ticket nie startuje,
    NIGHT-RUN REPORT z `needs-human: nieznany wykonawca <nazwa>`, koniec.
- **Skille review z argumentów** — jeden lub kilka (`/review-edge`, `/review-bugbot`,
  `/review-security`, `/review --fix`, …), z ich własnymi flagami. Bez nich → domyślny łańcuch review (łańcuch, krok 2). Skille review z argumentów nadal zastępują domyślny łańcuch.
  Każdy sprawdzasz raz na starcie nocy na liście skilli klienta:
  nieznany skill review → needs-human na starcie nocy — żaden ticket nie startuje,
  NIGHT-RUN REPORT z `needs-human: nieznany skill review <nazwa>`, koniec.
  `/review` poza Claude Code (brak wbudowanego review) → traktowane jak nieznany skill review
  (needs-human na starcie nocy).
  Rozróżnienie `/code-review` i `/review`:
  - `/code-review` = osobisty skill (gdy istnieje), dostaje numer issue (`/code-review <N>`), bo jego oś Spec czyta issue;
  - `/review [effort] [--fix]` = wbudowane review Claude Code; dostaje zakres `<BASE>...HEAD`;
  - kryterium wykrycia osobistego skilla `code-review`: skill nie deklaruje flag `--fix`/`--comment`;
  - gdy w argumentach podano `/code-review` z flagami `--fix` albo `--comment`: orkiestrator najpierw sprawdza, czy klient ma wbudowane `/review` (Claude Code); dopiero wtedy — przy wykryciu osobistego skilla `code-review` (niedeklarującego tych flag) — tłumaczy na `/review` z tymi flagami (decyzja odwracalna) i zapisuje to w raporcie (w linii Założenia). Poza Claude Code brak wbudowanego `/review` uniemożliwia tłumaczenie (needs-human na starcie nocy);
  - po `--fix`: zebranie poprawek przez `/git-commit` w osobnym commicie na branchu ticketu i ponowne CI;
  - `--comment` działa tylko wtedy, gdy PR już istnieje (po `/git-end`); przy review przed `/git-end` nie przekazujesz `--comment` — wynik zostaje w raporcie nocy (bez publikacji na nieistniejący PR);
  pozostałe skille review dostają tylko diff.

`EXEC` i `REVIEW` (albo „domyślne”) → nagłówek `CTX` i NIGHT-RUN REPORT.

## Start nocy (raz)

### 1. Gałąź bazowa

Baza (ta sama reguła w `/git-start`, `/git-check`, `/git-end`, `/night-run`): linia `base: <gałąź>`
w `.ai/project.md`, jeśli jest; inaczej `dev` tylko wtedy, gdy `origin/dev` istnieje i **nie jest
w tyle** za gałęzią domyślną (nie jest jej ścisłym przodkiem); inaczej gałąź domyślna repo.
Gdy ostatnie scalone PR-y szły gdzie indziej — jedna linijka ostrzeżenia, wybór bez zmian.

```bash
git fetch --all --prune
DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
BASE=$(sed -n 's/^base:[[:space:]]*\([^[:space:]]*\).*/\1/p' .ai/project.md 2>/dev/null | head -1)
if [ -z "$BASE" ]; then
  BASE=$DEFAULT
  if git rev-parse -q --verify origin/dev >/dev/null \
     && ! { git merge-base --is-ancestor origin/dev "origin/$DEFAULT" \
            && [ "$(git rev-parse origin/dev)" != "$(git rev-parse "origin/$DEFAULT")" ]; }; then
    BASE=dev
  fi
fi
LAST=$(gh pr list --state merged --limit 5 --json baseRefName -q '.[].baseRefName' \
  | sort | uniq -c | sort -rn | awk 'NR==1{print $2}')
[ -n "$LAST" ] && [ "$LAST" != "$BASE" ] && echo "uwaga: baza $BASE, ostatnie scalone PR-y szły do $LAST"
```

`BASE` i powód („base: z project.md” / „dev aktywny” / „dev w tyle” / „brak dev”) → NIGHT-RUN REPORT.

### 2. Bramki jakości

Źródła, bez duplikatów: (1) kroki `run:` z `.github/workflows/*.yml` na `pull_request`/`push`
(bez deploy, publikacji, sekretów); (2) overlay `.ai/project.md` (MCP `get_overlay`): kontrole,
testy, komendy, `codegen:`.

Brak obu → default: `ruff check`, `pytest <pliki dotknięte ticketem>`,
`python manage.py makemigrations --check --dry-run`, `tsc --noEmit` w pakietach frontendu,
przy `codegen: orval` (domyślnie) regeneracja klienta bez różnicy w `git diff`; jako założenie.
Lokalnie tylko **szybkie**; pełny zestaw — CI.

### 3. Baza zielona

Ostatni CI na bazie: `gh run list --branch $BASE --limit 1 --json conclusion,headSha`.
Porównaj `headSha` z `git rev-parse origin/$BASE`. Zgodne (run na HEAD bazy): czerwony → **halt** (przypadek C), zielony → baza zielona.
Różne (run z innego commita, np. push na `dev` bez workflow): ani zielony, ani czerwony nie rozstrzyga → bramki szybkie na `origin/$BASE` odpala krótki subagent. Brak CI → to samo.

### 4. Kolejka

Nazwy etykiet stanu: prawa kolumna `docs/agents/triage-labels.md` (jeśli jest); niżej stoją
nazwy domyślne — wstawiaj nazwy z `triage-labels.md` projektu, nie dosłownie.

- Cel ani argumenty nie podają listy →
  `gh issue list --state open --label ready-for-agent --json number,title --limit 50`.
  Pusta lista → NIGHT-RUN REPORT „brak ready-for-agent” i koniec.
- Issue z listy ręcznej z etykietą `ready-for-human` / `needs-info` / `needs-triage` /
  `wontfix` → pomijasz, w raporcie `skipped: <etykieta>`. Bez etykiety stanu → bierzesz
  (zgodność wstecz).
- Etykiety designu (każdy klient, także z `ready-for-agent` — zabezpieczenie przed źle
  przełączonym stanem): `design: layout` bez `docs/design/<N>.md` na bazie
  (`git cat-file -e origin/$BASE:docs/design/<N>.md` pada) → `skipped: design spec missing`;
  `design: tokens` → `skipped: design: tokens`.
- Warunek wykonania `needs-local` (także z listy ręcznej i przy `ready-for-agent`):
  - na hoście `vps` (`Host: vps` z nagłówka CTX / `kit-ai host`) → pomijasz, w raporcie `skipped: needs-local`;
  - na hoście `local` (`Host: local`) → bierzesz normalnie (bez pomijania).
- **Ticket w innej nocy:** przed podjęciem każdego ticketu (z kolejki lub listy ręcznej) sprawdzasz inne katalogi CTX tego dnia (`~/.cache/night-run-<repo>-<data>*/` poza Twoim `$CTX_DIR`). Ticket z listy, który w pliku `context.md` innego CTX tego dnia ma w `## Stan` krok ≠ `koniec` (ticket trwający w innej nocy) → pomijasz, w raporcie `skipped: w innej nocy <katalog>` (gdzie `<katalog>` to nazwa tamtego katalogu CTX, np. `night-run-<repo>-<data>` albo `night-run-<repo>-<data>-b`). Ticket z listy zależny od ticketu pominiętego w ten sposób (zależność `blocked_by`) również pomijasz: `skipped: zależność #N w innej nocy <katalog>`.

### 5. Kolejność

Per issue: `gh api repos/<owner>/<repo>/issues/<N>/dependencies/blocked_by --jq '.[].number'`.
Kolejność topologiczna, przy remisie z celu. Otwarty blokujący spoza listy → needs-human
„zablokowany przez #X spoza listy”.

### 6. Plik kontekstu nocy

Katalog nocy: domyślnie `CTX_DIR=~/.cache/night-run-<repo>-<data>/` (gdzie `<data>` to `YYYY-MM-DD`) — `CTX=$CTX_DIR/context.md`,
raz na noc, poniżej ~150 linii, sekcje. Wszędzie (prompt ticketu, `CronCreate`, Read/Write)
pełna ścieżka z `$HOME` zamiast `~`. `~/.cache` przeżywa restart hosta, `/tmp` nie —
nigdy tam (ani CTX, ani `## Stan`, ani logi pracy w tle).

- **Sufiks CTX dla równoległych nocy:** dwie noce w tym samym repo i dniu (równoległe workspace'y)
  mają osobne katalogi CTX, `## Stan`, watchdogi i cron, i nie ruszają nawzajem swoich ticketów.
  - **Cel `ctx: <sufiks>`** (np. `ctx: a`, `ctx: b`, `ctx: test`) → `CTX_DIR=~/.cache/night-run-<repo>-<data>-<sufiks>/`. Gdy katalog ten już istnieje, a jego `## Stan` ma krok ≠ `koniec`: jeśli wznawiasz przerwaną noc (ten sam proces/sesja lub cel ze wznowieniem) → kontynuujesz pracę od kroku z `## Stan`; jeśli to nowy start równoległej sesji, a trwa inna aktywna noc na tym sufiksie → zatrzymujesz start tej sesji — nie wykonujesz `CronDelete`, `TaskStop` ani `--report` dla tego katalogu (katalog CTX zajęty przez inną aktywną noc).
  - **Bez `ctx:`:** jeśli katalog dnia `~/.cache/night-run-<repo>-<data>/` istnieje, a jego `## Stan` ma krok ≠ `koniec` (noc w toku), to przydzielasz automatyczny sufiks `-b`, `-c`… (`CTX_DIR=~/.cache/night-run-<repo>-<data>-b/`, `...-c/` itd. — katalog tworzysz przez `mkdir`; jeśli już istnieje i jest w toku, sprawdzasz kolejny wolny lub z krokiem `koniec`) z linią w raporcie (`Sufiks CTX: automatyczny <sufiks> (noc w toku w <katalog>)`). Gdy katalog dnia nie istnieje lub ma krok `koniec`, to używasz bazowego `CTX_DIR=~/.cache/night-run-<repo>-<data>/` bez sufiksu.

- **Nagłówek:** uruchom raz na noc w repo `kit-ai night-ctx` i wklej wynik **bez zmian** na
  początek CTX (BASE, `Host:`, bramki szybkie, język, linia-znacznik generatora
  `<!-- kit-ai night-ctx v1 host=… -->`). `Host:` pochodzi z `kit-ai host`
  (`detect_host_profile()`), nie z treści bundla — **nie wnioskujesz go z `get_bundle`**.
  Wartości oznaczone „założenie” przenieś do NIGHT-RUN REPORT. Znacznika nie usuwaj ani nie
  edytuj: watchdog kończy noc, gdy go brak albo `host=` nie zgadza się z `kit-ai host`.
- **Mapa aplikacji:** katalog → co w nim jest, 1 linia.
- **Konwencje:** same reguły z AGENTS.md, BUGBOT.md, `.ai/project.md`.
- **Pułapki toolchainu:** z pamięci projektu (CLAUDE.md, notatki agenta) i overlay; brak → „brak danych”.
- **Przekazania:** zapisywane do osobnego pliku `$CTX_DIR/handoff-<N>.md` (≤ 30 linii: fakty dla następcy — modele, serwisy, endpointy, migracje, zmienione kontrakty, bez streszczenia pracy); w `context.md` zostaje tylko indeks `#N → handoff-<N>.md` dopisywany przez Ciebie po każdym MERGED.
- **Zaległe wywołania headless:** przed pierwszym ticketem przejrzyj `~/.cache/night-run-<repo>-*/`
  poprzednich nocy (zakończonych z krokiem `koniec` lub rzeczywiście przerwanych — nigdy aktywnej nocy z krokiem ≠ `koniec`). Katalog z `headless-rows.jsonl` to bufor bez podsumowania, czyli noc przerwana przed
  raportem: `node .ai/headless.mjs --report --ctx <tamten katalog> > <CTX_DIR>/zalegle-<nazwa tamtego katalogu>.md`
  (wrapper kasuje bufor dopiero po wypisaniu). Plik wpisz do NIGHT-RUN REPORT jako `zaległe wywołania`.
- **Stan (`## Stan` na końcu CTX):** linie `krok: ticket|review|resume|ci|koniec`, `coderabbit-rundy: #<N> <R>` (licznik rund CodeRabbit ticketu #N; zapisuje go git-end przed pushem każdej rundy, R+1; linia innego ticketu nie dotyczy bieżącego ticketu, wtedy R = 0; przetrwa wznowienie i Clean Slate; nadpisując `## Stan`, zachowaj tę linię),
  `subagent: <id>` (transkrypt czyta watchdog), `watchdog: <id zadania w tle>`, `wznowienia
  per ticket`, pauzy limitu: otwarta `pauza limitu od <ts>; wznowienie <ts> (epoch N)` (zapisuje
  ją watchdog), zamknięta `pauza limitu od <ts> do <ts>` (zamyka ją watchdog po wznowieniu; ty tylko sprawdzasz). Nadpisujesz **Ty**
  przy każdej zmianie kroku; tik czyta ją jako pierwszą.

### 7. Watchdog i cron (tylko Claude Code)

Orkiestrator budzi się tylko wtedy, gdy jest co robić. Tik kosztuje turę i cały kontekst,
więc nie jest mechanizmem oczekiwania.

- **Watchdog w tle (`.ai/night-run-watchdog.sh`, instalowany przy kliencie claude):** Wymaga `kit-ai` w PATH (weryfikacja `kit-ai host`; na VPS bez `uvx`). Bash
  `run_in_background` z **jawnym `timeout: 7200000`** i pełną ścieżką repo: `bash "$(git rev-parse --show-toplevel)/.ai/night-run-watchdog.sh" "$CTX" 60 110`
  (domyślnie próg anomalii 60 min, życie 110 min; cel `watchdog: próg N, życie M` (min)
  zamienia te liczby, życie ≤ 110). Bez `timeout` Bash w tle dostaje domyślne 30 min
  (1 800 000 ms) i ginie przed końcem życia — watchdog przestaje pilnować w kroku dłuższym
  niż 30 min. Zależność: życie ≤ 110 min < `timeout` (7 200 000 ms = 2 h, maksimum Bash w tle). Skrypt śpi i
  **nie budzi orkiestratora**, dopóki idzie praca: postępem jest zapis w katalogu CTX albo
  w transkrypcie subagenta z `subagent: <id>`. Kończy się, czyli budzi orkiestratora
  powiadomieniem o zakończeniu, tylko gdy:
  - exit 1 `anomalia` — brak postępu > 60 min (subagent failed/bez hand-backu też → tik);
  - exit 0 `halt` — nagłówek CTX bez znacznika generatora, brak `kit-ai` w PATH (dodaj do PATH; na VPS bez `uvx kit-ai`) albo `host=` ≠ `kit-ai host`
    (sprawdzane przy każdym starcie i odnowieniu) → halt C z powodem z linii `halt:`;
  - exit 0 `życie` — minęło 110 min → odnów (niżej);
  - exit 0 `koniec nocy` — w `## Stan` jest `krok: koniec`;
  - exit 0 `wznowienie po pauzie limitu` — wykrył komunikat limitu (429 / „session limit”)
    w transkrypcie subagenta, zapisał otwartą pauzę do `## Stan` i spał do godziny resetu
    z komunikatu + 5 min (bez godziny: co 30 min, przedłużane, gdy przyjdzie nowa linia
    limitu). Zamyka pauzę `do <ts>` sam watchdog. Pauza limitu **nie jest** anomalią.
- **Odnowienie w tej samej turze co start:** przy starcie ticketu, review, wznowienia i każdym
  hand-backu, w tym samym wywołaniu narzędzi co Agent/Bash: `TaskStop` starego watchdoga
  (`watchdog:` z `## Stan`, jeśli żyje), start nowego `run_in_background` z `timeout: 7200000`, zapis
  `watchdog: <id>` do `## Stan`. Po wybudzeniu z pauzy sprawdź, że otwarta pauza ma
  już `do <ts>` (zamyka ją watchdog); jeśli nie — dopisz `pauza limitu od X do <teraz>`, potem odnów.
- **Jeden watchdog naraz:** przed odnowieniem sprawdź listę zadań w tle; działa → `TaskStop`,
  nie dubluj.
- **Cron co 4 h jako siatka:** cron łapie to, co ginie razem z sesją (watchdog) i pauzę
  dłuższą niż życie watchdoga. **`CronList` przed `CronCreate`** — obowiązkowo, także przy wznowieniu sesji (cron przeżywa wznowienie i działa obok nowego): jest już cron dla tej nocy (dla tego `<CTX>`) o tym
  harmonogramie → nic nie tworzysz. Inaczej `CronCreate`, recurring `57 */4 * * *`, z promptem
  i wpisaną na sztywno ścieżką CTX: `night-run tik: przeczytaj sekcję „Tick watchdoga i crona” w /night-run
  i „## Stan” w <CTX>, działaj wg niej.` Tik crona to tura z kontekstem, więc nie częściej niż co 4 h.
- Bez `CronCreate` u klienta → ten krok pomiń (watchdog zostaje, jeśli jest Bash w tle).
- Każde zakończenie nocy (wszystko MERGED, halt, raport) zaczyna się od `CronDelete`
  i `TaskStop` watchdoga.

**Powiadomienie „is waiting on its own background work” (tylko Claude Code):** gdy przyjdzie,
orkiestrator **nie wywołuje żadnych narzędzi** i odpowiada jedną linią, np.
`ok — czekam na koniec pracy w tle`. To nie jest sygnał do statusu, `## Stan` ani
`ListAgents`; kolejkę napędza powiadomienie o zakończeniu subagenta; watchdog i cron łapią tylko anomalie.

## Łańcuch na ticket — dokładnie ten

1. **Subagent ticketu** (świeży, typ `night-run-ticket`, `model: MODEL`): z parametrami zlecenia z sekcji „Zlecenie ticketu” (kroki 1–8 w `night-run-ticket`), z podstawioną listą plików `handoff-<B>.md` dla blokujących #N (`blocked_by`, przechodnio w obrębie listy tej nocy; brak blokujących → brak handoffów). Łańcuch prowadzi sesja ticketu. Orkiestrator zleca tylko ticket i trzyma jedną linię stanu (`#N: <stan> <PR> <koszt>`). Przed startem ticketu upewnij się, że żaden inny CTX tego dnia nie ma go w `## Stan` jako trwającego (reguła z kroku 4; w razie kolizji pomijasz: `skipped: w innej nocy <katalog>`). Subagent ticketu dostaje z kontekstu nocy tylko część wspólną (nagłówek, mapa, konwencje, pułapki) oraz wskazane handoffy blokujących — nie cały CTX z Przekazaniami ani handoffy niezależnych ticketów. `## Stan` w `CTX` (ticket, id, krok `ticket`) nadpisujesz **w tym samym
   wywołaniu narzędzi co uruchomienie subagenta** (Claude Code: razem z odnowieniem watchdoga, sekcja 7), nie w osobnej turze — każda
   tura czyta cały kontekst. Wraca z hand-backiem i niewypchniętym branchem; wtedy
   poprawiasz `## Stan`, jeśli hand-back zmienia krok. W parametrach zlecenia kroki 2–3 w `night-run-ticket` dostają `Wykonawca` z wpisanymi `implementacja: <wykonawca> <model>, <model>; <wykonawca> <model>` albo `/headless <EXEC> [FLAGI] "<TREŚĆ>"` lub `brak`, oraz dwiema
   rozstrzygniętymi wartościami: `LIMIT` (`przejmij` / `czekaj`; z tekstu celu `limit:`, brak → `przejmij`)
   i `PRZEJĘCIE` (alias + źródło): (a) tekst celu `przejęcie: <alias>` (tylko ta noc), (b) Profil
   `models.claude.takeover`, (c) brak → `sesja` (model sesji). Alias z celu spoza `haiku`/`sonnet`/
   `opus`/`fable` → `sesja` z wpisem w raporcie („nieznany alias przejęcia”). Bez `/headless` i `implementacja:` pole `Wykonawca` ma wartość `brak`.
2. **Review.** Przed review — w obu wariantach — nadpisz `## Stan` (krok `review`; przy
   skillach z argumentów także nazwa bieżącego skilla), w tym samym wywołaniu narzędzi co
   uruchomienie review. Ze skillami review z argumentów: uruchamiasz je **Ty** według reguły
   „Komendy kitu uruchamiasz według klienta” (np. `review-bugbot` na modelu z
   frontmattera), w kolejności z argumentów, dopisując do wywołania linię `Język wyjścia: <language>` (wartość z `get_language`),
   wg reguły z sekcji Argumenty.
   Skille review uruchamiasz w katalogu brancha ticketu (worktree ticketu z hand-backu albo katalog główny, gdy worktree nie był używany): `git -C <katalog brancha>` albo cwd ustawiony na ten katalog. Przed startem sprawdzasz `git -C <katalog brancha> branch --show-current`: inny branch niż branch ticketu → nie odpalasz review na złym diffie, tylko zgłaszasz rozjazd w raporcie nocy (needs-human).
   Od skilla bierzesz tylko tabelę niżej (dla wbudowanego `/review`: orkiestrator przepisuje findingi do tabeli `Severity | Location | Finding | Fix` — nagłówek bez zmian — i oznacza każdy wiersz jako potwierdzony albo niepewny); skill / review z `--fix` poprawia sam — po `--fix` subagent ticketu po
   wznowieniu zbiera poprawki przez `/git-commit` (w osobnym commicie na branchu ticketu) i uruchamia ponowne CI.
   Bez argumentów — **subagent review** (zawsze nowy), który wykonuje domyślny łańcuch review dobrany po typach plików w diffie:
   - zawsze `/review-bugbot`;
   - diff dotyka plików wykonywalnych (`*.py`, `*.mjs`, `*.js`, `*.ts`, `*.sh`) → + jedno review, w kolejności: `/review-security` (auth, sekrety, guardy) > review stacku (Tier ≠ `none`) > `/review-edge`;
   - sam tekst (`*.md`, docs, szablony procedur) → tylko bugbot;
   - maks. 2 review na ticket;
   - bez `/code-review` w domyślnym łańcuchu (Spec sprawdza bramka przed merge) i bez `--fix`.
   Prompt subagenta review: „Review `git diff origin/$BASE...HEAD` na `<branch>`:
   Język wyjścia: <language> (wartość z `get_language`).
   Review w tej kolejności: `/review-bugbot`; gdy diff dotyka plików wykonywalnych (`*.py`, `*.mjs`, `*.js`, `*.ts`, `*.sh`), jedno dodatkowe review: `/review-security` > review stacku (Tier ≠ `none`) > `/review-edge`. Maks. 2 review; bez `/code-review` i `--fix`. Czytaj tylko diff
   i dotknięte pliki, zakresami. Zwróć `Severity | Location | Finding | Fix` (nagłówek tabeli
   bez zmian) + potwierdzony/niepewny. Dodaj wiersze Spec: każde kryterium z sekcji `Kryterium ukończenia` (albo `Kryteria akceptacji`; nagłówek bez ogonków `Kryterium ukonczenia` też się liczy) w body issue (`gh issue view <N>`) to wiersz Spec z Location `Spec: …`; niespełnione = High, spełnione = bez findingu. Linie `Ręcznie:` / `Recznie:` są niesprawdzalne w diffie: wiersz Spec ze statusem `niesprawdzalne`, nie High. Nie edytuj.” Zapisz jego id w `## Stan`.
   Raport review pokazywany użytkownikowi (i zapisywany w `## Stan` / raporcie nocy) orkiestrator
   przekłada na język Profilu: nagłówki sekcji, etykiety werdyktów i podsumowanie (np. `## Standardy` /
   `## Spec`, `TWARDE` / `OCENA`). Bez zmian: nagłówek tabeli `Severity | Location | Finding | Fix`
   i wartości Severity, cytaty kodu, identyfikatory i ścieżki.
3. **Wznów subagenta ticketu** (w Claude `SendMessage` na jego id, nie nowy start) z samą
   tabelą findingów (bez tłumaczenia): findingi → wykonawca implementacji, poprawka razem z testem (potwierdzone → poprawka + test; niepewne → opis PR). Gdy review miało `--fix`, subagent najpierw wykonuje `/git-commit` dla wprowadzonych poprawek i ponawia CI przed `/git-end`. Review z kroku 2 **jest**
   potwierdzeniem review dla `/git-end`. Przed wznowieniem nadpisz `## Stan` (krok `resume`),
   przed CI — krok `ci`. Dalej kroki 6–8 w `night-run-ticket`.
4. Sprawdź dowód sam: `gh pr view <PR> --json state` → `MERGED`.
5. Zapisz Przekazanie z hand-backu do osobnego pliku `$CTX_DIR/handoff-<N>.md` (≤ 30 linii: fakty dla następcy — modele, serwisy, endpointy, migracje, zmienione kontrakty, bez streszczenia pracy), dopisz wpis do indeksu w `CTX` (`#N → handoff-<N>.md`), a w rozmowie orkiestratora zostaw tylko jedną linię stanu: `#N: <stan> <PR> <koszt>` (dzięki temu kontekst orkiestratora nie rośnie z każdym ticketem). Policz koszt ticketu (sekcja „Pomiar”); powrót do bazy przed następnym ticketem: gdy `.git` jest plikiem (linked worktree, np. `[ -f .git ]`), `git fetch origin` i `git switch --detach origin/$BASE`; w głównym checkoucie bez zmian: `git checkout $BASE && git pull`.
6. **Reload plików kita po MERGED (tylko w repo źródłowym kita):**
   Gdy zmergowany ticket dotyczy repozytorium będącego źródłem kita (weryfikacja: `manifest.yaml` w root repozytorium, np. `[ -f manifest.yaml ]`):
   - **Warunek:** diff zmergowanego PR dotyka ścieżek `templates/` albo `src/guides/`. Repo aplikacji (brak `manifest.yaml` w root) albo brak zmian w tych ścieżkach → krok pominięty.
   - **Czyste drzewo robocze:** przed pullem sprawdź stan drzewa: `git status --porcelain`. Gdy drzewo jest brudne (`git status --porcelain` niepuste) → pominięcie z wpisem w raporcie nocy (`pominięto reload kita: brudne drzewo robocze`).
   - **Pull i reload:** przy czystym drzewie (`git status --porcelain` puste) wykonaj `git fetch origin`, następnie `git pull --ff-only origin "$BASE"` (bez przełączania branchy; działa też przy odłączonym HEAD), potem `kit-ai reload .`.
   - **Wczytanie nowej wersji:** orkiestrator czyta ponownie zmienione sekcje swojej procedury (z odświeżonych plików); subagenci i agenci `/git-*` biorą nową wersję sami przy starcie.
   - **Obsługa błędów:** błąd reloadu (`kit-ai reload` zakończone błędem) → wpis w raporcie nocy (`błąd reloadu kita: <szczegóły>`) i utworzenie nowego issue (`gh issue create`), aby problem został naprawiony w kolejnym biegu. Noc idzie dalej.

Hand-back needs-human albo halt od subagenta → sekcja „Gdy ticket napotka problem”.

## Zlecenie ticketu

Przekazujesz subagentowi ticketu parametry zlecenia (orkiestrator nie przepisuje kroków procedury — te definiuje agent `night-run-ticket`):

```markdown
Ticket #N, BASE, CTX: #<N>, baza <BASE>, kontekst <CTX>
Handoffy blokujących: <lista plików $CTX_DIR/handoff-<B>.md | brak blokujących>
Wykonawca: implementacja: <wykonawca> <model>, <model>; <wykonawca> <model> | /headless <EXEC> [FLAGI] "<TREŚĆ>" --ctx <CTX_DIR> | brak
LIMIT: <przejmij | czekaj>
PRZEJĘCIE: <alias> (<źródło>)
Nadpisania: merge-mimo-spec, merge-mimo-wątków | brak
Licznik CodeRabbit: coderabbit-rundy: #<N> <R> | brak (z `## Stan`; brak = 0)
Polecenia z celu dla ticketu: <tekst | brak>
Język wyjścia: <language>
```
## Testy — piramida po zależności, nie po warstwie

Poziomy: **unit** (bez bazy) · **integration-db** (`django_db`: ORM, endpointy, webhooki) ·
**integration** (żywe usługi, marker `integration`) · **e2e** (Playwright lub runner z repo).

- Zewnętrzne API płatności i podobne zawsze atrapą.
- **Nowe e2e** tylko gdy issue tego wymaga **i** runner jest w repo; inaczej „test przepływu
  na API”, tak nazwany w raporcie. Na VPS piszesz, ale nie uruchamiasz (guard) —
  „nieuruchomione lokalnie (VPS), weryfikuje CI” w raporcie i PR.
- Liczby **z komend**: `pytest <pliki> -m <marker> --co -q`; brak markerów → per plik
  + „brak markerów”. Do opisu PR i `Final report`.

## VPS (tylko przy `Host: vps` w nagłówku CTX)

- Krok odrzucony przez guard (`server-guard:`) → w CTX „tylko CI”, lokalnie idzie reszta.
- Nowa zależność: aktualizujesz **tylko lockfile** formą dozwoloną przez guard —
  `uv lock --no-build`, `uv add|remove <pkg> --no-sync --no-build`,
  `npm install --package-lock-only --ignore-scripts`,
  `pnpm install --lockfile-only --ignore-scripts`,
  `bun install` / `i` / `add` / `remove` z `--lockfile-only --ignore-scripts`. Każda inna forma to deny; nie
  obchodzisz go instalacją. Yarn nie ma trybu lock-only — nowa zależność yarn idzie
  przez `needs-local`.
- Gdy aktualizacja samego locka pada, bo paczka wymaga builda (uv „no build”,
  odpowiednik npm/pnpm/bun) → traktujesz to jak blokujący deny z #315: `needs-local`
  i komentarz z nazwą paczki i powodem. Nie próbujesz `uv sync` / pełnej instalacji.
- Brak CI = brak merge (krok 6 w `night-run-ticket`); nowe e2e: sekcja „Testy”.

## Zakazy

Nie skipujesz, nie usuwasz i nie osłabiasz testów. Nie `--no-verify`. Na `BASE` i inne
chronione gałęzie tylko merge PR po zielonym CI (przy `Host: local` bez CI: po bramkach
szybkich, krok 6 w `night-run-ticket`), nigdy push.

## Gdy ticket napotka problem

### Wyzwalacze

**needs-human** (przypadek A, B lub E): finding blokujący po ponownym sprawdzeniu Spec (E); otwarte wątki CodeRabbit po 6. rundzie (E); kryterium akceptacji niejasne albo sprzeczne
z ADR/`CONTEXT.md`; decyzja produktowa/prawna, której nie ma w issue ani docs; CI czerwone
po 3 próbach naprawy (wspólny sufit 3 rund naprawczych dla CI i reviewów orkiestratora, bez CodeRabbit) albo circuit breaker (identyczny błąd, flip-flop,
eksplozja diffa — krok 6 w `night-run-ticket`; po 2. rundzie albo po circuit breakerze najpierw Clean Slate (sufit 3, gdy jeszcze nie użyty i warunek bezpieczeństwa spełniony); rundy CodeRabbit nie uruchamiają Clean Slate); blokujący deny `server-guard:` (alternatywa nie wystarcza) albo
błąd builda przy aktualizacji samego lockfile → etykieta
`needs-local` zamiast `ready-for-human`; merge zablokowany przez ochronę gałęzi (wymagane review itp.) — PR
zostaje otwarty.

**halt** (przypadek C): czerwona gałąź bazowa, awaria CI/infrastruktury, brak sekretów,
nagłówek CTX bez znacznika `kit-ai night-ctx` albo `host=` ≠ `kit-ai host` (zgłasza watchdog).
U klientów bez `CronCreate` także limit API; w Claude Code limit API to przypadek D, nie C.

**Limity:** pauzy limitu bez limitu liczby, chyba że cel ustawia `pauzy: N` (po N-tej → halt C); 2 wznowienia na ticket (inne przyczyny) → needs-human.

### Clean Slate — hand-back `clean-slate`

**Clean Slate** przysługuje raz na ticket, po 2. nieudanej rundzie naprawczej albo po zadziałaniu circuit breakera (krok 6 w `night-run-ticket`):
1. Warunek bezpieczeństwa w worktree ticketu, po `git fetch origin`: `git status --porcelain` pusty
   i `git log origin/<branch>..HEAD` pusty; niespełniony warunek, błąd fetch albo komendy → needs-human bez resetu (przypadek A).
2. Reset: `git switch --no-overwrite-ignore --detach origin/<BASE>` (bez tej opcji git nadpisuje pliki
   ignorowane kolidujące z plikami śledzonymi w bazie); odmowa przełączenia (kolizja z plikiem ignorowanym) → needs-human bez resetu
   (przypadek A). Stary branch zostaje; jego PR zamykasz
   `gh pr close <PR> --comment "Zastąpiony przez Clean Slate"`. Nowy branch: `<typ>/<N>-<slug>-clean-slate`.
3. Świeży subagent ticketu od kroku 1, z modelem i effort z linii `Clean Slate:` w nagłówku CTX
   (`night-run.clean-slate` w Profilu: `provider`, `model`, `effort`). Brak sekcji = model jak dotąd.
   Do parametrów zlecenia dopisujesz linię „Clean Slate: użyty” i notatkę: „Poprzednie podejście zawiodło
   z powodu błędu X. Zacznij od czystej karty i unikaj ścieżki Y” (X i Y z hand-backu). Nowy subagent ma
   własny sufit 3 rund (rundy CodeRabbit mają osobny limit 6 rund i nie uruchamiają Clean Slate); drugiego Clean Slate nie ma, więc wyczerpany sufit przy czerwonym CI albo potwierdzonej, nierozwiązanej uwadze review orkiestratora → needs-human. Zlecenie nowego subagenta niesie też linię `coderabbit-rundy: #<N> <R>` z `## Stan` (liczba rund CodeRabbit wykonanych przed Clean Slate); nowy subagent liczy dalsze rundy od tej wartości, a limit 6 obejmuje cały ticket.

### Zasięg — zanim cokolwiek zrobisz

Które tickety z listy od tego zależą: wyłącznie jawnie, przez relację `blocked_by` (treść
issue / indeks w `CTX`), przechodnio: C blokowany przez B, a B przez A → po eskalacji A
tickety B i C są w zasięgu.

### Przypadki

- **A — tylko ten ticket:** raport na issue, bez merge, następny ticket.
- **B — część listy:** raport na issue + na każdym zależnym `needs-human: czeka na
  odpowiedzi z #N`; robisz tylko tickety spoza zasięgu.
- **C — wszystko:** `CronDelete` i stop watchdoga, potem `night-run halted: <powód>` na pierwszym issue,
  NIGHT-RUN REPORT, koniec.
- **D — pauza limitu (tylko Claude Code, 429 / „session limit”):** watchdog zapisał otwartą
  pauzę do `## Stan` i spał; budzi Cię powiadomienie „wznowienie po pauzie limitu”. Zamknij
  pauzę w `## Stan` (`do <teraz>`), sprawdź limit z celu (`pauzy: N`, przekroczony → halt C)
  i `koniec:` (teraz ≥ koniec → halt C); inaczej odnów watchdoga i wznów łańcuch od kroku
  z `## Stan`. Bez zmiany stanu w CTX nie wznawiaj ticketu, który już ma MERGED.
  Hand-back „pauza wykonawcy do <ISO>” (kod 75 wrappera): zapisz pauzę jak wyżej i odnów watchdoga;
  po wznowieniu ponowny `/headless` dla tego ticketu od kroku 2–3 w `night-run-ticket`. Pauza wykonawcy nie liczy się do wznowień ticketu.

- **E — finding blokujący** (Spec High niezałatwiony po ponownym sprawdzeniu albo otwarte wątki CodeRabbit po 6. rundzie): PR zostaje otwarty bez merge, issue zostaje otwarte, krok 8 w `night-run-ticket` pominięty. Komentarz na issue `needs-human: …` (zawiera link do PR) pisze orkiestrator. Etykieta: `ready-for-agent` → `ready-for-human`, zgodnie z regułą „pozostałe przypadki needs-human” niżej. Zasięg jak w „Zasięg”: zależne tickety dostają `needs-human: czeka na odpowiedzi z #N` (jak B), kolejne niezależne idą dalej.

Przy A, B i E, obok komentarza, przełącz stan ticketu (tylko gdy etykieta jest w repo; inaczej
sam komentarz; `--remove-label` tylko, gdy issue ma `ready-for-agent`):
- blokujący deny `server-guard:` → nadaj `needs-local` zamiast `ready-for-human` (nie zdejmuj
  `ready-for-agent`, `needs-local` to warunek wykonania):
  `gh issue edit <N> --add-label needs-local`
- brakujące dane od zgłaszającego → `needs-info` zamiast `ready-for-human`:
  `gh issue edit <N> --remove-label ready-for-agent --add-label needs-info`
- pozostałe przypadki needs-human:
  `gh issue edit <N> --remove-label ready-for-agent --add-label ready-for-human`
Merge nie rusza etykiet — zamknięte issue wypada z kolejki.

### Decyzja odwracalna — nie blokuj

Niejasność odwracalna (nazwa, kształt odpowiedzi endpointu, wartość domyślna), niedotykająca
pieniędzy, danych osobowych ani migracji usuwającej dane → najbezpieczniejsze założenie, jako
Q z przyjętą odpowiedzią w opisie PR. Blokuje tylko to, czego nie da się cofnąć.

### Format raportu needs-human (komentarz na issue)

```markdown
needs-human: <jedno zdanie, co stoi>

Q1. <pytanie>
- Opcje: a) … b) …
- Moja rekomendacja: … bo …
- Konsekwencja wyboru: …

Q2. …

Sprawdzone: <pliki, ADR, testy, komendy z wynikiem>
Wpływ: blokuje #X, #Y · nie blokuje #Z
Stan kodu: branch <nazwa> wypchnięty / porzucony
Wywołanie headless: <wiersz JSON z ostatniej linii wyjścia wrappera; bez wywołania → n/d>
```

### Karta eskalacji

Przy wyczerpanym sufcie rund albo circuit breakerze komentarz na issue to karta, nie zrzut logów:

```markdown
needs-human: <jedno zdanie, co stoi>

Co zaimplementowano: <zmiany i commity na branchu>
Na czym utknął: <dokładny błąd albo test>
Hipoteza: <prawdopodobna przyczyna, np. brak mocka, brak migracji>
PR: <link do pull requesta ticketu>
Wątek T3: <link wątku sesji ticketu; poza T3 Code → n/d>
```

Po needs-human orkiestrator od razu bierze kolejne niezależne issue; blokuje tylko relacja `blocked_by`.

## Tick watchdoga i crona (tylko Claude Code)

Gdy watchdog skończy się (anomalia, życie, wznowienie po pauzie, halt) albo cron wywoła tik,
robisz tik. To jedyny moment, w którym orkiestrator budzi się bez pracy do wykonania.
Najpierw zaległe powiadomienia, potem status subagenta z `## Stan` (`ListAgents`):

- watchdog `halt` (nagłówek CTX nie z generatora / rozjazd Host) → przypadek C z powodem
  z linii `halt:`; nie odnawiasz watchdoga;
- watchdog `życie` albo tik crona, a subagent działa → odnów watchdoga
  (`TaskStop` + start z `timeout: 7200000` + `watchdog:` w `## Stan`); cron bez zmian: jedna linia „ok”, koniec tiku;
- wznowienie po pauzie → zamknij pauzę w `## Stan`, potem jak w przypadku D i odpala watchdoga;
- hand-back „pauza wykonawcy do <ISO>” → jak w przypadku D (pauza w `## Stan`, odnów watchdoga);
  po wznowieniu ponowny `/headless` dla tego ticketu (krok 2–3 w `night-run-ticket`), pauza nie liczy się do wznowień ticketu;
- failed albo zakończony bez hand-backu → `SendMessage` na jego id; gdy się nie da → nowy
  subagent ticketu „kontynuuj z brancha `<branch>`: sprawdź `git log` / PR, dokończ od kroku X”, z linią `coderabbit-rundy: #<N> <R>` z `## Stan` w parametrach
  (fallback obowiązkowy — `SendMessage` po 429 może nie zadziałać);
- działa, ale bez zmian w gicie i PR dłużej niż próg anomalii watchdoga (§7) (`git log -1 --format=%ct` na branchu +
  ostatni check) → `TaskStop`, potem wznowienie jak wyżej;
- nic nie działa, a noc nieskończona (także przerwana tura orkiestratora) → łańcuch od kroku
  z `## Stan` (przypadek D).
- restart hosta / `kill` sesji: CTX i `## Stan` przetrwały w `~/.cache` — łańcuch od kroku
  z `## Stan`, praca od ostatniego commitu. Wznów sesję (`claude --continue`) albo nowy
  `/night-run`: czyta `## Stan`, `CronList` przed `CronCreate`, odpala watchdoga, gdy go nie ma.

## Pomiar kosztu ticketu (tylko Claude Code)

Po tickecie mierzysz koszt sesji pojedynczym poleceniem `kit-ai retro scan`:

```bash
kit-ai retro scan --session <sesja>
```

Wynik podaje koszt tokenów Sesji (tury, wejście, cache, wyjście, maks. kontekst) i zapisuje metryki w `${XDG_CACHE_HOME:-~/.cache}/kit-ai/retro/<repo>/<sesja>.jsonl` jako jedyne źródło kosztu Sesji (#409).
Model per krok: `meta.json` subagenta (`$HOME/.claude/projects/<projekt>/<sesja>/subagents/agent-<id>.meta.json`) i transkrypt (`message.model`) → kolumna `Model` w NIGHT-RUN REPORT; fallback jako `<komenda>: skill (sesja)`.
Czas = wall-clock. Inny klient → „brak transkryptu”. Z `/headless` albo review z argumentów dopisz „koszt bez wykonawcy headless i review w sesji głównej”.

**Orkiestrator:** to samo wywołanie `kit-ai retro scan --session <sesja_orkiestratora>` na sesji głównej; do raportu idą jego tury i `cache_read`.

## Retro

Ostatni krok przed raportem, raz na noc. Nie blokuje raportu: gdy skan albo klasyfikacja się nie uda, wpisz `Retro: pominięte — <powód>` i idź dalej.

1. Skan sesji i przebiegów headless tego repo od daty nocy (`YYYY-MM-DD` z nazwy katalogu CTX):
   `kit-ai retro scan --since <YYYY-MM-DD>`. Wynik podaje liczby i katalog z zapisami JSONL.
2. Zero znalezisk → `Retro: 0 znalezisk.` i koniec kroku.
3. Są znaleziska → uruchom skill `/kit-retro` na zapisach z tej nocy: pliki `*.jsonl` z katalogu z kroku 1, których `scanned_at` jest z tego przebiegu. Tabelę z ocenami zostaw w rozmowie, nie zapisuj jej do pliku.
4. Do raportu wpisz linię `Retro: …` z liczbami per kategoria (w bloku raportu poniżej).

Propozycje z tego kroku (kit, projekt, agent, zewnętrzne) idą do rozmowy i raportu. Issue zakłada człowiek po akceptacji (`/create-task`), więc nie zakładasz issue ani nie piszesz w GitHubie z tego kroku.

## NIGHT-RUN REPORT — ostatnia wiadomość

Zaczynasz od `CronDelete` i zatrzymania watchdoga. Pod `/goal` raport i dowody muszą paść
w rozmowie (warunek sprawdza transkrypt).

Przed wysłaniem raportu:
1. Przeczytaj wszystkie pliki `$CTX_DIR/handoff-*.md` z katalogu nocy i dołącz ich treść jako sekcję `## Przekazania` (podsekcja per issue: `### #<N>`) na końcu raportu za wszystkimi sekcjami `###` (brak handoffów → „brak”).
2. Uruchom `node .ai/headless.mjs --report --ctx "$CTX_DIR"` — wypisz wynik jako `## HEADLESS REPORT` pod NIGHT-RUN REPORT (wrapper kasuje bufor dopiero po udanym wypisaniu). Pliki zaległych wywołań z kroku 6 dopisz jako `## Zaległe wywołania`. Bez wywołań wrapper sam wypisze „brak wywołań headless”.

```markdown
## NIGHT-RUN REPORT
Baza: <BASE> — <powód>
Host: <vps | local> (z `kit-ai host`; nagłówek CTX)
Sufiks CTX: <brak / z celu: <sufiks> / automatyczny: <sufiks> (noc w toku w <katalog>)>
Bramki szybkie: <lista> (źródło: CI / overlay / założenie) · pełny zestaw: CI
Model ticketu: <MODEL> albo per ticket: #N <model> — <powód>
Wykonawca: <EXEC / subagent / subagent (brak /headless)> · Review: <skille z argumentów / domyślne>
Modele kroków: <git-start: haiku · git-commit: haiku · git-end: haiku · review: sonnet>
Fallback modelu: <komenda: skill / inline (sesja) — gdy brak agenta>
Pauzy limitu: <liczba> (przestój <od>–<do>, reset: <godzina z komunikatu / brak>)
Odnowienia watchdoga: <liczba> (powód: życie / pauza / ręcznie) · Tiki crona: <liczba> (co 4 h)
Wybudzenia orkiestratora: <liczba> (watchdog: anomalia / pauza / życie; cron: tik) · Ostatnie wznowienie: <godzina>
Wznowienia per ticket: <#N: liczba>
Orkiestrator (tylko Claude Code): <tury> tur / <cache_read> cache_read (sesja główna)
Retro: <liczba znalezisk> (kit <n> · projekt <n> · agent <n> · zewnętrzne <n>) · skan od <YYYY-MM-DD> · pominięte: <powód albo —>

| Ticket | Stan | Wykonawca | Review | Model | Dowód | Koszt (tury / cache_read / output / kontekst / czas) |
| --- | --- | --- | --- | --- | --- | --- |
| #N | MERGED | opencode | /review-edge | git-start: haiku · git-commit: haiku · git-end: haiku · review-bugbot: sonnet | `gh pr view <PR> --json state` → MERGED; <link Final report> | 58 / 6.1M / 41k / 164k / 20 min |
| #M | needs-human → ready-for-human | subagent | domyślne | git-end: skill (sesja) | <link do komentarza> | … |
| #K | MERGED | opencode → przejęte (haiku, limit) | /review-edge | przejęcie: haiku (Profil) · git-end: haiku | `gh pr view <PR> --json state` → MERGED; <link Final report> | 40 / 3.2M / 25k / 120k / 14 min |
| #J | skipped: needs-local / skipped: <etykieta> / skipped: w innej nocy <katalog> / skipped: zależność #N w innej nocy <katalog> / halted | — | — | — | etykieta stanu, inna noc albo link do komentarza halted | — |

Raport per krok: kolumny Wykonawca i Model odnotowują transport (natywna delegacja / `/headless` / subagent), użyty model oraz przejścia na zapas (np. `<model-1> → <model-2> (limit)`). Koszt delegata `n/a`, gdy transport nie zostawia logów.

Kolumna Wykonawca: gdy kod 75 został przejęty, zapisz `opencode → przejęte (<model>, limit)` (zamiast `opencode`
nazwa wykonawcy z `EXEC`); model i źródło (cel / Profil / sesja) przepisz z hand-backu do kolumny Model jako
`przejęcie: <model> (<źródło>)`.

Założenia: <co przyjęto bez danych z repo; odnotuj ewentualne tłumaczenie /code-review na /review>
Pomiar per agent: <wiersze ze snippetu>
Raporty review i findingi w podsumowaniu nocy podlegają tej samej regule języka: nagłówki sekcji, etykiety werdyktów i podsumowanie w języku Profilu (np. `## Standardy` / `## Spec`, `TWARDE` / `OCENA`); nagłówek tabeli `Severity | Location | Finding | Fix` i wartości Severity bez zmian, cytaty kodu, identyfikatory i ścieżki bez zmian.

### Nowe ekrany
| PR | Route |
| --- | --- |
| #<PR> | <plik dodany w routes-web / routes-mobile> |

## Przekazania
<dla każdego handoff-*.md sekcja ### #<N> z treścią pliku (fakty dla następcy: modele, serwisy, endpointy, migracje, zmienione kontrakty); brak handoffów → „brak”>
```

**Kontrakt raportu:** przed wysłaniem sprawdź każde pole powyższego bloku. Pole, którego nie dotyczy (np. Sufiks CTX bez sufiksu → `brak`, `Pauzy limitu`, `Orkiestrator` poza Claude Code, `Wznowienia per ticket` bez wznowień), dostaje `n/d — <powód>` (lub `brak`). Dane, których brak mimo wysiłku, dostają `brak danych: <powód>`. Pola nie wolno pominąć.

**Nowe ekrany:** pliki dodane w katalogach `routes-web` / `routes-mobile` (`.ai/project.md
## Ścieżki`) przez PR-y zmergowane tej nocy — tylko pliki nowe:
`gh api repos/<owner>/<repo>/pulls/<PR>/files --jq '.[] | select(.status=="added") | .filename'`
przeciw tym ścieżkom. Lista do decyzji człowieka; issue nie zakładasz. Brak `routes-*` →
„brak routes-* w ## Ścieżki”.

**Follow-up „zaprojektuj layout”** (sesję designu robi człowiek w Claude Code — Claude Design,
`/design-sync`; przebieg w `docs/agents/design-handoff.md`). Zmergowany ticket **bez**
`design: *` dodał plik w `routes-web` / `routes-mobile` → po merge'u zakładasz issue:

- tytuł: `refactor: design layout for <ekran>` (`refactor` ↔ `type: refactor` ↔ branch
  `refactor/N-…`);
- body: link do PR, route, komponenty sekcji z diffa, odnośnik do formatu speca w bundlu
  (`stack:frontend:ui-structure`), linia „Sesja designu: Claude Code”;
- etykiety (tylko istniejące w `gh label list --limit 200`): `design: layout`,
  `ready-for-human`, `type: refactor`, `scope: frontend:web` albo `scope: frontend:mobile`.

Brak `routes-*`, etykiety `design: layout` albo `--dry-run` → tylko wiersz w „Nowe ekrany”;
tam kolumna `Follow-up` z numerem issue.

Każdy ticket z listy ma w tabeli dokładnie jeden wiersz. Brak dowodu = ticket nie jest skończony.
