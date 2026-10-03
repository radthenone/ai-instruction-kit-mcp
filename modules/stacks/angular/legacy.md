# Angular — NgModule + RxJS (`angular@rxjs`)

Tier `web: angular@rxjs`. Uzupełnia `stack:angular` (wspólne zasady i układ `<web>`).
Dotyczy repo opartych o `NgModule`, dekoratory `@Input`/`@Output` i RxJS jako głównym
modelu stanu. Pisz kod spójny z repo, który nie utrudnia migracji (sekcja na końcu).

## NgModule

- Moduł per feature (`OrdersModule`) z własnym routingiem (`RouterModule.forChild`),
  ładowany leniwie: `loadChildren: () => import('./orders/orders.module').then(m => m.OrdersModule)`.
- `SharedModule` tylko z komponentami prezentacyjnymi, dyrektywami i pipe'ami
  (eksportowanymi); bez serwisów w `providers` — inaczej każdy leniwy moduł dostaje
  własną instancję.
- `CoreModule` (importowany raz w `AppModule`): interceptory (`HTTP_INTERCEPTORS`),
  guardy, serwisy singletonowe. Serwisy wolą `providedIn: 'root'` niż `providers` modułu.
- Nowy komponent w istniejącym feature'rze deklaruj w jego module. Nowy, samodzielny
  fragment (np. nowy feature) może już być standalone i importowany do modułu —
  to pierwszy krok migracji, nie niespójność.

## RxJS-first

- Dane jako `Observable` z serwisu; komponent składa strumienie, szablon je wyświetla.
- **`async` pipe** zamiast `subscribe` w komponencie — sam się wypisuje i współgra z `OnPush`:

```html
<ng-container *ngIf="vm$ | async as vm; else loading">
  <app-order-line *ngFor="let line of vm.lines; trackBy: trackById" [line]="line"></app-order-line>
</ng-container>
<ng-template #loading><app-spinner></app-spinner></ng-template>
```

- Jeden `vm$` (`combineLatest` / `map`) na widok zamiast wielu `| async` na tym samym
  źródle — każdy `async` pipe to osobna subskrypcja (i osobne żądanie HTTP dla zimnych
  obserwabli).
- Operatory spłaszczania świadomie: `switchMap` (wyszukiwanie, nawigacja — anuluje
  poprzednie), `concatMap` (zapisy w kolejności), `exhaustMap` (przycisk submit —
  ignoruje kolejne kliknięcia), `mergeMap` (niezależne równoległe).
- Współdzielenie wyniku: `shareReplay({ bufferSize: 1, refCount: true })`; bez
  `refCount` strumień żyje po odejściu ostatniego subskrybenta.
- Stan serwisu: `BehaviorSubject` prywatnie + publiczny `asObservable()`; komponenty
  nie wołają `next()` na cudzym subjekcie.
- Błędy: `catchError` w serwisie mapuje na stan błędu albo wyjątek domenowy
  (`arch:api-errors`); strumień widoku nie umiera po pierwszym błędzie.

## Zarządzanie subskrypcjami

Ręczny `subscribe` tylko gdy nie da się `async` pipe (efekt uboczny: nawigacja,
zapis do localStorage, integracja z biblioteką). Wtedy zawsze z wypisaniem:

- `takeUntilDestroyed(this.destroyRef)` (Angular 16+) — preferowane;
- starsze wersje: `takeUntil(this.destroy$)` jako **ostatni** operator, `destroy$.next()`
  i `complete()` w `ngOnDestroy`.

Nie: zagnieżdżone `subscribe` w `subscribe` (użyj operatora spłaszczania), ręczne
tablice `Subscription` bez sprzątania, `toPromise()` (przestarzałe — `firstValueFrom`).

## Szablony: `*ngIf` / `*ngFor`

- `*ngFor` zawsze z `trackBy` (funkcja po `id`) dla list zmiennych.
- `*ngIf="x$ | async as x; else tpl"` zamiast podwójnych subskrypcji.
- `[ngSwitch]` dla wielu wariantów; logika poza szablonem (pipe albo pole w `vm$`).
- Gdy wersja Angulara w repo ma nowy control flow (17+), nowy kod może go używać —
  migracja całości: `ng generate @angular/core:control-flow`.

## Formularze i HTTP

- Reactive Forms (`FormGroup`, `FormBuilder`); typowane, jeśli wersja ≥ 14.
- `valueChanges` przez operatory (`debounceTime`, `distinctUntilChanged`, `switchMap`)
  zamiast reagowania w `subscribe`.
- Interceptory klasowe (`HttpInterceptor` + `HTTP_INTERCEPTORS`, `multi: true`) — tak,
  jak repo je ma; nowe interceptory funkcyjne tylko po przejściu na `provideHttpClient`.

## Testy

- TestBed z modułem feature'a albo deklaracjami komponentu; `HttpClientTestingModule`
  + `HttpTestingController` (`expectOne`, `flush`, `verify`).
- Strumienie: `fakeAsync` + `tick` dla czasu (`debounceTime`), marble testing
  (`TestScheduler`) dla złożonych operatorów.
- Komponent z `OnPush`: zmiana wejścia przez `fixture.componentRef.setInput`, potem
  `detectChanges()`.

## Migracja w stronę signals (`stack:angular:modern`)

Zmiany w legacy kodzie mają zbliżać do modern:

1. Nowe komponenty, dyrektywy i pipe'y standalone; istniejące konwertuj schematem
   `ng generate @angular/core:standalone` (etapami: konwersja → usunięcie modułów →
   bootstrap `bootstrapApplication`).
2. `*ngIf`/`*ngFor` → `@if`/`@for` (`control-flow` schematic).
3. Wstrzykiwanie w konstruktorze → `inject()` (`inject` schematic).
4. `@Input`/`@Output` → `input()`/`output()` (schematics `signal-input-migration`,
   `output-migration`).
5. Stan widoku: `vm$ | async` → `toSignal(vm$)` + `computed()`; RxJS zostaje tam, gdzie
   wyraża czas i anulowanie (`switchMap`, `debounceTime`).
6. Moduły klasowe `HTTP_INTERCEPTORS`/guardy → funkcyjne przy `provideHttpClient` /
   `provideRouter`.
7. Po migracji: Tier `web: angular` w `.ai/project.profile.yaml` + `kit-ai reload`.

Każdy schematic uruchamiaj osobnym commitem, z przejściem testów — nie mieszaj migracji
z funkcją.
