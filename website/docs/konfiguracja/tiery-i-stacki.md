# Tiery i stacki

**Tier** to warstwa produktu: `backend`, `web` albo `mobile`. Każdy Tier ma dokładnie jeden **stack** albo `none`. Brak klucza oznacza `none`.

## Dozwolone wartości

| Tier | Wartości | Co oznaczają |
|---|---|---|
| `backend` | `none`, `django`, `django-html`, `fastapi`, `flask` | `django`: Django + DRF. `django-html`: Django z szablonami HTML, tylko podpowiedź układu. `fastapi`, `flask`: API w Pythonie |
| `web` | `none`, `react`, `react@legacy`, `angular`, `angular@rxjs`, `expo` | `react`: React 19+. `react@legacy`: React 16–18. `angular`: standalone i signals. `angular@rxjs`: NgModule i RxJS. `expo`: Expo Router na web |
| `mobile` | `none`, `expo`, `react-native` | `expo`: iOS i Android w Expo. `react-native`: projekt RN bez Expo |

## Wariant w stacku

Goła nazwa oznacza **bieżące podejście**: `react` to React 19+. Starszy wariant nazywasz po `@`: `react@legacy`. Tak samo `angular@rxjs`. Zasada wynika z [ADR-0008](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0008-a-bare-stack-name-means-the-current-approach.md).

## Co zmienia wybór Tieru

- **Bundle**: `get_bundle backend` zawiera moduły Tieru backend. Bundle `frontend` składa się z Tierów web i mobile.
- **Agenci**: agenci backendu (`review-backend`, `teacher-backend`, `subagent-backend`) pojawiają się, gdy `backend ≠ none`. Agenci klienta (`review-frontend`, `teacher-frontend`, `subagent-frontend`, `review-ui`) pojawiają się, gdy `web` albo `mobile` ≠ `none`. Gdy Tier wraca do `none` i zrobisz `kit-ai reload`, ich pliki znikają.
- **BUGBOT.md**: sekcje `<!-- tier:backend -->` i `<!-- tier:client -->` trafiają tylko do wybranych Tierów.
- **Układ katalogów**: podpowiedź drzewka zależy od pary web i mobile. Gdy nie ma pasującej, używane są domyślne ścieżki: `backend/`, `frontend/web/`, `frontend/mobile/`. Dla Expo unified: `frontend/`.

!!! warning "Dwa toolchainy RN"
    Kombinacja `web: expo` i `mobile: react-native` daje ostrzeżenie. To dwa toolchainy React Native w jednym repo. Rozważ `mobile: expo` albo `web: react`.

## Moduły stacku

Stack rozwija się do modułów. Przykład dla `backend: django`: przegląd Django + DRF, struktura katalogów, standard kodu DRF-first, instrukcje agenta i testy pytest. Dla `web: react` (wariant bieżący): przegląd, React 19+ (actions, `use()`, kompilator) i wspólne reguły UI. Pełna lista modułów jest w [Moduły i bundle](moduly-i-bundle.md).

## Jak kit wykrywa Tiery

Nie musisz ich wpisywać ręcznie. `/kit-ai:kit-project-begin` sprawdza pliki repo: `manage.py` albo `django` w `pyproject.toml` daje `backend: django`, `angular.json` daje `web: angular`, `app.json` z sekcjami `ios` i `android` daje `mobile: expo`. Agent proponuje wartość, a ty ją akceptujesz.
