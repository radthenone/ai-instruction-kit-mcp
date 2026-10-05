# Testing — React Native (Jest + React Native Testing Library)

## Stack

| Narzędzie | Rola |
|-----------|------|
| `jest` (preset `react-native`) | runner, transformacje Babel |
| `@testing-library/react-native` | render komponentów, zapytania jak użytkownik |
| `msw` (tryb Node) / mock klienta HTTP na granicy | API |
| Detox albo Maestro | e2e na symulatorze / emulatorze |

Konfiguracja w `<mobile>/jest.config.js`: `preset: 'react-native'`, `setupFiles`
z mockami natywnymi, `transformIgnorePatterns` dla bibliotek publikowanych jako ESM.

## Mocki modułów natywnych

- W Jest nie ma natywnej warstwy — każdy moduł natywny potrzebuje mocka. Wiele bibliotek
  dostarcza gotowy (`react-native-gesture-handler/jestSetup`, mock Reanimated,
  `@react-native-async-storage/async-storage/jest/async-storage-mock`) — używaj ich
  zamiast własnych.
- Własne TurboModules: mock w `jest.setup.ts` (`jest.mock('./NativeOrders', ...)`)
  zgodny ze specyfikacją TS modułu.
- Nawigacja: renderuj ekran w prawdziwym `NavigationContainer` z małym stosem testowym
  zamiast mockować `useNavigation` — test łapie wtedy błędy parametrów tras.

## Testy komponentów i ekranów

- Zapytania po tym, co widzi użytkownik: `getByRole`, `getByText`, `getByLabelText`
  (dostępność); `testID` tylko gdy nic innego nie identyfikuje elementu.
- Interakcje `userEvent` (`press`, `type`) zamiast wołania propsów ręcznie.
- Asynchroniczność: `await screen.findBy...` / `waitFor`, nie sztuczne timeouty.
- Dane: `QueryClient` testowy (`retry: false`) w wrapperze; API mockowane na granicy sieci.
- Kod platformowy: test dla `Platform.OS` obu platform, gdy zachowanie się różni.

## E2E

- Detox (szare pudełko, synchronizacja z aplikacją) albo Maestro (flowy YAML) — wg repo.
- Scenariusze krytyczne: logowanie, główna ścieżka zakupu / formularza, deep link,
  zgoda na uprawnienie.
- Build e2e osobny od dev (release-like), uruchamiany w CI na emulatorze Androida
  i symulatorze iOS (`arch:testing`).

## Czego nie testować w Jest

- Wyglądu natywnych komponentów i animacji — to rola e2e albo testów zrzutów na urządzeniu.
- Samego linkowania modułów natywnych — to sprawdza build iOS/Android w CI.

## Powiązane

- `arch:testing` — piramida i polityka CI
- `stack:react-native:mobile-instructions` — moduły natywne, nawigacja
