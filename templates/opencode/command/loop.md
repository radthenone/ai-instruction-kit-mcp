---
description: "Pętla: /loop [5m] [max=N] <zadanie> — plugin kit-loop powtarza turę (co interwał albo od razu) aż do dowodu końca. /loop stop. Przerwania: Esc, /loop stop, limit 10 iteracji."
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

# /loop — iteruj aż do dowodu końca

Pętlę prowadzi plugin `.opencode/plugins/kit-loop.js`: po każdej turze wysyła
następną — od razu albo po interwale (`5m`, `30s`, `1h` jako pierwsze słowo).
Kończy ją `<promise>DONE</promise>` na końcu odpowiedzi, Esc, `/loop stop`
albo limit iteracji (default 10, `max=N`).

## Start

- `stop` → „Pętla zatrzymana.” — plugin już ją zatrzymał. Koniec.
- Inaczej z argumentów (bez interwału i `max=N`) wywiedź **zadanie** i
  **warunek końca** (jeden, sprawdzalny). Przy interwale warunek jest opcjonalny
  (np. „sprawdzaj CI co 5 min”); bez interwału i bez warunku — zapytaj jednym
  zdaniem i czekaj.

## Każda iteracja

1. Działaj: jeden mały krok (kod, test, komenda).
2. Zweryfikuj krok dowodem. Niepowodzenie → naprawa w następnej iteracji, nie
   nowy plan.
3. Warunek końca spełniony dowodem → LOOP REPORT (zadanie, dowód) i ostatnia
   linia dokładnie `<promise>DONE</promise>`.
4. Inaczej → jedno zdanie, co dalej, i zakończ turę — plugin wyśle następną.
