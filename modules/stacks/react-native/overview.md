# React Native — przegląd Stacku (mobile)

Tier `mobile: react-native`. Aplikacja React Native z CLI (`@react-native-community/cli`),
z własnymi projektami natywnymi `ios/` i `android/` w repo, nawigacją React Navigation
i budowaniem przez Xcode / Gradle. Katalog kodu: klucz `mobile:` w sekcji `## Ścieżki`
w `.ai/project.md` (dalej: `<mobile>`).

## Typowy zestaw

| Obszar | Typowo | Gdzie decyzja |
|--------|--------|---------------|
| Bundler | Metro | `<mobile>/metro.config.js` |
| Silnik JS | Hermes | `android/gradle.properties`, `ios/Podfile` |
| Architektura | New Architecture (Fabric, TurboModules) | `newArchEnabled` / `RCT_NEW_ARCH_ENABLED` |
| Nawigacja | React Navigation (native stack, tabs) | `<mobile>/package.json` |
| Stan serwera | TanStack Query (hooki z klienta przy `codegen: orval`) | Profil `codegen:` |
| Listy | `FlatList` / `FlashList` | repo |
| Konfiguracja env | `react-native-config` albo odpowiednik | overlay |
| Testy | Jest (preset `react-native`) + React Native Testing Library; e2e Detox albo Maestro | repo |
| Typowanie | TypeScript strict | `core:typing-typescript` |

Wersję React Native sprawdzaj w lockfile `<mobile>` — każde wydanie zmienia szablon
projektów natywnych; przy aktualizacji używaj React Native Upgrade Helper, nie pamięci.

## Zasady w skrócie

- **JS i natywne to jeden produkt.** Zmiana zależności z kodem natywnym = `pod install`
  i nowy build iOS/Android, nie tylko przeładowanie Metro.
- **Ekrany per feature**, nawigacja typowana (`RootStackParamList`), deep linking
  w jednej konfiguracji.
- **Platforma jawnie**: `Platform.select`, pliki `.ios.tsx` / `.android.tsx` tylko dla
  realnych różnic, nie kopiowanie całych ekranów.
- **Wydajność list i animacji**: wirtualizowane listy, animacje na wątku UI (Reanimated),
  bez ciężkiej pracy w renderze.
- **Sekrety nie w bundlu JS** — wszystko w paczce aplikacji da się odczytać.

## Moduły Stacku

- `stack:react-native:structure` — układ katalogów
- `stack:react-native:mobile-instructions` — nawigacja, moduły natywne, budowanie iOS/Android
- `stack:react-native:testing` — Jest + RNTL, mocki natywne, e2e

## Powiązane

- `arch:api-contract`, `arch:api-errors`, `arch:platforms`, `arch:testing`, `arch:i18n`,
  `core:typing-typescript`
