---
mode: "agent"
description: "Autonomiczna nocna praca na liście issue (samodzielnie, /goal opcjonalny) — orkiestrator, na każdy ticket świeży subagent (git-start → test-first → PR → merge) albo wykonawca /headless, review na diffie (także skille review z argumentów), needs-human zamiast pytań, na końcu NIGHT-RUN REPORT. Użyj TYLKO gdy cel lub użytkownik wprost nazywa /night-run. Wywołuj jako /night-run."
---

Język odpowiedzi, prompt dla subagenta i hand-back: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

# /night-run — lista issue bez człowieka

Przerabiasz listę issue z argumentów albo celu (bez listy — kolejkę `ready-for-agent`),
jeden po drugim, aż każde jest **zmergowane** albo ma komentarz **needs-human**. Człowiek
śpi. Issue są wygrillowane za dnia — projekt jest w ich treści, Twoja rola to wykonanie.

## Zasady nadrzędne

- **Jesteś orkiestratorem w głównej sesji, nigdy wykonawcą ticketu.** Ticket robi subagent
  ticketu, review osobny świeży subagent albo skille review z argumentów. Sam nie czytasz
  kodu i nie odpalasz testów: Twój kontekst ma zostać mały.
- **Komendy kitu uruchamiasz według klienta** (`/git-*`, `/review-*` i inne z argumentów
  lub promptu ticketu), by działały na modelu z frontmattera agenta, nie sesji:
  - **Claude Code:** agent o nazwie komendy jest w `.claude/agents/<nazwa>.md` → **Agent**
    tego typu bez parametru `model` (model bierze się z frontmattera); brak agenta →
    **Skill**. Subagent uruchamia kolejne komendy-agentów (do 3 poziomów,
    `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), więc `/git-*` zostają wewnątrz subagenta
    ticketu, a orkiestrator nie dostaje z nich tur. Sam `/night-run` działa w głównej
    sesji (w Claude uruchamiany Skillem, nie Agentem): potrzebuje `CronCreate` i watchdoga.
  - **opencode:** komenda `/<nazwa>` z `.opencode/command/` (model z frontmattera, gdy
    Profil ma `models.opencode`); brak `model:` → model sesji.
  - **klienci bez modelu per agent** (Cursor, Codex, VS Code, Kiro, Kilo, Antigravity) →
    bez zmian: inline albo skill na modelu sesji.
  - **Model komendy z celu** — tylko jawna forma `<komenda>: model <nazwa>` (np.
    `git-start: model haiku`) nadpisuje frontmatter tej komendy tam, gdzie klient ma
    parametr modelu. Samo `model: <nazwa>` ustawia wyłącznie model ticketu (niżej).
  - Brak agenta/komendy (fallback na Skill albo inline) zapisujesz w hand-backu
    i w NIGHT-RUN REPORT.
- Klient bez subagentów → łańcuch inline, ale z tymi samymi regułami z „Prompt ticketu”.
- **Polecenia z tekstu celu mają pierwszeństwo** przed tą procedurą (np. „bez merge, same PR-y”,
  „#155 pomiń PDF”, inny próg dużego ticketu; `watchdog: próg N, życie M` — progi watchdoga, §7).
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
/night-run #N1 #N2 [/headless <wykonawca> [--model …] [--timeout …] [--heartbeat …] "<treść>"] [/review-* …]
```

`/goal` opcjonalny: noc działa sama. Wznawianie nocy = watchdog `.ai/night-run-watchdog.sh`
+ tik `CronCreate` co 4 h (krok 7), nie warunek `/goal`. Domyślnie bez limitu pauz i bez
końca nocy; cel z `pauzy: N` (po N-tej pauzie halt C) albo `koniec: HH:MM` (teraz ≥ koniec →
halt C) je włącza. Pod `/goal` jego tekst to cel (niżej „Polecenia z tekstu celu”).

- **Lista issue** — `#N` przed pierwszym argumentem z `/`. Brak → kolejka (krok 4).
- **`/headless <wykonawca> [flagi] "<treść>"`** — implementację ticketu robi wykonawca
  headless (`EXEC`, `FLAGI`, `TREŚĆ`). Argument kończy zamykający cudzysłów treści
  (cudzysłów obowiązkowy); treść i flagi wrappera przekazujesz bez zmian (`--timeout`
  domyślnie 30 min — większy ticket potrzebuje więcej). Wariant promptu w „Prompt ticketu”.
  `EXEC` sprawdzasz raz na starcie nocy, przed pierwszym ticketem:
  - klient bez `/headless` (brak skilla/komendy `headless` albo `.ai/headless.mjs`) →
    fallback: implementacja subagentem jak bez argumentu, w raporcie
    `wykonawca: subagent (brak /headless)`;
  - `EXEC` spoza `clients:` w `.ai/project.profile.yaml` albo równy hostowi (klient tej
    sesji) → nieznany wykonawca → needs-human na starcie nocy — żaden ticket nie startuje,
    NIGHT-RUN REPORT z `needs-human: nieznany wykonawca <nazwa>`, koniec.
- **Skille review z argumentów** — jeden lub kilka (`/review-edge`, `/review-bugbot`,
  `/review-security`, `/code-review --fix`, …), z ich własnymi flagami. Bez nich → review jak dziś (łańcuch, krok 2).
  Każdy sprawdzasz raz na starcie nocy na liście skilli klienta:
  nieznany skill review → needs-human na starcie nocy — żaden ticket nie startuje,
  NIGHT-RUN REPORT z `needs-human: nieznany skill review <nazwa>`, koniec.
  Gdy skill to `/code-review`, przekazujesz mu numer ticketu (`/code-review <N>` z flagami) —
  jego oś Spec czyta issue; pozostałe skille review dostają tylko diff.

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
Czerwony → **halt** (przypadek C). Brak CI → bramki szybkie na `origin/$BASE` odpala krótki subagent.

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

### 5. Kolejność

Per issue: `gh api repos/<owner>/<repo>/issues/<N>/dependencies/blocked_by --jq '.[].number'`.
Kolejność topologiczna, przy remisie z celu. Otwarty blokujący spoza listy → needs-human
„zablokowany przez #X spoza listy”.

### 6. Plik kontekstu nocy

Katalog nocy: `CTX_DIR=~/.cache/night-run-<repo>-<data>/` — `CTX=$CTX_DIR/context.md`,
raz na noc, poniżej ~150 linii, sekcje. Wszędzie (prompt ticketu, `CronCreate`, Read/Write)
pełna ścieżka z `$HOME` zamiast `~`. `~/.cache` przeżywa restart hosta, `/tmp` nie —
nigdy tam (ani CTX, ani `## Stan`, ani logi pracy w tle).

- **Nagłówek:** BASE, `Host: vps | local` (ustalany raz: bundle z MCP `get_bundle`
  zawiera `infra:vps-lightweight` → `vps`, inaczej `local`), bramki szybkie, „pełny zestaw
  testów: tylko CI”.
- **Mapa aplikacji:** katalog → co w nim jest, 1 linia.
- **Konwencje:** same reguły z AGENTS.md, BUGBOT.md, `.ai/project.md`.
- **Pułapki toolchainu:** z pamięci projektu (CLAUDE.md, notatki agenta) i overlay; brak → „brak danych”.
- **Przekazanie:** `### #N` + modele, serwisy, endpointy, migracje z hand-backu. Dopisujesz
  **Ty** po każdym MERGED.
- **Stan (`## Stan` na końcu CTX):** linie `krok: ticket|review|resume|ci|koniec`,
  `subagent: <id>` (transkrypt czyta watchdog), `watchdog: <id zadania w tle>`, `wznowienia
  per ticket`, pauzy limitu: otwarta `pauza limitu od <ts>; wznowienie <ts> (epoch N)` (zapisuje
  ją watchdog), zamknięta `pauza limitu od <ts> do <ts>` (zamyka ją watchdog po wznowieniu; ty tylko sprawdzasz). Nadpisujesz **Ty**
  przy każdej zmianie kroku; tik czyta ją jako pierwszą.

### 7. Watchdog i cron (tylko Claude Code)

Orkiestrator budzi się tylko wtedy, gdy jest co robić. Tik kosztuje turę i cały kontekst,
więc nie jest mechanizmem oczekiwania.

- **Watchdog w tle (`.ai/night-run-watchdog.sh`, instalowany przy kliencie claude):** Bash
  `run_in_background` z pełną ścieżką repo: `bash "$(git rev-parse --show-toplevel)/.ai/night-run-watchdog.sh" "$CTX" 60 110`
  (domyślnie próg anomalii 60 min, życie 110 min — poniżej twardych 2 h Bash w tle; cel
  `watchdog: próg N, życie M` (min) zamienia te liczby, życie ≤ 110). Skrypt śpi i
  **nie budzi orkiestratora**, dopóki idzie praca: postępem jest zapis w katalogu CTX albo
  w transkrypcie subagenta z `subagent: <id>`. Kończy się, czyli budzi orkiestratora
  powiadomieniem o zakończeniu, tylko gdy:
  - exit 1 `anomalia` — brak postępu > 60 min (subagent failed/bez hand-backu też → tik);
  - exit 0 `życie` — minęło 110 min → odnów (niżej);
  - exit 0 `koniec nocy` — w `## Stan` jest `krok: koniec`;
  - exit 0 `wznowienie po pauzie limitu` — wykrył komunikat limitu (429 / „session limit”)
    w transkrypcie subagenta, zapisał otwartą pauzę do `## Stan` i spał do godziny resetu
    z komunikatu + 5 min (bez godziny: co 30 min, przedłużane, gdy przyjdzie nowa linia
    limitu). Zamyka pauzę `do <ts>` sam watchdog. Pauza limitu **nie jest** anomalią.
- **Odnowienie w tej samej turze co start:** przy starcie ticketu, review, wznowienia i każdym
  hand-backu, w tym samym wywołaniu narzędzi co Agent/Bash: `TaskStop` starego watchdoga
  (`watchdog:` z `## Stan`, jeśli żyje), start nowego `run_in_background`, zapis
  `watchdog: <id>` do `## Stan`. Po wybudzeniu z pauzy sprawdź, że otwarta pauza ma
  już `do <ts>` (zamyka ją watchdog); jeśli nie — dopisz `pauza limitu od X do <teraz>`, potem odnów.
- **Jeden watchdog naraz:** przed odnowieniem sprawdź listę zadań w tle; działa → `TaskStop`,
  nie dubluj.
- **Cron co 4 h jako siatka:** cron łapie to, co ginie razem z sesją (watchdog) i pauzę
  dłuższą niż życie watchdoga. **`CronList` przed `CronCreate`** — obowiązkowo, także przy wznowieniu sesji (cron przeżywa wznowienie i działa obok nowego): jest już cron o tym
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

1. **Subagent ticketu** (świeży, `model: MODEL`): `N`, `BASE`, `CTX` + „Prompt ticketu”
   dosłownie. `## Stan` w `CTX` (ticket, id, krok `ticket`) nadpisujesz **w tym samym
   wywołaniu narzędzi co uruchomienie subagenta** (Claude Code: razem z odnowieniem watchdoga, sekcja 7), nie w osobnej turze — każda
   tura czyta cały kontekst. Wraca z hand-backiem i niewypchniętym branchem; wtedy
   poprawiasz `## Stan`, jeśli hand-back zmienia krok. Z `/headless` kroki 2–3 promptu
   zastępujesz linią „2–3. (z `/headless`)” z wpisanymi `EXEC`, `FLAGI` i `TREŚĆ` oraz dwiema
   rozstrzygniętymi wartościami: `LIMIT` (`przejmij` / `czekaj`; z tekstu celu `limit:`, brak → `przejmij`)
   i `PRZEJĘCIE` (alias + źródło): (a) tekst celu `przejęcie: <alias>` (tylko ta noc), (b) Profil
   `models.claude.takeover`, (c) brak → `sesja` (model sesji). Alias z celu spoza `haiku`/`sonnet`/
   `opus`/`fable` → `sesja` z wpisem w raporcie („nieznany alias przejęcia”). Bez `/headless` tę linię usuwasz.
2. **Review.** Przed review — w obu wariantach — nadpisz `## Stan` (krok `review`; przy
   skillach z argumentów także nazwa bieżącego skilla), w tym samym wywołaniu narzędzi co
   uruchomienie review. Ze skillami review z argumentów: uruchamiasz je **Ty** według reguły
   „Komendy kitu uruchamiasz według klienta” (np. `review-bugbot` na modelu z
   frontmattera), każdy na `git diff origin/$BASE...HEAD` brancha ticketu, w kolejności
   z argumentów. `/code-review` wołasz z numerem ticketu (`/code-review <N>`), bo jego oś
   Spec czyta issue. Od skilla bierzesz tylko tabelę niżej; skill z `--fix` poprawia sam — subagent ticketu po
   wznowieniu zbiera to `/git-commit`.
   Bez argumentów — **subagent review** (zawsze nowy): „Review `git diff origin/$BASE...HEAD` na `<branch>`:
   `/review-bugbot` + `/review-backend` i/lub `/review-frontend` wg diffa. Czytaj tylko diff
   i dotknięte pliki, zakresami. Zwróć `Severity | Location | Finding | Fix` +
   potwierdzony/niepewny. Nie edytuj.” Zapisz jego id w `## Stan`.
3. **Wznów subagenta ticketu** (w Claude `SendMessage` na jego id, nie nowy start) z
   findingami: potwierdzone → poprawka + test; niepewne → opis PR. Review z kroku 2 **jest**
   potwierdzeniem review dla `/git-end`. Przed wznowieniem nadpisz `## Stan` (krok `resume`),
   przed CI — krok `ci`. Dalej kroki 6–8 promptu.
4. Sprawdź dowód sam: `gh pr view <PR> --json state` → `MERGED`.
5. Dopisz „Przekazanie” do `CTX`, policz koszt ticketu (sekcja „Pomiar”),
   `git checkout $BASE && git pull` przed następnym ticketem.

Hand-back needs-human albo halt od subagenta → sekcja „Gdy ticket napotka problem”.

## Prompt ticketu

Przekazujesz go subagentowi dosłownie, poza wyborem wariantu kroków 2–3 (łańcuch, krok 1).
Komendy kitu w krokach uruchamiasz według reguły „Komendy kitu uruchamiasz według klienta”.

```markdown
Ticket #<N>, baza <BASE>. Kontekst projektu: <CTX> — przeczytaj go najpierw, zamiast
AGENTS.md, BUGBOT.md i ADR-ów. ADR czytasz tylko wtedy, gdy issue go wskazuje.
Specyfikacja = body issue + komentarz z briefem agenta (AGENT-BRIEF od `/triage`), jeśli jest:
`gh issue view <N> --comments`.
Frontend: po kroku 1 plik `docs/design/<N>.md` jest w drzewie (z <BASE> albo z istniejącego
brancha issue) → layout wyłącznie według `docs/design/<N>.md`; rozbieżność = hand-back
needs-human. Brak speca → layout domyślny z bundla (`stack:frontend:ui-structure`).

Język odpowiedzi, statusy i hand-back: z MCP `get_language` (Profil), niezależnie od języka wejścia.

Kroki:
1. `/git-start #<N>`. Branch musi wychodzić z <BASE>; inaczej
   `gh issue develop <N> --name <typ>/<N>-<slug> --base <BASE> --checkout`.
2–3. (z `/headless`) `/headless <wykonawca> [flagi] "<treść>"` z flagami i treścią bez zmian —
   reguły ticketu i numer dokleja stopka wrappera. Sam nie piszesz kodu: pilnujesz wrappera
   (wzorzec „Praca w tle”), sprawdzasz raport (`git stash list`, `git log`). Wrapper pada
   → maks. 2 próby, potem needs-human. Dalej kroki 4–5.
   Kod wyjścia wrappera `75` = pauza limitu wykonawcy (linia `PAUSE=rate-limit reset=<ISO|brak>`
   w raporcie) — nie jest próbą: nie liczy się do 2 prób i nie jest needs-human. Nie wykonałeś
   jeszcze pracy: oddajesz hand-back „pauza wykonawcy do <ISO>” (gdy `reset=brak`, wpisz «nieznana»)
   i kończysz turę. Orkiestrator zapisuje pauzę w `## Stan` jako
   `pauza limitu od <ts>; wznowienie <ISO+5 min> (epoch N)` (format watchdoga). Gdy `reset=brak`:
   `wznowienie <teraz+30 min> (epoch N)` — kolejne sprawdzenie, nie zgadywanie godziny.
   ISO+5 min liczy orkiestrator; linię zamyka sam watchdog (watchdog dopisuje `do`). Po wznowieniu wznawiasz
   ten sam ticket od kroku 2–3 (`/headless` od nowa, ten sam branch).
   **Przejęcie zamiast czekania (#257).** Wartości `LIMIT` i `PRZEJĘCIE` z linii kroku 2–3
   ustawia orkiestrator (łańcuch, krok 1). `LIMIT: czekaj` → zostaje powyższa pauza do resetu
   (zachowanie z #250). `LIMIT: przejmij` (domyślny) → kod 75 nie czeka: uruchamiasz
   **subagenta przejęcia** (Agent z parametrem `model` = model z `PRZEJĘCIE`) z DOSŁOWNIE tą samą treścią z
   cudzysłowu `/headless <wykonawca> [flagi] "<treść>"` oraz raportem wrappera (commity,
   `git status`, ostatnie linie) i stanem brancha. Effort: bez parametru — subagent przejęcia
   dziedziczy effort sesji. Komendy z treści: Skill, gdy dostępny; skill z `disable-model-invocation`
   przez odczyt jego `SKILL.md` i wykonanie treści. Przejęcie nie rusza niezacommitowanych zmian
   (bez `git checkout`/`git stash`), commituje lokalnie (`git commit`); przy limicie zagnieżdżenia 3
   (orkiestrator → ticket → przejęcie) `/git-commit`, review i `/git-end` dalej robi subagent ticketu.
   Przejęcie, które pada (błąd albo kolejny limit) → needs-human; nie liczy się jako druga próba wrappera. W hand-backu podaj model przejęcia i jego źródło (cel / Profil / sesja).
2. Duży ticket (>3 kryteria akceptacji albo >1 aplikacja/pakiet): plan 5–10 kroków.
3. Test-first: test czerwony → kod → zielony → commit. Commit po każdym zielonym kroku
   (nie czekasz z commitem do końca ticketu — restart hosta w nocy nie gubi pracy).
   Końcowy `/git-commit` z kroku 5 zostaje.
4. Lokalnie tylko testy dotknięte ticketem + bramki szybkie z <CTX>. Pełny zestaw: CI.
   Na VPS (`Host: vps` w nagłówku <CTX>) `uv run` zawsze z `--no-sync`.
5. `/git-commit`. Nie pushujesz. Oddajesz hand-back.
--- po wznowieniu ---
6. Poprawki z review, potem `/git-end` (review zrobione, nie czekaj). W prompcie `/git-end`
   przekazujesz treść opisu PR: testy, założenia jako Q z odpowiedzią, niepewne findingi. **CI
   pilnuje agent `git-end`:** `sleep 20; gh pr checks <PR> --watch` wzorcem „Praca w tle” (`sleep`,
   bo checki rejestrują się z opóźnieniem). `EXIT` ≠ 0 i w logu `no checks reported` → powtórz raz
   po minucie; nadal brak → przy `Host: local` merge po bramkach szybkich (zapis w `Final report`);
   przy `Host: vps` brak CI = brak merge: kroki 7–8 pomijasz, PR otwarty, hand-back needs-human
   „brak CI na <BASE>”, przypadek A. Inne `EXIT` ≠ 0 → `/git-end` nie naprawia kodu: wraca
   hand-backiem z logiem CI, a Ty (subagent ticketu) poprawiasz i ponawiasz `/git-end` (maks. 2
   próby); nadal czerwone → needs-human.
7. `gh pr merge <PR> --merge`.
8. Jeden raport: komentarz na PR `## Final report (night-run) — #<N>`. Na issue tylko link
   do niego, potem `gh issue close <N>` (`Closes` nie zamyka przy merge na niedomyślną).

Reguły:
- Plik > ~150 linii czytasz zakresami: `codegraph explore` (gdy jest `.codegraph/`) albo
  `grep -n` + `sed -n X,Yp`, wiele odczytów w jednej komendzie. Nigdy całego pliku: ani
  `cat` / `xargs cat`, ani Read bez `offset`/`limit`.
- Bez skilli procesowych (writing-plans, tdd, verification, review-*); wolno `/git-*`, `/headless`.
- Deny od guarda kita (`server-guard:` / `git-guard:` w powodzie) to reguła, nie awaria:
  nie obchodzisz jej (ta sama komenda spod taska wpisana wprost, `bash -c`, własny skrypt,
  inny interpreter), nie liczysz jej do prób naprawy. Wolno użyć alternatywy wskazanej
  w powodzie deny (np. `uv run --no-sync`, `UV_NO_SYNC=1`, `git stash`). Deny
  `server-guard:` → komenda trafia do raportu jako „tylko CI”; deny `git-guard:` → zapis
  w raporcie, a gdy bez tej komendy nie da się skończyć — needs-human.
- Praca w tle (CI, dłuższy `pytest`): od razu w tle (w Claude `run_in_background`), jeden
  wzorzec, bez pipe (`| tee` gubi exit code): `<cmd> > <log> 2>&1; echo "EXIT=$?" >> <log>`.
  `<log>` w katalogu <CTX> (`<katalog CTX>/<nazwa>.log`), nigdy w `/tmp` — po restarcie hosta
  wznawiasz po nim pracę.
  Koniec = powiadomienie o zakończeniu albo linia `EXIT=` w logu; wynik = jej wartość. Nie czekasz na tekst narzędzia (`passed`, `All checks…`) ani na stan procesu
  (`ps`, `pgrep`, `kill -0`) — taka pętla wisi bez końca albo staje na prośbie o zgodę.
  Przed hand-backiem żadne Twoje zadanie w tle nie działa, zbędne kończysz.
  (tylko Claude Code) Nie kończysz tury, dopóki `/headless` działa w tle — inaczej
  orkiestrator dostaje powiadomienie „is waiting on its own background work” i płaci turę.
  Czekasz na pierwszoplanowym Bash z limitem czasu, który blokuje do linii `EXIT=` w logu
  wrappera (`timeout 600 sh -c 'until grep -q ^EXIT= <log>; do sleep 5; done'`), i powtarzasz
  go do skutku. To dozwolone tylko tutaj, u subagenta ticketu; orkiestrator nie blokuje się
  i na powiadomienia nie reaguje narzędziami.
- Zero pytań do człowieka. Needs-human albo halt → wypchnij branch, hand-back z Q1/Q2
  (komentarz na issue daje orkiestrator).

Hand-back (bez streszczania pracy): stan (do review / MERGED / needs-human / halt); branch, PR,
link `Final report`; testy unit/x, integration-db/y, integration/z, e2e/w (z komend);
dodane modele, serwisy, endpointy, migracje; założenia; model: <per komenda: agent
<nazwa> (<model>) / skill / inline — fallback przy braku agenta>.
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
- Brak CI = brak merge (krok 6 promptu); nowe e2e: sekcja „Testy”.

## Zakazy

Nie skipujesz, nie usuwasz i nie osłabiasz testów. Nie `--no-verify`. Na `BASE` i inne
chronione gałęzie tylko merge PR po zielonym CI (przy `Host: local` bez CI: po bramkach
szybkich, krok 6 promptu), nigdy push.

## Gdy ticket napotka problem

### Wyzwalacze

**needs-human** (przypadek A lub B): kryterium akceptacji niejasne albo sprzeczne
z ADR/`CONTEXT.md`; decyzja produktowa/prawna, której nie ma w issue ani docs; CI czerwone
po 2 próbach naprawy; merge zablokowany przez ochronę gałęzi (wymagane review itp.) — PR
zostaje otwarty.

**halt** (przypadek C): czerwona gałąź bazowa, awaria CI/infrastruktury, brak sekretów.
U klientów bez `CronCreate` także limit API; w Claude Code limit API to przypadek D, nie C.

**Limity:** pauzy limitu bez limitu liczby, chyba że cel ustawia `pauzy: N` (po N-tej → halt C); 2 wznowienia na ticket (inne przyczyny) → needs-human.

### Zasięg — zanim cokolwiek zrobisz

Które tickety z listy od tego zależą: jawnie (blocked-by) i niejawnie (zmieniony model,
pole, serwis, endpoint, z którego korzysta inny — treść issue + „Przekazanie” w `CTX`).

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
  po wznowieniu ponowny `/headless` dla tego ticketu od kroku 2–3. Pauza wykonawcy nie liczy się do wznowień ticketu.

Przy A i B, obok komentarza, przełącz stan ticketu (tylko gdy etykieta jest w repo; inaczej
sam komentarz; `--remove-label` tylko, gdy issue ma `ready-for-agent`):
`gh issue edit <N> --remove-label ready-for-agent --add-label ready-for-human`
(`needs-info` zamiast `ready-for-human`, gdy stoi na brakujących danych od zgłaszającego,
nie na decyzji). Merge nie rusza etykiet — zamknięte issue wypada z kolejki.

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
```

## Tick watchdoga i crona (tylko Claude Code)

Gdy watchdog skończy się (anomalia, życie, wznowienie po pauzie) albo cron wywoła tik,
robisz tik. To jedyny moment, w którym orkiestrator budzi się bez pracy do wykonania.
Najpierw zaległe powiadomienia, potem status subagenta z `## Stan` (`ListAgents`):

- watchdog `życie` albo tik crona, a subagent działa → odnów watchdoga
  (`TaskStop` + start + `watchdog:` w `## Stan`); cron bez zmian: jedna linia „ok”, koniec tiku;
- wznowienie po pauzie → zamknij pauzę w `## Stan`, potem jak w przypadku D i odpala watchdoga;
- hand-back „pauza wykonawcy do <ISO>” → jak w przypadku D (pauza w `## Stan`, odnów watchdoga);
  po wznowieniu ponowny `/headless` dla tego ticketu (krok 2–3), pauza nie liczy się do wznowień ticketu;
- failed albo zakończony bez hand-backu → `SendMessage` na jego id; gdy się nie da → nowy
  subagent ticketu „kontynuuj z brancha `<branch>`: sprawdź `git log` / PR, dokończ od kroku X”
  (fallback obowiązkowy — `SendMessage` po 429 może nie zadziałać);
- działa, ale bez zmian w gicie i PR dłużej niż próg anomalii watchdoga (§7) (`git log -1 --format=%ct` na branchu +
  ostatni check) → `TaskStop`, potem wznowienie jak wyżej;
- nic nie działa, a noc nieskończona (także przerwana tura orkiestratora) → łańcuch od kroku
  z `## Stan` (przypadek D).
- restart hosta / `kill` sesji: CTX i `## Stan` przetrwały w `~/.cache` — łańcuch od kroku
  z `## Stan`, praca od ostatniego commitu. Wznów sesję (`claude --continue`) albo nowy
  `/night-run`: czyta `## Stan`, `CronList` przed `CronCreate`, odpala watchdoga, gdy go nie ma.

## Pomiar kosztu ticketu (tylko Claude Code)

Po tickecie liczysz jego subagentów (ticket + review) — `python3`, bez `jq`. Wiersz: agent | model | tury | input | cache_creation | cache_read | output | maks. kontekst | czas.
Model per krok: `meta.json` subagenta
(`$HOME/.claude/projects/<projekt>/<sesja>/subagents/agent-<id>.meta.json`) i transkrypt
(`message.model`) → kolumna `Model` w NIGHT-RUN REPORT; fallback jako `<komenda>: skill (sesja)`.

```bash
python3 -c '
import json, sys, datetime as dt
K = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
for p in sys.argv[1:]:
    use, ts, mod = {}, [], set()
    for line in filter(str.strip, open(p, encoding="utf-8")):
        d = json.loads(line); m = d.get("message") or {}
        if d.get("timestamp"): ts.append(dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")))
        if d.get("type") == "assistant" and m.get("usage") and m.get("model") != "<synthetic>":
            u = use.setdefault(m.get("id"), {}); mod.add(m.get("model") or "?")
            for k in K: u[k] = max(u.get(k, 0), m["usage"].get(k, 0))
    tot = [sum(u.get(k, 0) for u in use.values()) for k in K]
    ctx = max((sum(u.get(k, 0) for k in K[:3]) for u in use.values()), default=0)
    mins = (max(ts) - min(ts)).total_seconds() / 60 if ts else 0
    row = [p.replace("\\", "/").rsplit("/", 1)[-1], ",".join(sorted(mod)), len(use), *tot, ctx, f"{mins:.0f} min"]
    print("| " + " | ".join(map(str, row)) + " |")
' $HOME/.claude/projects/*/*/subagents/agent-{<id1>,<id2>}.jsonl
```

Tura = unikalne `message.id` (`output_tokens` rośnie — bierz maks.). Czas = wall-clock. Inny klient → „brak transkryptu”. Z `/headless` albo review
z argumentów dopisz „koszt bez wykonawcy headless i review w sesji głównej”.

**Orkiestrator:** ten sam snippet na transkrypcie sesji głównej
(`$HOME/.claude/projects/<projekt>/<sesja>.jsonl`, nie `subagents/`); do raportu idą jego tury i `cache_read`.

## NIGHT-RUN REPORT — ostatnia wiadomość

Zaczynasz od `CronDelete` i zatrzymania watchdoga. Pod `/goal` raport i dowody muszą paść
w rozmowie (warunek sprawdza transkrypt).

```markdown
## NIGHT-RUN REPORT
Baza: <BASE> — <powód>
Host: <vps | local> (z nagłówka CTX)
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

| Ticket | Stan | Wykonawca | Review | Model | Dowód | Koszt (tury / cache_read / output / kontekst / czas) |
| --- | --- | --- | --- | --- | --- | --- |
| #N | MERGED | opencode | /review-edge | git-start: haiku · git-commit: haiku · git-end: haiku · review-bugbot: sonnet | `gh pr view <PR> --json state` → MERGED; <link Final report> | 58 / 6.1M / 41k / 164k / 20 min |
| #M | needs-human → ready-for-human | subagent | domyślne | git-end: skill (sesja) | <link do komentarza> | … |
| #K | MERGED | opencode → przejęte (haiku, limit) | /review-edge | przejęcie: haiku (Profil) · git-end: haiku | `gh pr view <PR> --json state` → MERGED; <link Final report> | 40 / 3.2M / 25k / 120k / 14 min |
| #J | skipped: <etykieta> / halted | — | — | — | etykieta stanu albo link do komentarza halted | — |

Kolumna Wykonawca: gdy kod 75 został przejęty, zapisz `opencode → przejęte (<model>, limit)` (zamiast `opencode`
nazwa wykonawcy z `EXEC`); model i źródło (cel / Profil / sesja) przepisz z hand-backu do kolumny Model jako
`przejęcie: <model> (<źródło>)`.

Założenia: <co przyjęto bez danych z repo>
Pomiar per agent: <wiersze ze snippetu>

### Nowe ekrany
| PR | Route |
| --- | --- |
| #<PR> | <plik dodany w routes-web / routes-mobile> |
```

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
