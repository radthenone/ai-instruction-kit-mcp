# Struktura katalogów — React Native

`<mobile>` = klucz `mobile:` w sekcji `## Ścieżki` w `.ai/project.md`. Poniżej układ
względem tego katalogu — gdy repo ma inny, trzymaj się repo i opisz rozjazd w overlayu.
Wspólny pakiet typów / UI z web (gdy Tier web też jest wybrany): ścieżka w overlayu.

## Layout

```text
<mobile>/
  src/
    app/
      App.tsx              # providery (QueryClient, SafeArea, Navigation)
      navigation/
        RootNavigator.tsx
        linking.ts         # deep linking
        types.ts           # RootStackParamList
    features/<feature>/
      screens/
      components/
      hooks/
    shared/
      ui/                  # komponenty bez wiedzy o domenie
      lib/
    api/generated/         # klient z OpenAPI — nie edytuj ręcznie
  ios/                     # projekt Xcode, Podfile, Podfile.lock
  android/                 # projekt Gradle, app/build.gradle
  __tests__/ albo src/**/*.test.tsx
  e2e/                     # Detox / Maestro
  index.js                 # AppRegistry.registerComponent
  metro.config.js
  babel.config.js
  package.json
```

## Zasady

- Feature nie importuje z wnętrza innego feature'a — wspólne do `shared/`.
- `ios/` i `android/` to kod źródłowy, nie artefakt: commitowane, przeglądane w PR
  (`Podfile.lock` też). Katalogi build (`ios/build`, `android/app/build`, `Pods/`) — w `.gitignore`.
- Natywny kod własny (moduły, widoki) w `ios/<App>/` i `android/app/src/main/java|kotlin/`
  albo w osobnym pakiecie w repo — opisz wybór w overlayu.
- Assety (fonty, obrazy) z jednego źródła i podpinane do obu platform jednym
  mechanizmem (`react-native.config.js`), nie kopiowane ręcznie.
