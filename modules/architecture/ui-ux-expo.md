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

## Dostępność

- Touch targets min. 44pt.
- Kontrast kolorów (theme w `core/theme/`).
- Label dla pól formularza.

## Design system

- Tokeny kolorów/spacing w theme — nie hardcode w feature.
- shadcn-like w Expo: lokalne primitives + NativeWind + `class-variance-authority`.

## Powiązane moduły

- `stack:expo-router:structure`
- `capability:auth` — flow logowania, MFA
