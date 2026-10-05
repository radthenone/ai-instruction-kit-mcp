# Angular — aktualne podejście (standalone + signals)

Tier `web: angular`. Uzupełnia `stack:angular` (wspólne zasady i układ `<web>`). Zakłada
Angular z signals i nowym control flow (17+); konkretne API sprawdzaj w wersji z
`<web>/package.json`.

## Standalone components

- Każdy nowy komponent, dyrektywa i pipe jest standalone; zależności szablonu w `imports`
  komponentu. Bez nowych `NgModule`.
- Bootstrap: `bootstrapApplication(AppComponent, appConfig)`; providery w `app.config.ts`
  (`provideRouter(routes)`, `provideHttpClient(withInterceptors([...]))`).
- W nowszych wersjach standalone jest domyślne — nie dopisuj `standalone: true`, jeśli
  wersja tego nie wymaga (sprawdź istniejące komponenty).

## Signals

- Stan komponentu i serwisu jako `signal()`; wartości pochodne `computed()`; aktualizacja
  `set()` / `update()` — bez mutowania obiektu w środku sygnału.
- Wejścia i wyjścia funkcjami: `input()` / `input.required()`, `output()`, dwustronne
  `model()` — zamiast dekoratorów `@Input`/`@Output` w nowym kodzie.
- `effect()` tylko do synchronizacji z czymś spoza Angulara (localStorage, biblioteka
  wykresów, logowanie). Przeliczenie stanu w efekcie = błąd — użyj `computed()`
  (albo `linkedSignal()`, gdy wartość ma się resetować przy zmianie źródła).
- Odczyty z `ViewChild`/`ContentChild` przez `viewChild()` / `contentChild()`.
- Most do RxJS: `toSignal(obs$)` w komponencie (z `initialValue` albo
  `requireSync`), `toObservable(sig)` gdy potrzebny operator RxJS (debounce, switchMap).
  Strumienie zdarzeń i anulowanie żądań nadal dobrze wyraża RxJS — nie przepisuj ich na siłę.
- Dane asynchroniczne zależne od sygnałów: `resource()` / `httpResource()`, jeśli wersja
  w repo je ma i repo ich używa — inaczej serwis z `HttpClient` + `toSignal`.

## Szablony: `@if` / `@for` / `@switch` / `@defer`

```html
@if (order(); as order) {
  <app-order-summary [order]="order" />
} @else {
  <app-spinner />
}

@for (line of lines(); track line.id) {
  <app-order-line [line]="line" />
} @empty {
  <p>Brak pozycji.</p>
}
```

- `track` w `@for` obowiązkowe — po stabilnym identyfikatorze z danych, nie `$index`
  dla list zmiennych.
- `@defer (on viewport)` dla ciężkich, niekrytycznych fragmentów (wykres, komentarze)
  z `@placeholder` / `@loading`.
- Nowy kod bez `*ngIf`/`*ngFor`/`[ngSwitch]`; migracja istniejących:
  `ng generate @angular/core:control-flow`.

## Wstrzykiwanie: `inject()`

- `private readonly orders = inject(OrderService)` w polach klasy zamiast parametrów
  konstruktora — działa też w funkcjach (guardy, interceptory, resolvery).
- `inject()` tylko w kontekście wstrzykiwania (pole klasy, konstruktor, fabryka providera);
  poza nim `runInInjectionContext`.
- Konfiguracja przez `InjectionToken` + provider, nie importy stałych z `environments/`
  rozsiane po kodzie.

## Routing

- Trasy w `app.routes.ts` i `<feature>.routes.ts`; feature ładowany leniwie
  (`loadChildren: () => import(...)`, `loadComponent`).
- Guardy, resolvery i interceptory funkcyjne (`CanActivateFn`, `ResolveFn`,
  `HttpInterceptorFn`) — bez klas implementujących interfejsy.
- Parametry trasy jako wejścia komponentu: `withComponentInputBinding()` + `input()`.
- URL jest stanem: filtry i paginacja w query params.

## Formularze

- Reactive Forms typowane: `FormBuilder.nonNullable.group({...})`; typ wartości wynika
  z definicji, bez `any`.
- Walidatory synchroniczne funkcjami; asynchroniczne z debounce; błędy serwera
  (`arch:api-errors`) mapowane na kontrolki (`setErrors`).
- Stan formularza do szablonu przez signals (`toSignal(form.statusChanges)`) albo
  bezpośrednio z kontrolek — bez ręcznego `subscribe` w komponencie.
- Signal Forms tylko, jeśli wersja w repo je ma jako stabilne i repo ich używa.

## HttpClient

- `provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))` w `app.config.ts`;
  `withFetch()` przy SSR.
- Serwis zwraca dane domenowe (zmapowane), komponent nie zna kształtu surowej odpowiedzi.
- Przy `codegen: orval` używaj wygenerowanych serwisów zamiast ręcznego `HttpClient`.

## Detekcja zmian

- Signals + `OnPush` to droga do aplikacji bez zone.js (`provideZonelessChangeDetection()`),
  jeśli repo jest zoneless albo to planuje. W kodzie zoneless nie polegaj na tym, że
  `setTimeout` czy `Promise` odświeżą widok — aktualizuj sygnał.

## Testy

- TestBed z komponentami standalone: `imports: [OrderPageComponent]`, providery
  `provideHttpClient()`, `provideHttpClientTesting()`, `provideRouter([])`.
- HTTP: `HttpTestingController` (`expectOne`, `flush`, `verify` w `afterEach`).
- Wejścia signal: `fixture.componentRef.setInput('order', ...)`.
- Angular Testing Library (zapytania po roli i etykiecie), jeśli repo jej używa.
- Runner wg `angular.json` (Vitest albo Karma) — nie zmieniaj go przy okazji.
