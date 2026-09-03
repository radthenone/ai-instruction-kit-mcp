# `/teacher-backend` — Django/DRF (albo co mówi overlay)

> Prywatne notatki z użycia. Źródło: `.claude/commands/teacher-backend.md`.
> Wspólna mechanika nauczycieli i format odpowiedzi: [teacher-agent](teacher-agent.md).

**Kolejność, w której patrzy senior** — sama kolejność jest lekcją:

1. **Dane przed kodem** — model, klucze, constrainty, indeksy **w bazie**, nie
   tylko walidacja w Pythonie. Baza to ostatnia linia obrony i przeżyje ten kod.
2. **Gdzie mieszka logika** — model/manager/queryset vs serializer vs view vs
   serwisy. Fat view = przyszły ból.
3. **Kontrakt na zewnątrz** — serializer/schema to publiczne API. Zmiana pola =
   zmiana kontraktu; `codegen:` z overlay decyduje, czy regenerować klienta FE.
4. **Zapytania** — N+1, `select_related`/`prefetch_related`, agregacja w bazie.
   Zawsze pytanie: **ile zapytań poleci na jeden request**.
5. **Migracje** — bez downtime; osobno schema, osobno backfill; czy da się cofnąć.
6. **Transakcje i wyścigi** — `atomic`, `select_for_update`, idempotencja.
   Dwa requesty naraz to norma, nie edge case.
7. **Celery** — argumenty = **ID, nie obiekty ORM**; retry i at-least-once
   znaczą, że task **wykona się dwa razy** i musi to przeżyć.
8. **Uprawnienia** domyślnie zamknięte; otwarty endpoint wymaga uzasadnienia.
9. **Konfiguracja** — 12-factor, sekrety z env, brak rozjazdu dev/prod.
10. **Testy jako projekt** — pokrycie linii ≠ pokrycie ryzyka.

Osobna sekcja: **typowanie — gdzie płaci, a gdzie kosztuje**. Moduły
`core:typing-python` mówią *jak* pisać adnotacje; nauczyciel mówi *czy i gdzie*
się opłaca — bo w Django odpowiedź nie brzmi „wszędzie".

**vs [review-backend](review-backend.md):** ten uczy patrzeć zanim się napisze
kod; tamten łapie, co już wyszło źle w diffie.
