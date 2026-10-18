---
name: headless
description: Zleć zadanie innemu klientowi kitu w trybie headless (np. tańszemu modelowi w OpenCode) i dostań krótki raport. Use when /headless <wykonawca> "<treść>", delegowanie implementacji do innego CLI, praca pod /goal z tańszym wykonawcą. Wywołuj jako /headless.
---

# /headless — zadanie dla innego klienta

Uruchamiasz innego klienta kitu bez interfejsu, czekasz na wynik i streszczasz go. Sam nie
implementujesz zadania, nie interpretujesz go i nie commitujesz. Wykonawca pracuje test-first
i commituje lokalnie po każdym zielonym kroku; push i PR robi host po review.

Ten klient (host): `codex`. Host nie wywołuje sam siebie.

## Składnia

```text
/headless <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] "<treść>"
```

- `<wykonawca>` — klient z `clients:` w `.ai/project.profile.yaml`, inny niż host, z trybem
  headless (dziś: `claude`, `opencode`).
- `--model` — model sesji wykonawcy; bez flagi decyduje jego projektowy config (np. `model`
  w `opencode.json`), potem jego domyślny model.
- `--timeout` — minuty, domyślnie 30.
- `--heartbeat` — co ile minut linia stanu `[headless] ♥` w logu, domyślnie 10.
- Inne flagi = błąd. Walidację robi wrapper — nie zgaduj i nie poprawiaj argumentów.

## Kroki

1. Uruchom wrapper z roota repo. Treść przekaż **słowo w słowo** przez heredoc (bez
   cudzysłowów wokół, bez własnych dopisków); wrapper sam doda stopkę z zasadami:

   ```bash
   node .ai/headless.mjs --host codex <wykonawca> [--model <id>] [--timeout <min>] [--heartbeat <min>] <<'HEADLESS_EOF'
   <treść>
   HEADLESS_EOF
   ```

   Bez basha (np. PowerShell): treść jako jeden argument po flagach —
   `node .ai/headless.mjs --host codex <wykonawca> [flagi] '<treść>'` (w PowerShell
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
3. Po zakończeniu (także kod ≠ 0 albo `124` = timeout) przeczytaj z wyjścia raport
   końcowy wrappera (`[headless] raport końcowy`): `git status --short`, commity wykonawcy
   od startu, nowe wpisy stasha i ostatnie linie wykonawcy. Ostrzeżenie o stashu (`UWAGA`)
   przenieś do raportu dla użytkownika — tam może leżeć praca wykonawcy; sam go nie zdejmuj.
   Wyjście ucięte przez klienta — raport jest w logu:
   `sed -n '/^\[headless\] raport końcowy/,$p' <log>`.

4. Raport dla użytkownika:

   ```markdown
   ## /headless <wykonawca> — <OK | błąd <kod> | timeout>
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
  zostają; push i PR po review).
- Nie zdejmuj stasha (`git stash pop`) — tylko ostrzeżenie w raporcie.
- Nie dopisuj nic do treści zadania i nie przekazuj innych flag CLI wykonawcy.
- Nie wywołuj wykonawcy z pominięciem wrappera.
