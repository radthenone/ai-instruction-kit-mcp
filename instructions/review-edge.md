# `/review-edge` — pedant od przypadków brzegowych

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-edge.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

**Pedant od brzegów, nie stylista.** Ma zakaz powtarzania stylistycznych
findingów z [review-backend](review-backend.md) i [review-frontend](review-frontend.md).

Czego szuka:

- null / undefined / puste kolekcje
- race conditions przy async
- brakująca walidacja wejścia (API, formularze)
- breaking changes bez wersjonowania / migracji
- off-by-one, nieobsłużone wyjątki

Do **większych** zmian. Przy zmianie na dwa pliki to narzut.

Zwraca standardową tabelę `Severity | Location | Finding | Fix` — patrz format
w [review-bugbot](review-bugbot.md).

**Pułapka:** `/review-edge` na dwie linijki. Pedant bez materiału zaczyna
wymyślać.

**Do przemyślenia:** `/review-edge` nie ma dostępu do testów — mówi „uruchom
to", ale nie uruchamia. To robota [review-tests](review-tests.md). Może warto
je odpalać parą.
