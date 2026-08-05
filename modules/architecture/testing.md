# Testing — standard monorepo (FE / BE)

## Cel

Jedna kanoniczna polityka testów dla projektów z instruction-kit.
Backend i frontend mają **osobne** runner’y, katalogi i joby CI — wspólny jest tylko
kontrakt API i definicja „co mockujemy”.

Szczegóły stacku:
- Backend (Django/DRF + pytest): `stack:django-drf:testing`
- Frontend (Expo/React + Jest/Vitest): `stack:expo-router:testing`

## Piramida

```text
        /\
       /E2E\          rzadko — krytyczne ścieżki (checkout, login)
      /------\
     / Integr.\       API + DB / compose; FE: MSW + Query
    /----------\
   /   Unit     \     większość — szybkie, deterministyczne
  /--------------\
```

| Warstwa | Backend | Frontend | Kiedy na PR |
|---------|---------|----------|-------------|
| Unit | serializery, modele, helpery, adaptery (mock vendor) | hooki, utils, komponenty czyste | zawsze |
| Integration | `APIClient` + DB; marker `integration` | feature + MSW / mock Orval | zawsze (BE); FE gdy są testy |
| E2E | Playwright/Cypress przeciw staging / compose | Detox / Maestro (mobile) opcjonalnie | merge / nightly / tag |

**Zasada:** wolisz wiele szybkich unitów + kilka integration niż gruby E2E na każdy PR.

## Layout katalogów (kanon)

```text
backend/src/tests/           # NIE w apps/*/tests/
  conftest.py
  factories/
  <app_or_domain>/
  integration/               # @pytest.mark.integration

frontend/
  src/**/__tests__/          # albo *.test.ts(x) obok pliku
  src/test/                  # setup, MSW handlers, render helpers
```

Nie trzymaj testów produkcyjnych w `apps/` ani w `src/features` bez konwencji `__tests__` /
`*.test.*` — agent i CI muszą mieć jedną ścieżkę odkrywania.

## Co mockować

| Mockuj | Nie mockuj |
|--------|------------|
| Vendor zewnętrzny (Stripe, S3, SMTP, Google OAuth) | Własne capability / app w tym samym procesie (np. `payments` woła `orders`) |
| Sieć HTTP poza procesem testu | ORM / DB w testach z `@pytest.mark.django_db` |
| Czas zegara (freezegun / fake timers) gdy flaky | Losowość bez seeda — seeduj albo ustal wartości |

Integracje vendorów: mock w `core/integrations/` (lub odpowiedniku), nie w ViewSecie /
komponencie UI.

## Markery i selekcja (pytest)

Rejestruj w `pytest.ini` / `pyproject.toml`:

| Marker | Znaczenie | CI |
|--------|-----------|-----|
| (brak) / unit | szybkie, bez Docker poza Postgres testowym | każdy PR |
| `integration` | compose / prawdziwy broker / slow | PR gdy infrastruktura gotowa; inaczej nightly |
| `e2e` | przeglądarka / urządzenie | nie blokuj każdego PR |

Przykład uruchomienia:

```bash
# PR — bez wolnych
pytest -m "not integration and not e2e"

# pełny zestaw lokalnie / nightly
pytest
```

Frontend: analogicznie tagi / projekty Jest (`unit` vs `integration`) albo osobne skrypty
`test` / `test:integration`.

## Izolacja i determinizm

1. **Jeden test = jeden scenariusz** — nazwa opisuje zachowanie (`test_checkout_rejects_empty_cart`).
2. **Brak zależności między testami** — kolejność uruchomienia nie ma znaczenia.
3. **Fabryki zamiast fixture dumpów SQL** — `factory_boy` (BE), factory/helpers (FE).
4. **Assert na zachowanie**, nie na implementację (nie snapshotuj całego drzewa HTML bez powodu).
5. **Flaky = bug** — napraw seed/czas/race albo przenieś do integration z retry polityką CI.

## Kontrakt API a testy

- Zmiana serializer/viewset → regeneruj OpenAPI + Orval (`arch:api-contract`).
- Testy FE nie hardcodują kształtów odpowiedzi — typy z wygenerowanego klienta.
- Job `api-contract` w CI: `git diff --exit-code` na wygenerowanym kliencie.

## Taskfile / CI

Źródło komend: `taskfiles/test.yml` (lub równoważne). CI wywołuje **taski**, nie ad-hoc
`pytest`/`jest` ze ścieżkami lokalnymi developera.

Minimalny gate PR: lint + types + unit (BE); lint + types (+ unit FE gdy istnieją).
Szczegóły jobów: `arch:ci-cd`.

## Antywzorce

- Testy tylko „czy status 200” bez asercji body / efektu ubocznego.
- Współdzielony mutable state między testami (moduły globalne, cache bez czyszczenia).
- Testowanie prywatnych helperów zamiast publicznego API warstwy.
- E2E jako jedyna siatka bezpieczeństwa (wolne, drogie, nietrwałe).
- Duplikowanie logiki asercji — wspólne helpery w `tests/` / `src/test/`.

## Definition of Done (zmiana z logiką)

- [ ] Unit pokrywa happy path + 1–2 edge / error
- [ ] Auth / permissions: test „obcy użytkownik nie widzi obiektu”
- [ ] Zewnętrzna integracja zmockowana
- [ ] Marker `integration` tylko gdy naprawdę potrzeba I/O poza procesem
- [ ] Task lokalny przechodzi; CI green na tym samym tasku

## Powiązane

- `stack:django-drf:testing` — pytest-django, factories, APIClient
- `stack:expo-router:testing` — Jest/Vitest, Testing Library, MSW
- `arch:ci-cd` — joby i macierz platform
- `arch:api-contract` — drift schema / Orval
- `core:code-review` — review przed pushem
