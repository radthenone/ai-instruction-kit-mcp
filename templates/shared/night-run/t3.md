# Karta transportu T3 Code dla /night-run

Karta transportu dla procedury `/night-run` w środowisku T3 Code (plik instalowany jako `.ai/night-run-t3.md`).
Zastępuje transport procedury `/night-run` (uruchamianie i nadzór zadań, sprzątanie, raportowanie), nie zmienia kroków procedury zlecenia ticketu (`night-run-ticket`).

## 1. Sesja ticketu (orkiestrator → dziecko ticketu)

Orkiestrator nocy uruchamia sesję dla każdego ticketu za pomocą narzędzia `delegate_task`:
- `isolation: worktree` — T3 tworzy izolowane worktree dla sesji ticketu z plikami kita i środowiskiem `.venv` (przygotowanymi przez hak `post-checkout`), a T3 nadaje temu worktree własny branch;
- `mode: async` — uruchomienie asynchroniczne;
- `clientRequestId` — klucz idempotencji złożony z nazwy katalogu CTX i numeru ticketu (np. `<nazwa katalogu CTX>-<numer ticketu>`); ponowienie z tym samym `clientRequestId` nie tworzy drugiego dziecka;
- `task` — wskazuje procedurę `night-run-ticket`, podaje parametry zlecenia (baza `<BASE>`, ścieżka `<CTX>`, nazwa brancha `<typ>/<N>-<slug>` (ta sama wartość co `title`; sesja ticketu jej nie wyprowadza), handoffy blokujących, treść issue, reguły) i wprost zezwala na dalszą delegację (sesja ticketu ma pełne prawo delegować implementację i podzadania);
- `role: general`, `title: "<typ>/<N>-<slug>"` — tytuł to nazwa brancha z konwencji kita (`/git-start`, np. `feat/475-enforce-branch-naming`), z której T3 wyprowadza nazwę brancha worktree; nie wolny tekst.

Sesja ticketu zaraz po starcie (przed `/git-start #<N>`) najpierw sprawdza bazę: `git fetch origin` (błąd fetch → needs-human); niepusty `git status --porcelain` (brudne worktree) → needs-human; gdy `git merge-base --is-ancestor HEAD origin/<BASE>` zwraca 0 i `git status --porcelain` jest pusty, wykonuje `git merge --ff-only origin/<BASE>` (inny PR zmergował się po utworzeniu worktree); potem `git merge-base --is-ancestor origin/<BASE> HEAD`. Niezerowy kod wyjścia (rozbieżna historia albo brudne worktree; baza się nie zgadza → needs-human): bez zmiany nazwy, bez ponownego użycia brancha, ticket nie jest kontynuowany. Potem sprawdza `git branch --show-current`. Gdy T3 nadało inną nazwę niż `<typ>/<N>-<slug>` z `task`, natychmiast wykonuje `git branch -m <typ>/<N>-<slug>` (przed pierwszym commitem i push), żeby PR powstał pod nazwą z konwencji. Pusty wynik (odłączony HEAD) → `git switch -c <typ>/<N>-<slug>`. Branch o tej nazwie już istnieje (odmowa `-m`) → needs-human, nigdy `-M`. Potem `/git-start` użyje aktywnego brancha `<typ>/<N>-<slug>` zamiast tworzyć nowy.

PR sesji ticketu (`gh pr create`, krok 6 `night-run-ticket`) dostaje wszystkie etykiety issue flagami `--label`; etykiety procesowe stanu (`ready-for-agent`, `ready-for-human`, `needs-info`, `needs-triage`, `wontfix`) są odrzucane. Tytuł PR to czysty Conventional Commit po angielsku opisujący zmianę domenową, bez prefiksu `(night-run)`.

## 2. Wykonawca implementacji (z sesji ticketu)

Gdy ticket wymaga delegowania wykonawcy implementacji (kroki 2–3 w `night-run-ticket`):
- delegowanie wykonuje sesja ticketu (z sesji ticketu), a nie główny orkiestrator nocy;
- wywołanie `delegate_task`:
  * `isolation: shared` — wykonawca pracuje w checkoucie sesji ticketu, na branchu roboczym sesji ticketu z `/git-start`;
  * `mode: async`;
  * `task` — specyfikacja zadania implementacyjnego, testy z timeoutem, log postępu w CTX oraz obowiązkowy hand-back.

### Mapowanie modeli na `target`

Parametry nocy `implementacja: <wykonawca> <model>; review: <wykonawca> <model>` sesja ticketu tłumaczy na obiekt `target` w `delegate_task` (osobno dla implementacji i dla review):

| `<wykonawca>` | `providerInstanceId` | `model` (przykład) | `options` (przykład) |
|---------------|----------------------|--------------------|----------------------|
| `claude` | `claudeAgent` | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | `[{id: "effort", value: "medium"}]` |
| `antigravity` | `antigravity` | model z listy providera | `[{id: "thought_level", value: "high"}]` |
| `opencode` | `opencode` | `<provider>/<model>` z listy providera, np. `opencode/deepseek-v4.1-flash-free` | `[{id: "variant", value: "high"}]` |

Przykład: `review: claude claude-haiku-5-5` → `target: {providerInstanceId: "claudeAgent", model: "claude-haiku-5-5"}`, a review idzie z `role: review`, `mode: wait`, `isolation: shared`.
- przed pierwszym `delegate_task` w sesji: `orchestrator_capabilities`; nazwy modeli i `options` bierz z jego wyniku, nie z pamięci; `providerInstanceId` w tabeli to nazwa domyślna — gdy w wyniku `orchestrator_capabilities` jest wyłączona albo jej nie ma → needs-human; nie wybieraj innej instancji tego samego `driverKind`, nawet gdy włączona jest dokładnie jedna (np. `opencode2`);
- options tylko gdy parametr nocy je podaje (np. `@poziom`, `#wariant` w nazwie modelu lub parametr `effort:` / `variant:`) albo provider ich wymaga; poziom wysiłku orkiestrator tłumaczy na właściwą opcję providera: `id: "effort"` (Claude), `id: "variant"` (OpenCode), `id: "thinking_level"` (Antigravity); brak wskazanego poziomu → pomiń `options` (provider używa wartości `default` z `orchestrator_capabilities`); brak `<model>` → pomiń pole `model` (domyślny model providera);
- provider albo model niedostępny → needs-human, bez cichej zamiany na inny model i bez fallbacku na natywne narzędzia.

## 3. Stan i wznawianie

- Identyfikator zadania `taskId` zwrócony przez `delegate_task` zostaje zapisany w `## Stan` w pliku CTX (`ticket: #<N> taskId: <taskId>`);
- po przerwaniu sesji orkiestratora lub restarcie wznowienie następuje przez odpytanie `task_status` na podstawie zapisanego `taskId`;
- ponowienie wywołania z tym samym `clientRequestId` nie tworzy drugiego dziecka.

## 4. Watchdog i cron

- watchdog i cron pominięte: w środowisku T3 nie uruchamia się skryptu `.ai/night-run-watchdog.sh` ani `CronCreate` (T3 samodzielnie zarządza cyklem życia zadań i wątków w tle).
- nasłuch PR reaktywny, zamiast pętli `gh pr checks --watch` (ani `sleep`, `Monitor`, `ScheduleWakeup`): zaraz po `gh pr create` orkiestrator woła `link_pull_request` z pełnym URL PR, potem `watch_pull_request`; T3 wybudza orkiestratora po zakończeniu checków albo przy nowym komentarzu lub review, a orkiestrator kończy turę zamiast czekać;
- `unwatch_pull_request` po `MERGED`, po decyzji needs-human dla PR i przed końcem nocy (NIGHT-RUN REPORT) — na każdym PR, który orkiestrator obserwuje.

## 5. Uwagi CodeRabbit i sprzątanie po MERGED

Po wybudzeniu z `watch_pull_request` z nowymi uwagami CodeRabbit (autor `coderabbitai`) orkiestrator przekazuje je sesji ticketu (albo wykonawcy); po pushu poprawki zamyka tylko wątki zaadresowane tą poprawką, przez GraphQL:

```bash
gh api graphql --paginate -F pr=<N> -f owner=<owner> -f repo=<repo> -f query='
query($owner:String!,$repo:String!,$pr:Int!,$endCursor:String){repository(owner:$owner,name:$repo){pullRequest(number:$pr){
  reviewThreads(first:100,after:$endCursor){pageInfo{hasNextPage endCursor}
    nodes{id isResolved comments(first:1){nodes{author{login} path body}}}}}}}'
gh api graphql -f id=<threadId> -f query='
mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}'
```

- `reviewThreads` filtruj po `isResolved: false` i autorze `coderabbitai`; `id` wątku idzie do `resolveReviewThread(input:{threadId:$id})`;
- uwaga niezaadresowana albo odrzucona → wątek zostaje otwarty, z odpowiedzią w wątku (powód), nie zamykany po cichu;
- przed pushem poprawki odczytaj pełną treść wszystkich wcześniejszych review CodeRabbit ze wszystkich stron endpointu reviews (potok ze wszystkich stron jw., bez filtra `commit_id`: `set -o pipefail; gh api --paginate --slurp repos/<owner>/<repo>/pulls/<N>/reviews | jq 'flatten | map(select(.user.login == "coderabbitai[bot]"))'`) i uwagi wymagające działania przekaż sesji ticketu razem z uwagami z wątków;
- `reviewThreads` nie obejmuje uwag spoza diffu (sekcja „Outside diff range” w treści review) ani uwag ogólnych, a zdarzenie `watch_pull_request` niesie tylko skrócony podgląd komentarza; pełną treść review czytaj ze wszystkich stron (endpoint zwraca domyślnie 30 review na stronę, chronologicznie) przez `set -o pipefail; gh api --paginate --slurp repos/<owner>/<repo>/pulls/<N>/reviews | jq 'flatten | map(select(.user.login == "coderabbitai[bot]" and .commit_id == "<head>")) | last'` (pola `state` i `body`; w REST `user.login` autora `coderabbitai` to `coderabbitai[bot]`, `<head>` to bieżący head commit PR) — wybór ostatniego wpisu po wszystkich stronach, nie po pierwszej; uwagi wymagające działania z tej treści przekazuj sesji ticketu razem z uwagami z wątków;
- niezerowy kod wyjścia potoku (błąd `gh api`) albo pusty wynik → `needs-human` (błąd odczytu review), nigdy „brak uwag”;
- wynik `null` → review bieżącego head nie jest jeszcze odczytane: poczekaj na review bieżącego head (wybudzenie przez `watch_pull_request`) i nie przechodź do merge, dopóki go nie odczytasz; limit czasu (maks. 10–15 min) i postępowanie po jego upływie określa `git-end` (w rundzie 1 sprawdź otwarte wątki bota, a gdy ich brak — odnotuj brak review bota w raporcie; w kolejnych rundach `needs-human`); uwagi wymagające działania z wcześniejszych review nadal przekazuj sesji ticketu.

Gdy PR ticketu osiągnie stan `MERGED`:
1. Orkiestrator woła `unwatch_pull_request` dla PR (podpiętego wcześniej przez `link_pull_request`, sekcja 4);
2. Orkiestrator usuwa worktree sesji ticketu: `node .ai/worktree.mjs remove <katalog>`;
3. Orkiestrator usuwa lokalny branch ticketu: `git branch -d <typ>/<N>-<slug>` (branch nadany przez T3 po rename z sekcji 1);
4. odmowa -d (`git branch -d` zgłasza błąd / odmowę) -> wpis w raporcie, bez -D (zakaz `-D`, nigdy nie wymuszamy usunięcia przez `-D`).

## 6. Pola raportu (NIGHT-RUN REPORT)

W końcowym raporcie nocy (NIGHT-RUN REPORT):
- Czas trwania: czas z wątków (na podstawie metadanych i znaczników czasu z zadań T3);
- Tokeny delegatów: tokeny delegatów „n/d”;
- Model: model „niepotwierdzony”, gdy `executedModel` jest `null` (np. dla wykonawców, w których T3 zwraca `executedModel: null`).
