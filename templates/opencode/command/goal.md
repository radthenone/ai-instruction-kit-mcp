---
description: "Trwały cel sesji: /goal [max=N] <cel> — plugin kit-loop wznawia pracę turami aż do dowodu końca. /goal status|clear. Przerwania: Esc, /goal clear, limit 25 tur."
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

# /goal — cel sesji z pętlą

Pętlę prowadzi plugin `.opencode/plugins/kit-loop.js`: po każdej Twojej turze
wysyła kolejną, dopóki nie zakończysz odpowiedzi linią `<promise>DONE</promise>`,
użytkownik nie przerwie (Esc, `/goal clear`) albo nie minie limit tur.

## Sterowanie (najpierw sprawdź argumenty)

- Puste albo `status` → pokaż blok GOAL (cel, tura, status) i nic nie rób.
- `clear` / `pause` → „Cel wyczyszczony.” — plugin już zatrzymał pętlę. Koniec.
- Inaczej → nowy cel: wypisz blok GOAL i od razu zacznij pracę (nie pytaj).

## Blok GOAL

```markdown
## GOAL
Cel: <treść argumentów bez max=N>
Warunek końca: <jeden sprawdzalny warunek wywiedziony z celu>
Dowód: <ostatni dowód lub brak>
```

## Każda tura

1. Zrób kolejny krok ku celowi.
2. Sprawdź warunek końca **dowodem** (kod 0 komendy, zielone testy, zawartość
   pliku). Deklaracja „działa” to nie dowód.
3. Spełniony → GOAL REPORT (cel, dowód) i ostatnia linia dokładnie
   `<promise>DONE</promise>`.
4. Niespełniony → jedno zdanie, co dalej, i zakończ turę bez pytań — plugin
   wyśle następną. Nie wypisuj znacznika DONE, jeśli cel nie jest osiągnięty.
