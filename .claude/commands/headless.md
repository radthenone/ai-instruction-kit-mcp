---
description: Zleć zadanie innemu klientowi kitu w trybie headless (np. tańszemu modelowi w OpenCode) i dostań krótki raport. Use when /headless <wykonawca> "<treść>", delegowanie implementacji do innego CLI, praca pod /goal z tańszym wykonawcą. Wywołuj jako /headless.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

# /headless — zadanie dla innego klienta

Uruchamiasz innego klienta kitu bez interfejsu, czekasz na wynik i streszczasz go. Sam nie
implementujesz zadania, nie interpretujesz go i nie commitujesz.

Ten klient (host): `claude`. Host nie wywołuje sam siebie.

## Składnia

```text
/headless <wykonawca> [--model <id>] [--timeout <min>] "<treść>"
```

- `<wykonawca>` — klient z `clients:` w `.ai/project.profile.yaml`, inny niż host, z trybem
  headless (dziś: `claude`, `opencode`).
- `--model` — model sesji wykonawcy; bez flagi decyduje jego projektowy config (np. `model`
  w `opencode.json`), potem jego domyślny model.
- `--timeout` — minuty, domyślnie 30.
- Inne flagi = błąd. Walidację robi wrapper — nie zgaduj i nie poprawiaj argumentów.

## Kroki

1. Uruchom wrapper z roota repo. Treść przekaż **słowo w słowo** przez heredoc (bez
   cudzysłowów wokół, bez własnych dopisków); wrapper sam doda stopkę z zasadami:

   ```bash
   node .ai/headless.mjs --host claude <wykonawca> [--model <id>] [--timeout <min>] <<'HEADLESS_EOF'
   <treść>
   HEADLESS_EOF
   ```

   Bez basha (np. PowerShell): treść jako jeden argument po flagach —
   `node .ai/headless.mjs --host claude <wykonawca> [flagi] '<treść>'` (w PowerShell
   apostrof w treści podwój: `''`).

   Zadanie trwa zwykle dłużej niż limit pojedynczej komendy (10 min) — jeśli klient pozwala,
   uruchom komendę w tle i poczekaj na jej koniec; nie przerywaj jej sam. Wrapper po
   zakończeniu, błędzie albo timeoucie zabija całe drzewo procesów wykonawcy.
2. Kod wyjścia `2` = błędne wywołanie (np. wykonawca == host, spoza `clients:`, nieznana
   flaga). Pokaż komunikat wrappera użytkownikowi i zakończ.
3. Po zakończeniu (także kod ≠ 0 albo `124` = timeout) sprawdź stan repo:

   ```bash
   git status --short
   git diff --stat
   ```

4. Raport dla użytkownika:

   ```markdown
   ## /headless <wykonawca> — <OK | błąd <kod> | timeout>
   - Zmiany: <pliki z git status / diff --stat, jedno zdanie co>
   - Testy: <z raportu wykonawcy: komenda i wynik albo „nie uruchomione”>
   - Problemy: <z raportu wykonawcy i z kodu wyjścia albo „brak”>
   - Dalej: review diffa, potem `/git-commit`
   ```

## Zakazy

- Nie commituj, nie pushuj, nie poprawiaj kodu po wykonawcy.
- Nie dopisuj nic do treści zadania i nie przekazuj innych flag CLI wykonawcy.
- Nie wywołuj wykonawcy z pominięciem wrappera.
