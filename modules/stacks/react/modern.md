# React 19+ — aktualne podejście

Tier `web: react`. Uzupełnia `stack:react` (wspólne zasady i układ `<web>`). Gdy lockfile
pokazuje React < 19 — to nie ten moduł, zmień Tier na `react@legacy`.

## Kompilator zamiast ręcznej memoizacji

- React Compiler (plugin Babel/Vite) memoizuje komponenty i wartości sam. W nowym kodzie
  **nie** dodawaj `useMemo`, `useCallback`, `React.memo` „na zapas”.
- Ręczna memoizacja tylko z powodem, który kompilator nie pokrywa (np. stabilna referencja
  wymagana przez bibliotekę zewnętrzną) — z komentarzem dlaczego.
- Kompilator zakłada czyste komponenty: bez mutacji propsów/stanu, bez odczytu `ref.current`
  w renderze. Kod łamiący reguły kompilator pomija — lint (`eslint-plugin-react-compiler` /
  reguły w `eslint-plugin-react-hooks`) to wychwyci.
- Gdy kompilator nie jest jeszcze włączony w repo — sprawdź `vite.config.ts`; nie dopisuj
  memoizacji, zaproponuj włączenie kompilatora.

## Actions i formularze

- Formularz wysyłany przez akcję: `<form action={submit}>`, gdzie `submit` to funkcja
  (może być `async`) dostająca `FormData`. React sam obsługuje stan „w toku” i reset formularza.
- `useActionState(action, initialState)` → `[state, formAction, isPending]` — wynik
  (błędy walidacji, komunikat) i stan wysyłki bez ręcznego `useState` na `loading`/`error`.
- `useFormStatus()` w komponencie wewnątrz `<form>` (np. przycisk submit) — `pending`
  bez przekazywania propsów.
- `useOptimistic` dla natychmiastowej odpowiedzi UI (polubienie, dodanie do listy),
  porzucanej automatycznie po zakończeniu akcji (sukces lub błąd) — po sukcesie zaktualizuj
  właściwy stan / unieważnij query, inaczej zmiana zniknie.
- `useTransition` / `startTransition` dla aktualizacji niepilnych (filtrowanie, nawigacja),
  także z funkcją `async`.
- Walidacja: schemat (np. `zod`) współdzielony między walidacją klienta a typem danych;
  błędy serwera mapowane z formatu `arch:api-errors` na pola formularza.
- Duże, dynamiczne formularze (tablice pól, zależności) — `react-hook-form`, jeśli repo
  go używa; nie mieszaj dwóch podejść w jednym formularzu.

## `use()` i Suspense

- `use(promise)` odczytuje wynik obietnicy w renderze i zawiesza komponent do jej
  rozwiązania — najbliższy `<Suspense>` pokazuje fallback, error boundary łapie odrzucenie.
- Obietnica musi być stabilna (utworzona poza renderem albo z cache biblioteki) — `use(fetch(...))`
  w renderze tworzy nowe żądanie przy każdym renderze.
- `use(Context)` działa także warunkowo (w `if`), w odróżnieniu od `useContext`.
- Dane z API dalej przez TanStack Query (`useSuspenseQuery`, gdy trasa używa Suspense) —
  `use()` to prymityw, nie zamiennik cache.

## Zmiany API względem 18

- `ref` to zwykły prop komponentu funkcyjnego — bez `forwardRef` w nowym kodzie.
- `<Context value={...}>` jako provider zamiast `<Context.Provider>`.
- Funkcja czyszcząca w ref callback (`ref={(node) => { …; return () => … }}`).
- `<title>`, `<meta>`, `<link>` renderowane w komponencie trafiają do `<head>` — bez
  osobnej biblioteki do metadanych dla prostych przypadków.
- Usunięte: `propTypes`/`defaultProps` w komponentach funkcyjnych (typy TS i domyślne
  parametry), legacy context, string refs, `ReactDOM.render` (`createRoot`).

## Routing

- Routing w `<web>/src/app/`; trasy ładowane leniwie (`lazy`) per feature.
- Dane trasy: loader routera albo `queryClient.ensureQueryData` w loaderze + hook
  w komponencie — jedno źródło (cache Query), nie dwa.
- URL jest stanem: filtry, paginacja, zakładki w parametrach wyszukiwania, nie w `useState`.

## Stan

| Rodzaj | Narzędzie |
|--------|-----------|
| Dane z API | TanStack Query (unieważnianie po mutacji: `invalidateQueries`) |
| Stan formularza / wysyłki | actions (`useActionState`, `useFormStatus`) |
| Stan UI lokalny | `useState` / `useReducer` |
| Stan współdzielony bez API | Context (rzadko zmienny) albo Zustand (często zmienny) |
| Stan w URL | parametry routera |

## Testy

- Vitest + Testing Library: zapytania po roli i etykiecie (`getByRole`, `getByLabelText`),
  interakcje `userEvent`, asercje na tym, co widzi użytkownik — nie na stanie komponentu.
- API mockowane na granicy sieci (MSW z handlerami zgodnymi z kontraktem), nie przez
  mock hooka z wygenerowanego klienta.
- Akcje i Suspense: `await screen.findBy...` zamiast sztucznych timeoutów.
- Ścieżki krytyczne (logowanie, zakup) — e2e Playwright (`arch:testing`).
