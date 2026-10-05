# Angular — przegląd Stacku (web)

Tier `web: angular` (aktualne podejście: standalone + signals) albo `web: angular@rxjs`
(NgModule + RxJS-first). Ten moduł jest wspólny dla obu; szczegóły: `stack:angular:modern`
albo `stack:angular:legacy`. Katalog kodu: klucz `web:` w sekcji `## Ścieżki`
w `.ai/project.md` (dalej: `<web>`).

## Typowy zestaw

| Obszar | Typowo | Gdzie decyzja |
|--------|--------|---------------|
| Workspace / build | Angular CLI (`angular.json`, builder `application` na esbuild) | `<web>/angular.json` |
| Routing | `@angular/router` | — |
| HTTP | `HttpClient` + interceptory | — |
| Klient API | wygenerowany z OpenAPI (`codegen: orval`, wyjście `angular`) | Profil `codegen:` |
| Formularze | Reactive Forms (typowane) | — |
| Testy | runner z `angular.json` (Vitest albo Karma/Jasmine) + TestBed; e2e Playwright | repo |
| Typowanie | TypeScript strict + `strictTemplates` | `core:typing-typescript` |

Wersję Angulara sprawdzaj w `<web>/package.json` — API zmienia się co pół roku
(główne wydania), co do konkretów pytaj Context7, nie pamięć.

## Układ katalogów

```text
<web>/
  src/
    app/
      app.config.ts        # providery aplikacji (router, HttpClient, interceptory)
      app.routes.ts        # trasy główne, lazy per feature
      core/                # interceptory, guardy, serwisy całej aplikacji
      shared/ui/           # komponenty prezentacyjne bez wiedzy o domenie
      features/<feature>/
        <feature>.routes.ts
        pages/             # komponenty tras (smart)
        components/        # komponenty prezentacyjne feature'a
        data/              # serwisy dostępu do danych, modele
      api/generated/       # klient z OpenAPI — nie edytuj ręcznie
    environments/          # tylko gdy repo ich używa; sekrety nigdy
  angular.json
  package.json
```

Feature nie importuje z wnętrza innego feature'a — wspólne do `shared/` albo `core/`.

## Zasady wspólne

- **Komponenty smart vs prezentacyjne.** Komponent trasy pobiera dane i woła serwisy;
  komponenty prezentacyjne dostają dane wejściem i zgłaszają zdarzenia wyjściem.
- **Logika poza komponentem.** Dostęp do API, mapowanie i stan współdzielony — w serwisach
  (`providedIn: 'root'` albo provider trasy), nie w klasie komponentu.
- **`ChangeDetectionStrategy.OnPush`** w nowych komponentach — wymusza dane niemutowalne
  i przewidywalne odświeżanie.
- **Szablony bez logiki.** Wywołania metod w szablonie liczą się przy każdej detekcji
  zmian — wartości pochodne licz w klasie (signal `computed` albo pipe).
- **HTTP przez interceptory** — nagłówek auth, mapowanie błędów (`arch:api-errors`),
  korelacja; nie w każdym serwisie osobno.
- **Bez manipulacji DOM** (`document.querySelector`, `nativeElement.innerHTML`) — szablon,
  dyrektywy, `Renderer2`; `innerHTML` tylko przez sanitizer Angulara.
- **Dostępność**: semantyczny HTML, etykiety pól, focus w dialogach (CDK `a11y`).

## Kontrakt API

Przy `codegen: orval` (MCP `get_codegen`) serwisy klienta są w `<web>/src/app/api/generated/` —
nie piszesz ręcznie wywołań `HttpClient` do własnego API ani interfejsów odpowiedzi.
Zmiana kontraktu po stronie backendu = regeneracja w tym samym PR (`arch:api-contract`).

## Powiązane

- `stack:angular:modern` — standalone, signals, `@if`/`@for`, `inject()`
- `stack:angular:legacy` — NgModule, RxJS-first, migracja w stronę signals
- `arch:api-contract`, `arch:api-errors`, `arch:testing`, `arch:i18n`, `core:typing-typescript`
