# Mobile instructions — React Native

## Zakres

Zmiany w `<mobile>/**` (klucz `mobile:` w `## Ścieżki` w `.ai/project.md`). Układ:
`stack:react-native:structure`. API React Native i bibliotek natywnych zmienia się między
wydaniami — wersje z lockfile, konkrety z Context7.

## Nawigacja (React Navigation)

- Native stack (`@react-navigation/native-stack`) jako domyślny — natywne przejścia;
  zakładki `@react-navigation/bottom-tabs`.
- Typowane trasy: `RootStackParamList` + `NativeStackScreenProps<RootStackParamList, 'Order'>`;
  `useNavigation` typowane przez deklarację globalną `RootParamList`.
- Parametry tras to identyfikatory i proste wartości — nie całe obiekty z API (dane
  dociąga ekran przez cache zapytań).
- Deep linking w jednym miejscu (`linking.ts`: `prefixes`, `config` z mapą ekranów);
  zmiana ścieżki ekranu = zmiana publicznego URL-a aplikacji.
- Ekran autoryzacji przez warunkowe drzewo nawigatorów (zalogowany / niezalogowany),
  nie przez `navigate` po starcie.

## Moduły natywne

- Biblioteka z kodem natywnym: autolinking robi podpięcie — po instalacji
  `cd ios && pod install` i pełny rebuild obu platform. Sprawdź zgodność z New
  Architecture (Fabric / TurboModules), zanim dodasz zależność.
- Własny moduł natywny: TurboModule ze specyfikacją TypeScript (Codegen generuje
  interfejsy) — nie stary `NativeModules` bez typów w nowym kodzie.
- Natywne uprawnienia (kamera, lokalizacja, powiadomienia): wpisy w `Info.plist`
  (`NS…UsageDescription`) i `AndroidManifest.xml` w tym samym PR, co kod, który ich
  używa; pytanie o zgodę w momencie użycia, nie na starcie.
- Kod zależny od platformy: `Platform.OS` / `Platform.select` dla drobnych różnic,
  `Komponent.ios.tsx` / `Komponent.android.tsx` dla większych.

## Budowanie iOS

- `pod install` w `ios/` po każdej zmianie zależności natywnych; commituj `Podfile.lock`.
- Otwieraj `*.xcworkspace`, nie `*.xcodeproj`.
- Podpisywanie, profile i wersje (`CFBundleShortVersionString`, build number) —
  konfiguracja w overlayu / CI (fastlane albo odpowiednik), nie ręcznie w PR.
- Build release lokalnie przynajmniej raz po zmianie natywnej — debug ukrywa błędy
  minifikacji i Hermesa.

## Budowanie Android

- Gradle wrapper z repo (`./gradlew`), JDK w wersji z dokumentacji danego wydania RN.
- `versionCode` rośnie przy każdym wydaniu; `applicationId` stały.
- Keystore i hasła poza repo (zmienne CI / `~/.gradle/gradle.properties`).
- Release: `./gradlew bundleRelease` (AAB do sklepu); sprawdź reguły ProGuard/R8,
  jeśli biblioteka natywna ich wymaga.

## Dane i API

- Dane z backendu przez TanStack Query (przy `codegen: orval` — wygenerowane hooki);
  `focusManager` / `onlineManager` podpięte pod `AppState` i stan sieci.
- Błędy API w formacie `arch:api-errors`; brak sieci to osobny stan UI, nie generyczny błąd.
- Sekrety (klucze API z uprawnieniami) nie w bundlu JS ani w `react-native-config` —
  przez backend. Tokeny użytkownika w Keychain / Keystore, nie w `AsyncStorage`.

## UI i wydajność

- `SafeAreaView` / `useSafeAreaInsets` z `react-native-safe-area-context`.
- Długie listy: `FlatList`/`FlashList` z `keyExtractor` po `id`, bez `ScrollView` + `map`.
- Animacje i gesty: Reanimated + Gesture Handler (wątek UI); bez animowania przez `setState`.
- Obrazy w odpowiednim rozmiarze i z cache; dostępność: `accessibilityLabel`,
  `accessibilityRole`, minimalne pole dotyku ~44pt.

## Zasady obowiązkowe

- Zmiana natywna (zależność, uprawnienie, konfiguracja) wymaga nowego buildu aplikacji —
  zaznacz to w opisie PR.
- Testy do każdej zmiany zachowania (`stack:react-native:testing`).
- Taski (Metro, buildy, e2e) — `.ai/project.md`.
