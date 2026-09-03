# `/review-ui` — UX/a11y na ekranach i formularzach

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-ui.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

Mobile-first, jeśli bundle tak mówi.

Czego szuka:

- touch targety **poniżej 44pt**
- brak stanów: loading, empty, error
- hardcoded kolory/spacing zamiast tokenów theme
- brak labeli formularza, za słaby kontrast
- niespójność ze wspólnymi komponentami

Niepewny flow produktu albo copy prawny → pyta.

Zwraca standardową tabelę `Severity | Location | Finding | Fix` — patrz format
w [review-bugbot](review-bugbot.md).

**Do przemyślenia:** czy `/review-ui` i [review-frontend](review-frontend.md)
nie powinny się scalić — nakładają się na komponentach. Argument przeciw: UI
patrzy na UX i a11y, frontend na konwencje stacku i Orval. Na razie zostawiam.
