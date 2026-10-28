---
mode: "agent"
description: "Zleć zadanie innemu klientowi kitu w trybie headless (np. tańszemu modelowi w OpenCode) i dostań krótki raport. Use when /headless <wykonawca> '<treść>', delegowanie implementacji do innego CLI, praca pod /goal z tańszym wykonawcą. Wywołuj jako /headless."
---

# /headless — zadanie dla innego klienta

Uruchamiasz innego klienta kitu bez interfejsu, czekasz na wynik i streszczasz go. Sam nie
implementujesz zadania, nie interpretujesz go i nie commitujesz. Wykonawca pracuje test-first
i commituje lokalnie po każdym zielonym kroku; push i PR robi host po review.

Ten klient (host): `vscode`. Host nie wywołuje sam siebie.

Język odpowiedzi i raportu: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Składnia

```text
/headless <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] "<treść>"
```

Przykłady (host → wywołanie):

```text
claude:       /headless opencode "..."   albo   /headless gemini "..."
opencode:     /headless gemini "..."
antigravity:  /headless opencode "..."
```

Limit dostawcy albo brak binarki → wrapper sam przekazuje tę samą treść 1:1 drugiemu
tańszemu wykonawcy: `opencode → gemini` albo `gemini → opencode` (pomija hosta i klientów
spoza `clients:`). Ostatni z limitem → kod `75` i zadanie przejmuje host (krok 2).
Zastępca bierze swój domyślny model (`--model` dotyczy tylko wykonawcy z wywołania).

- `<wykonawca>` — klient z `clients:` w `.ai/project.profile.yaml`, inny niż host, z trybem
  headless (dziś: `claude`, `opencode`, `antigravity`; alias `gemini` = `antigravity`).
- `--model` — model sesji wykonawcy; bez flagi decyduje jego projektowy config (np. `model`
  w `opencode.json`), potem jego domyślny model. `gemini`/`antigravity`: agy nie ma
  projektowego configu, więc wrapper czyta `.agents/agy.json` (gitignored, edytujesz sam),
  np. `{"model": "gemini-3.8-flash-high"}` albo `{"model": "gemini-3.8-flash", "effort": "high"}`
  (poziom w sufiksie nazwy albo w `effort`, nie oba); bez pliku `gemini-3.8-flash-medium`.
- Linked worktree (`git worktree add`) nie ma projektowego configu (jest w `.gitignore`):
  wrapper bierze `opencode.json` z głównego checkoutu, przekazuje go wykonawcy jako
  `OPENCODE_CONFIG` i czyta z niego `model`. Raport końcowy mówi wprost
  `CONFIG=main-checkout <ścieżka>` albo `CONFIG=missing — executor default model`.
- `--timeout` — minuty, domyślnie 60; liczony osobno dla każdego wykonawcy w łańcuchu.
- `--heartbeat` — co ile minut linia stanu `[headless] ♥` w logu, domyślnie 10.
- Inne flagi = błąd. Walidację robi wrapper — nie zgaduj i nie poprawiaj argumentów.

## Kroki

1. Uruchom wrapper z roota repo. Treść przekaż **słowo w słowo** przez heredoc (bez
   cudzysłowów wokół, bez własnych dopisków); wrapper sam doda stopkę z zasadami:

   ```bash
   node .ai/headless.mjs --host vscode <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] <<'HEADLESS_EOF'
   <treść>
   HEADLESS_EOF
   ```

   Bez basha (np. PowerShell): treść jako jeden argument po flagach —
   `node .ai/headless.mjs --host vscode <wykonawca> [flagi] '<treść>'` (w PowerShell
   apostrof w treści podwój: `''`).

   Zadanie trwa zwykle dłużej niż limit pojedynczej komendy (10 min) — jeśli klient pozwala,
   uruchom komendę w tle i poczekaj na jej koniec; nie przerywaj jej sam. Wrapper po
   zakończeniu, błędzie albo timeoucie zabija całe drzewo procesów wykonawcy.

   Pierwsza linia wyjścia to ścieżka logu (`[headless] log: <log>`). Nie śledź wyjścia na
   bieżąco — stan w razie potrzeby czytasz jedną linią:
   `grep '^\[headless\]' <log> | tail -1`. Budzić się (np. Monitor) warto tylko na linię
   `[headless] możliwe zacięcie`; samo zacięcie niczego nie zabija — robi to `--timeout`.
2. Kod wyjścia `2` = błędne wywołanie (np. wykonawca == host, spoza `clients:`, nieznana
   flaga). Pokaż komunikat wrappera użytkownikowi i zakończ.
   Kod `75` = limit u ostatniego wykonawcy łańcucha, nie błąd: linia
   `PAUSE=rate-limit reset=<ISO|brak>` w logu; wcześniejszych zastępców wrapper już próbował.
   Zadanie przejmuje host, z **tą samą treścią 1:1** i zasadami ze stopki (test-first, lokalne
   commity, bez push), od stanu brancha z raportu:
   - skill w głównym wątku → wykonaj treść sam;
   - subagent `headless` → nie wykonuj; hand-back `przejęcie: limit <wykonawca>, reset <ISO|brak>`
     z treścią i raportem — przejmuje główny wątek;
   - pod `/night-run` → reguła `LIMIT` z `/night-run` (`przejmij` / `czekaj`).
3. Po zakończeniu (także kod ≠ 0 albo `124` = timeout) przeczytaj z wyjścia raport
   końcowy wrappera (`[headless] raport końcowy`): `git status --short`, commity wykonawcy
   od startu, nowe wpisy stasha i ostatnie linie wykonawcy. Ostrzeżenie o stashu (`UWAGA`)
   przenieś do raportu dla użytkownika — tam może leżeć praca wykonawcy; sam go nie zdejmuj.
   Wyjście ucięte przez klienta — raport jest w logu:
   `sed -n '/^\[headless\] raport końcowy/,$p' <log>`.

4. Raport dla użytkownika:

   ```markdown
   ## /headless <wykonawca> — <OK | błąd <kod> | timeout | przejęte przez hosta>
   - Łańcuch: <np. `opencode → antigravity` z linii `[headless] … przekazuję zadanie` albo pomiń>
   - Zmiany: <pliki z git status, jedno zdanie co>
   - Commity wykonawcy: <z raportu końcowego albo „brak”>
   - Stash: <wpisy z ostrzeżenia `UWAGA` albo pomiń linię>
   - Testy: <z raportu wykonawcy: komenda i wynik albo „nie uruchomione”>
   - Problemy: <z raportu wykonawcy i z kodu wyjścia albo „brak”>
   - Log: <ścieżka logu>
   - Dalej: review commitów i diffa, potem `/git-commit` dla reszty i `/git-end`
   ```

## Zakazy

- Nie commituj, nie pushuj, nie poprawiaj kodu po wykonawcy (lokalne commity wykonawcy
  zostają; push i PR po review). Wyjątek: przejęcie po kodzie `75` (krok 2).
- Nie zdejmuj stasha (`git stash pop`) — tylko ostrzeżenie w raporcie.
- Nie dopisuj nic do treści zadania i nie przekazuj innych flag CLI wykonawcy.
- Nie wywołuj wykonawcy z pominięciem wrappera.
