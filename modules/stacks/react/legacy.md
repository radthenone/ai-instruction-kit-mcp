# React 16–18 — starsze podejście (`react@legacy`)

Tier `web: react@legacy`. Uzupełnia `stack:react` (wspólne zasady i układ `<web>`).
Dotyczy repo, które jeszcze nie są na React 19 — wersję potwierdza lockfile `<web>`.
Pisz kod, który działa **teraz** i nie utrudnia migracji (sekcja na końcu).

## Hooki

- Komponenty funkcyjne + hooki (React ≥ 16.8). Komponenty klasowe tylko w istniejącym
  kodzie i w error boundary; nowych nie dopisuj.
- `useEffect` z pełną listą zależności — lint `react-hooks/exhaustive-deps` nie jest
  wyciszany. Zależność, która „nie powinna” być na liście, to sygnał, że logika nie
  należy do efektu (obsługa zdarzenia, wartość pochodna) albo potrzebuje `useRef`.
- React 18 + `StrictMode` w dev montuje komponent dwa razy — efekt musi mieć sprzątanie
  (unsubscribe, `AbortController`); podwójne żądanie w dev to objaw braku sprzątania,
  nie powód do wyłączenia StrictMode.
- `forwardRef` dla komponentów, które przekazują `ref` do elementu DOM; `useImperativeHandle`
  tylko gdy rodzic naprawdę potrzebuje metody, nie stanu.

## Ręczna memoizacja

Bez kompilatora memoizacja jest ręczna — ale celowana, nie „wszędzie”:

| Narzędzie | Kiedy ma sens |
|-----------|----------------|
| `React.memo` | komponent renderuje się często z tymi samymi propsami i jest kosztowny (długa lista, wykres) |
| `useMemo` | kosztowne przeliczenie albo obiekt/tablica przekazywane do `memo`-komponentu lub do zależności efektu |
| `useCallback` | funkcja przekazywana do `memo`-komponentu albo używana w zależnościach efektu |

- Memoizacja bez odbiorcy, który porównuje referencje, nic nie daje — tylko koszt i szum.
- Najpierw strukturą: przenieś stan niżej, przekaż `children` zamiast renderować ciężkie
  dzieci w zmieniającym się rodzicu. Dopiero potem `memo`.
- Wydajność mierz React DevTools Profilerem, nie na oko.

## Pobieranie danych: `useEffect` vs biblioteka

- Dane z własnego API → TanStack Query (albo hooki z wygenerowanego klienta przy
  `codegen: orval`). Daje cache, deduplikację, ponowienia, unieważnianie po mutacji
  i obsługę wyścigów.
- Ręczny `fetch` w `useEffect` tylko dla jednorazowych, nieudostępnianych danych —
  i wtedy obowiązkowo: `AbortController` w sprzątaniu, obsługa stanu błędu i ładowania,
  ignorowanie odpowiedzi po odmontowaniu / zmianie parametrów.
- Nie kopiuj danych z zapytania do `useState` „żeby edytować” — formularz dostaje
  `defaultValues` z danych, mutacja idzie przez `useMutation` + `invalidateQueries`.

## Formularze

- Kontrolowane pola (`value` + `onChange`) dla prostych formularzy; większe —
  `react-hook-form` (niekontrolowane, mniej renderów), jeśli repo go używa.
- Stan wysyłki z `useMutation` (`isPending`, `error`), nie trzy osobne `useState`.
- Walidacja schematem (np. `zod`) współdzielonym z typem danych; błędy serwera
  (`arch:api-errors`) mapowane na pola.

## React 18 — co już jest dostępne

- `createRoot` zamiast `ReactDOM.render` (React 18); automatyczny batching aktualizacji
  także w promise'ach i timeoutach.
- `useTransition` / `useDeferredValue` dla aktualizacji niepilnych (filtrowanie listy).
- `useId` dla identyfikatorów `label`/`aria-*` zamiast liczników.
- `<Suspense>` dla `React.lazy`; Suspense dla danych — przez bibliotekę
  (`useSuspenseQuery`), nie własny mechanizm rzucania obietnic.

## Migracja w stronę modern (`stack:react:modern`)

Każda zmiana w legacy kodzie powinna zbliżać do 19, nie oddalać:

1. Usuń ostrzeżenia z konsoli React 18 i `StrictMode` (to lista problemów na 19).
2. Komponenty klasowe → funkcyjne przy okazji zmian w nich; `defaultProps`/`propTypes`
   w komponentach funkcyjnych → domyślne parametry i typy TS (19 je usuwa).
3. String refs, legacy context, `findDOMNode` → `useRef`, `createContext`, refy na elementach
   (19 ich nie ma).
4. Ręczne pobieranie w efektach → TanStack Query.
5. Aktualizacja do 19 (codemody `react-codemod`), potem włączenie kompilatora i usuwanie
   ręcznej memoizacji tam, gdzie nie jest potrzebna z innego powodu.
6. Po migracji: Tier `web: react` w `.ai/project.profile.yaml` + `kit-ai reload`.

Nie pisz nowego kodu w API, które 19 usuwa — nawet jeśli 18 je jeszcze wspiera.

## Testy

- Vitest albo Jest (wg repo) + Testing Library: zapytania po roli i etykiecie,
  `userEvent`, `await findBy...` dla asynchronicznych zmian.
- API mockowane na granicy sieci (MSW), nie przez mock hooków.
- Ostrzeżenie `act(...)` w teście to sygnał niedoczekanej aktualizacji — czekaj na
  efekt widoczny dla użytkownika, nie owijaj na ślepo w `act`.
