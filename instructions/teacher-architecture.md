# `/teacher-architecture` — granice, kontrakt, odwracalność

> Prywatne notatki z użycia. Źródło: `.claude/commands/teacher-architecture.md`.
> Wspólna mechanika nauczycieli i format odpowiedzi: [teacher-agent](teacher-agent.md).

**Uczy:** gdzie co mieszka, granice FE/BE, kontrakt API, infra, wybór narzędzi.

**Czyta:** `get_bundle("architecture")`, `get_overlay()`, strukturę katalogów,
**`docs/adr/`** (może decyzja już zapadła i ma uzasadnienie),
`get_module("core:engineering-canon")` — Fowler, Strangler Fig, ADR wg Nygarda,
DORA, 12-factor.

## Rzeczy, które warto stąd pamiętać

- **Granice przed technologią.** Wybór biblioteki to konsekwencja granicy, nie
  odwrotnie.
- **Logika biznesowa w jednym miejscu.** Reguła powtórzona w backendzie i w UI
  rozjedzie się w miesiąc. Frontend waliduje dla UX, backend dla prawdy.
- **Kiedy NIE dzielić.** Mikroserwisy kupują niezależny deploy za cenę sieci,
  spójności danych i observability. Przy jednym zespole prawie zawsze przegrana.
  „Monolit modularny" to sygnał doświadczenia, nie wymówka.
- **Współdzielony kod to zobowiązanie** — zmiana boli w dwóch miejscach naraz.
- **Infra dopiero pod ból.** Pytanie brzmi „jaki problem to rozwiązuje **dziś**",
  nie „czy się przyda".
- **Odwracalność** jako osobna sekcja odpowiedzi. Schemat danych, auth,
  publiczne API, wybór bazy = jednokierunkowe. Reszta = spróbuj i zmień.

Typowe zadanie na koniec: **napisz ADR na 10 zdań** w `docs/adr/`.

**vs [review-architecture](review-architecture.md):** tamten łapie naruszenie
granicy w gotowym diffie. Ten ma sprawić, żebym granice **widział sam**.
