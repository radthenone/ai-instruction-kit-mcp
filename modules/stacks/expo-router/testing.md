# Testing — Frontend (Expo Router / React)

## Stack (zalecany)

| Narzędzie | Rola |
|-----------|------|
| **Jest** (Expo default) lub **Vitest** (Vite/React web) | runner |
| **@testing-library/react-native** lub **@testing-library/react** | interakcje UI |
| **MSW** (Mock Service Worker) | HTTP / kontrakt API bez prawdziwego BE |
| **@testing-library/jest-dom** (web) | asercje DOM |
| React Native Testing Library matchers | asercje mobile |

Wybór runnera trzymamy w lockfile projektu; agenci nie mieszają Jest i Vitest w jednym pakiecie
bez migracji.

## Layout

```text
frontend/
  src/
    test/
      setup.ts              # import matchers, MSW listen
      server.ts             # MSW setupServer / setupWorker
      handlers.ts           # handlery OpenAPI-shaped
      render.tsx            # wrapper: QueryClient, Navigation, theme
    features/<feature>/
      __tests__/
        CheckoutForm.test.tsx
      # albo
      CheckoutForm.test.tsx
    core/
      hooks/
        useDebounce.test.ts
```

Jeden `render` helper z providerami (TanStack Query, safe area, i18n) — nie kopiuj
providerów w każdym teście.

## Piramida FE

| Warstwa | Co | Narzędzia |
|---------|-----|-----------|
| Unit | utils, hooki, czyste funkcje mapujące DTO → UI | Jest/Vitest |
| Component | render + userEvent / fireEvent; stany loading/error/empty | Testing Library |
| Feature / integration | ekran + MSW (happy + error path) | Testing Library + MSW |
| E2E | krytyczne ścieżki web/mobile | Playwright / Detox / Maestro — rzadko |

**Query / użytkownik:** testuj to, co widzi użytkownik (`getByRole`, `getByLabelText`),
nie szczegóły implementacji (`testID` tylko gdy brak roli a11y).

## MSW i kontrakt API

- Handlery zwracają kształt zgodny z OpenAPI / wygenerowanym klientem Orval.
- Po zmianie API: regeneracja klienta (`arch:api-contract`) + aktualizacja handlerów.
- Nie `fetch` mock ad-hoc w każdym teście — centralne `handlers.ts`.

```text
src/test/handlers.ts   # GET/POST zgodne z /api/...
src/test/server.ts      # setupServer(...handlers)
```

W `beforeAll` → `server.listen()`; `afterEach` → `server.resetHandlers()`;
`afterAll` → `server.close()`.

## Co mockować

| Mockuj | Nie mockuj (w unit/component) |
|--------|-------------------------------|
| Sieć (MSW) | Logika lokalnego stanu (Zustand) — testuj ją |
| Native modules bez JS (SecureStore, Camera) | Proste komponenty prezentacyjne |
| Nawigacja głęboka (opcjonalnie mock router) | Cały drzewo aplikacji w każdym teście |

Sesja / auth: fixture user + handler `/_allauth/...` lub odpowiednik JWT — spójnie
z `capability:auth`.

## Przykładowe zasady asercji

1. Arrange: `render(<Screen />)` + MSW stan.
2. Act: `userEvent` / `fireEvent.press`.
3. Assert: tekst, rola, wywołanie mutacji (czekaj na UI lub `waitFor`).

Unikaj snapshotów całych drzew ekranów jako jedynej asercji — snapshot tylko dla
stabilnych, małych fragmentów (ikona, token stylu) jeśli w ogóle.

## Expo: web vs native

| Cel | Uwagi |
|-----|--------|
| Wspólny kod w `src/` | Testuj raz z odpowiednim presetem (RN Testing Library) |
| Pliki `.web` / `.native` | Osobne testy lub `jest-expo` platform; nie zakładaj jednego DOM |
| SecureStore / AsyncStorage | mock modułu w `setup` |

Job CI PR: `task test:frontend` (lub `bun test` / `npm test`) — bez EAS.
EAS / Detox: merge, nightly lub manual (`arch:ci-cd`).

## Komendy

```bash
task test:frontend
# lub w frontend/
bun test
# integracyjne (gdy wydzielone)
bun test --testPathPattern=integration
```

## Antywzorce

- Testowanie szczegółów stylu / className zamiast zachowania.
- Prawdziwy backend w unitach (flaky, wolne, CI zależne od compose FE).
- `act(...)` warnings ignorowane — napraw async.
- Jeden mega-test całego checkoutu zamiast małych scenariuszy + 1 integration.
- Duplikowanie typów odpowiedzi zamiast typów z Orval.

## Definition of Done (zmiana UI / feature)

- [ ] Unit lub component test dla happy path
- [ ] Stan błędu / pusty (gdy UX je pokazuje)
- [ ] MSW zaktualizowany przy nowym endpoincie
- [ ] Brak nowych ostrzeżeń act / peer dependency w CI

## Powiązane

- `arch:testing` — polityka monorepo
- `arch:api-contract` — Orval / drift
- `stack:expo-router:structure` — układ `src/`
- `arch:ui-ux-expo` — a11y (role, label — sprzyja testom)
- `capability:payments:expo-stripe` — mock Stripe SDK, nie żywe charge
