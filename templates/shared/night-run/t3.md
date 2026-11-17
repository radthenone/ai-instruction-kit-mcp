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

Sesja ticketu tworzy PR w kroku 6 i zwraca jego URL dopiero w hand-backu, więc orkiestrator woła `write_pull_request_guides(pullRequests: [{url: "<URL PR>"}])` po otrzymaniu hand-backu z URL PR, nie w trakcie review, żeby w zakładce PR Guide w T3 Code powstał przewodnik po zmianach PR.

## 2. Wykonawca implementacji (z sesji ticketu)

Gdy ticket wymaga delegowania wykonawcy implementacji (kroki 2–3 w `night-run-ticket`):
- delegowanie wykonuje sesja ticketu (z sesji ticketu), a nie główny orkiestrator nocy;
- wywołanie `delegate_task`:
  * `isolation: shared` — wykonawca pracuje w checkoucie sesji ticketu, na branchu roboczym sesji ticketu z `/git-start`;
  * `mode: async`;
  * `task` — specyfikacja zadania implementacyjnego, testy z timeoutem, log postępu w CTX oraz obowiązkowy hand-back.

## 3. Stan i wznawianie

- Identyfikator zadania `taskId` zwrócony przez `delegate_task` zostaje zapisany w `## Stan` w pliku CTX (`ticket: #<N> taskId: <taskId>`);
- po przerwaniu sesji orkiestratora lub restarcie wznowienie następuje przez odpytanie `task_status` na podstawie zapisanego `taskId`;
- ponowienie wywołania z tym samym `clientRequestId` nie tworzy drugiego dziecka.

- Karta eskalacji needs-human (sekcja „Karta eskalacji” w `night-run`): pole `Wątek T3:` to wartość pola `link` z wyniku `delegate_task` sesji ticketu, wstawiona dosłownie.

## 4. Watchdog i cron

- watchdog i cron pominięte: w środowisku T3 nie uruchamia się skryptu `.ai/night-run-watchdog.sh` ani `CronCreate` (T3 samodzielnie zarządza cyklem życia zadań i wątków w tle).

## 5. Sprzątanie po MERGED

Gdy PR ticketu osiągnie stan `MERGED`:
1. Orkiestrator woła narzędzie `link_pull_request` z adresem URL zmergowanego PR;
2. Orkiestrator usuwa worktree sesji ticketu: `node .ai/worktree.mjs remove <katalog>`; gdy komenda zgłosi „Ścieżka nie istnieje”, worktree został usunięty wcześniej — krok 2 uznaje się za wykonany i orkiestrator przechodzi do kroku 3; inna odmowa zatrzymuje sprzątanie i trafia do raportu;
3. Orkiestrator usuwa lokalny branch ticketu: `git branch -d <typ>/<N>-<slug>` (branch nadany przez T3 po rename z sekcji 1);
4. odmowa -d (`git branch -d` zgłasza błąd / odmowę) -> wpis w raporcie, bez -D (zakaz `-D`, nigdy nie wymuszamy usunięcia przez `-D`).
5. Po krokach 2–4 (także po odmowie `-d` z kroku 4) orkiestrator archiwizuje wątek sesji ticketu: `t3_thread_organize(action: 'archive', threadId: childThreadId)` (`childThreadId` z wyniku `delegate_task` sesji ticketu); historia wątku zostaje w archiwum.

## 6. Pola raportu (NIGHT-RUN REPORT)

W końcowym raporcie nocy (NIGHT-RUN REPORT):
- Czas trwania: czas z wątków (na podstawie metadanych i znaczników czasu z zadań T3);
- Tokeny delegatów: tokeny delegatów „n/d”;
- Model: model „niepotwierdzony”, gdy `executedModel` jest `null` (np. dla wykonawców, w których T3 zwraca `executedModel: null`).

## 7. Clean Slate

Hand-back `clean-slate` (sekcja „Clean Slate” w `night-run`) → gdy spełniony jest warunek bezpieczeństwa z `night-run`, orkiestrator wykonuje kroki w tej kolejności; każdy zapis w `## Stan` to osobny krok:
1. zapisuje w `## Stan` etap `clean-slate: w toku` ze starym `taskId`, notatką o błędzie X i ścieżce Y oraz ścieżką worktree (`ticket: #<N> clean-slate: w toku, <stary taskId>, <ścieżka worktree>, notatka: <X, Y>`);
2. usuwa worktree ticketu (`node .ai/worktree.mjs remove <katalog>`);
3. zapisuje w `## Stan` etap `clean-slate: worktree usunięty`;
4. woła świeży `delegate_task` jak w sekcji 1, z różnicami:
   - nowy `clientRequestId`: `<nazwa katalogu CTX>-<numer ticketu>-clean-slate`;
   - `title`: `<typ>/<N>-<slug>-clean-slate`;
   - z `night-run.clean-slate` w Profilu: `provider` → `target.providerInstanceId`, `model` → `target.model`, `effort` → `target.options` jako `{id: "effort", value: <effort>}`; brak pola = wartość jak w sekcji 1;
   - `task` zawiera linię „Clean Slate: użyty” i notatkę zapisaną w kroku 1;
5. zapisuje nowy `taskId` w `## Stan` w miejsce starego.

Wznowienie bierze etap, ścieżkę worktree i notatkę z `## Stan`, nie z pamięci sesji:
- etap `clean-slate: w toku` i worktree istnieje → dokończ usunięcie i przejdź do kroku 3;
- etap `clean-slate: w toku` i worktree już nie istnieje → przejdź do kroku 4;
- etap `clean-slate: worktree usunięty` bez nowego `taskId` → przejdź do kroku 4.

Krok 4 przy wznowieniu podaje ten sam `clientRequestId`, więc T3 wznawia zlecenie bez nowego `taskId`; nigdy drugi `delegate_task` z innym `clientRequestId` dla tego samego Clean Slate i nigdy drugi Clean Slate na ticket.
