# UI/UX — Expo / React Native

## Zasady ogólne

- Mobile-first — projektuj dla touch, safe area, keyboard.
- Spójność: wspólne komponenty w `src/ui/`, warianty przez CVA + NativeWind.
- Web vs native: pliki `.web.tsx` / `.native.tsx` lub helpery w `src/ui/platform/`.
- Nie używaj DOM-only API (np. klasyczny shadcn/ui) bez weryfikacji na native.

## Stan a UX

| Typ danych | Narzędzie | UX |
|------------|-----------|-----|
| Lista z API | TanStack Query | skeleton, pull-to-refresh, empty state |
| Formularz | react-hook-form + zod | inline errors, disable submit |
| UI tymczasowy | Zustand | modale, bottom sheets |

## Performance

- `React.lazy` / lazy routes dla ciężkich ekranów (web).
- Debounce wyszukiwania — `useDebouncedValue` + `enabled` w query.
- Obrazy: optymalizacja rozmiaru, placeholder (expo-image).
- Unikaj zbędnych re-renderów — stabilne referencje w hookach.

## Dostępność (a11y)

Minimum (web + native):

| Zasada | Opis |
|--------|------|
| Touch target | min. ~44×44 pt |
| Kontrast | tokeny theme — nie losowy gray na gray |
| Etykiety | każde pole formularza: widoczny label / `accessibilityLabel` |
| Role | przyciski jako button; unikaj `View` + `onPress` bez roli |
| Stan | loading / disabled / error komunikowane nie tylko kolorem |
| Dynamiczny typ | nie tnij fontów systemowych bez powodu |

Testy: preferuj `getByRole` / `getByLabelText` (`stack:expo-router:testing`).
Głębsze WCAG / audit — według wymagań produktu w overlay.

## Design system

- Tokeny kolorów/spacing w theme — nie hardcode w feature.
- shadcn-like w Expo: lokalne primitives + NativeWind + `class-variance-authority`.

## Powiązane moduły

- `stack:expo-router:structure`
- `stack:expo-router:testing` — a11y-friendly queries
- `arch:i18n` — copy UI
- `capability:auth` — flow logowania, MFA
