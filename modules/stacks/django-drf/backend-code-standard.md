# Standard tworzenia kodu backendu (Django/DRF)

## Cel dokumentu

Ten dokument jest **jednym wspólnym standardem** generowania kodu backendu dla
wszystkich agentów AI pracujących w projektach opartych o ten kit: Cursor, Codex,
GitHub Copilot, Claude, Antigravity i inne klienty.

Cel jest praktyczny: kod backendu ma być spójny, czytelny, bezpieczny i zgodny
z idiomami **Django i Django REST Framework**. Agenci nie mają wymyślać
równoległych warstw (service, selector, utils) tam, gdzie DRF i Django już dają
gotowy mechanizm.

Dokument jest neutralny względem narzędzia. Pozostałe pliki agentowe
(`AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/*`,
`.cursor/rules/*`) odsyłają tutaj zamiast duplikować te zasady.

**Ważne:** istniejący kod w repo może nie odzwierciedlać jeszcze tego standardu.
Przy nowych zmianach i refaktorach **stosuj ten dokument**, a nie „jak jest w
pliku X", jeśli plik jest sprzeczny z zasadami poniżej.

## Zasada nadrzędna: DRF-first

Domyślny przepływ mutacji przez API REST:

```text
Model (invariants) → Serializer (walidacja + create/update) → ViewSet (HTTP + perform_*)
```

Zasady:

1. Najpierw użyj natywnego mechanizmu Django/DRF (`ModelSerializer.create`,
   `perform_create`, `validate`, nested serializer, `@action`).
2. Nie twórz dodatkowych klas, rejestrów, „spec" ani folderów `services/`,
   `selectors/`, `utils.py`, jeśli nie umiesz w jednym zdaniu powiedzieć, czego
   w Django/DRF brakuje.
3. **Jeśli jedyny caller to ViewSet → nie ma domenowego service.**
4. Integracje zewnętrzne (mail, storage, płatności) nadal idą przez
   `core/integrations/` — to osobna reguła (`capability-provider-architecture.md`,
   `providers-and-settings.md`).

### Przykład rozumowania (wzorcowy)

> Endpoint `POST/PATCH` na zasób REST → `Serializer` (`validate`, `create`,
> `update`) + `ViewSet` (`get_queryset`, `perform_create`). Bez service.
>
> Signup allauth (brak ViewSetu) → dedykowany serializer (np.
> `ProfileSignupSerializer`) wołany z adaptera w `core/integrations/`.
>
> Celery / management command → minimalne wejście (`id`) + ten sam serializer
> do walidacji, jeśli potrzeba. Bez duplikacji pól.
>
> Stripe / S3 / SMTP → `core/integrations/<capability>/`, nie logika w serializerze
> domenowym.

## Domyślny przepływ REST (CRUD)

Dla typowego zasobu (np. `Profile`, `Address`):

| Operacja | Gdzie |
| -------- | ----- |
| Walidacja pól | `Serializer.validate_*`, `validate` |
| Zapis / aktualizacja | `Serializer.create()`, `update()`; `transaction.atomic` tutaj |
| Wstrzyknięcie FK (`user`, `profile`) | `ViewSet.perform_create()` / `perform_update()` → `serializer.save(...)` |
| Filtrowanie po właścicielu | `ViewSet.get_queryset()` |
| Custom action (`set-default`, `change-role`) | `@action` w ViewSecie; ciało w serializerze akcji lub metodzie modelu |
| Kształt odpowiedzi | `Serializer.to_representation` |

ViewSet ma zostać **cienki** (kilka–kilkanaście linii na akcję). Logika zapisu
nie siedzi w view — siedzi w serializerze (lub krótkiej metodzie modelu).

## Warstwy i odpowiedzialności

Podział poniżej opisuje **konwencję projektu**. Warstwy opcjonalne (`selectors`,
`filters`, `apps/<domena>/services/`) dodajesz **na żądanie**, nie domyślnie przy
każdym modelu.

| Warstwa | Odpowiedzialność |
| ------- | ---------------- |
| `models` | Stan, relacje, `clean()`, constraints (`UniqueConstraint`, `CheckConstraint`), `TextChoices` w `choices.py`, proste `@property`, **manager tylko dla fabryk ORM** (`create_user`) — nie CRUD API |
| `serializers` | **Serce API:** walidacja, `create`/`update`, nested writes, kształt payloadu — jedyne źródło prawdy o polach |
| `views/viewsets` | HTTP: permissions, `get_queryset()`, `perform_*` (kontekst FK), `@action` (orkiestracja) |
| `permissions` | Reguły dostępu (DRF `BasePermission`) — „kto może", nie „co wolno biznesowo" |
| `filters` | *(opcjonalnie)* query params → QuerySet (`django-filter`) |
| `selectors` | *(opcjonalnie)* złożone QuerySety współdzielone między wieloma viewsetami |
| `core/integrations/` | Adaptery zewnętrznych providerów (mail, storage, allauth, płatności) |
| `tasks` | Celery — argumenty = ID; enqueue po `transaction.on_commit` |

**Nie zakładaj** folderu `apps/<domena>/services/` przy każdej appce. Pojawia się
tylko gdy realnie wołasz coś spoza DRF (integracja, Celery, hook frameworka).

### Gdzie umieścić kod — decyzyjnik

```text
Trwały stan / tabela?                         → model
Kształt i walidacja payloadu API?             → serializer
Zapis przez REST (create/update/nested)?      → serializer.create/update
Endpoint HTTP?                                → viewset
Reguła „kto może" (auth)?                     → permission + get_queryset()
Query param na liście?                        → filter (gdy potrzeba)
Złożony współdzielony QuerySet?               → selector (gdy potrzeba)
Hook allauth / brak requestu DRF?             → dedykowany serializer + adapter
Integracja zewnętrzna (vendor)?               → core/integrations/
Praca w tle?                                  → task
```

## Model

W modelu zostaw tylko to, co naprawdę należy do modelu:

- relacje, `Meta`, constraints na poziomie bazy,
- `clean()` dla reguł obowiązujących **zawsze** (admin, shell, import, API),
- proste `@property` czytające z własnych pól,
- manager wyłącznie jako fabryka ORM (np. `CustomUserManager.create_user`).

Krótkie metody instancji z `transaction.atomic` są dopuszczalne (np.
`Address.set_as_default()`), o ile nie wołają maila, Celery ani vendora.

Nie umieszczaj w modelu: parsowania requestu, logiki HTTP, integracji
zewnętrznych, całej walidacji API (to serializer).

## Serializer — serce API

Tu trzymasz **większość logiki REST** (~80% pracy przy endpoincie):

- `validate_<field>`, `validate` — walidacja i reguły krzyżowe,
- `create()`, `update()` — zapis, nested writes, `transaction.atomic`,
- `to_internal_value` — gdy wejście wymaga normalizacji (np. signup allauth),
- `to_representation` / `SerializerMethodField` — kształt odpowiedzi,
- osobne serializery read vs write, gdy kształty się różnią,
- `read_only_fields` dla pól z kontekstu (`user`, `role`, `email`).

Zasady:

- Serializer jest **jedynym źródłem prawdy o polach**. Nie duplikuj listy pól w
  rejestrach ani „spec".
- Reguły biznesowe API (np. „musi mieć 18 lat") → `validate` w serializerze;
  te same reguły trwałe dodatkowo w `Model.clean()` jeśli muszą obowiązywać poza API.
- Zagnieżdżony zapis (profil + adresy w jednym POST) → nested serializer +
  `create()` w jednym miejscu, nie rozproszenie po view + service.
- Nie wołaj w serializerze domenowym: Stripe, boto3, SMTP — to `core/integrations/`.

### Serializery specjalne (inny entry point niż ViewSet)

Gdy flow **nie przechodzi** przez ViewSet (signup allauth, import CSV), użyj
**osobnego serializera** dziedziczącego po wspólnym (wspólna walidacja pól):

```python
class ProfileSignupSerializer(ProfileSerializer):
    """Profil przy rejestracji allauth — nie używać z ProfileViewSet."""

    def to_internal_value(self, data):
        data = normalize_signup_payload(data)  # np. firstName → first_name
        return super().to_internal_value(data)

    def create(self, validated_data):
        user = self.context["user"]
        profile, _ = Profile.objects.update_or_create(
            user=user,
            defaults=validated_data,
        )
        return profile
```

Adapter allauth woła wyłącznie:

```python
serializer = ProfileSignupSerializer(
    data=get_request_payload(request),
    context={"user": saved_user},
)
serializer.is_valid(raise_exception=True)
serializer.save()
```

Nie twórz `ProfileService`, który robi `get_or_create` + `partial update` obok
serializera — to duplikacja ścieżek zapisu.

## ViewSet — cienka orkiestracja HTTP

Szablon na każdy zasób:

```text
permission_classes
serializer_class (+ get_serializer_class gdy read/write różne)
get_queryset()              # filtr po właścicielu — ZAWSZE tutaj dla zasobów per-user
perform_create/update()     # tylko wstrzyknięcie FK: user, profile
@action                     # niestandardowe operacje; ciało w serializerze lub modelu
```

- `IsAuthenticated` + filtrowanie querysetu po właścicielu = domyślny wzorzec
  dla zasobów użytkownika (`Profile`, `Address`).
- Custom action: view zwraca `Response(serializer.data)`; mutacja w serializerze
  akcji lub `obj.set_as_default()` na modelu.
- Nie parsuj ręcznie `request.query_params` — użyj `django-filter` / `OrderingFilter`.

## User vs Profile vs Address

- **User** (hasło, email, weryfikacja) → django-allauth (`/accounts/`, `/_allauth/`),
  bez własnego CRUD w domenie.
- **Profile** → API DRF (`ProfileSerializer` + `ProfileViewSet`).
- **Address** → osobny zasób REST (`AddressSerializer` + `AddressViewSet`), nie
  nested w profilu, dopóki frontend nie wymaga jednego POST-a.

## Kiedy service jest dozwolony

Service (w `core/integrations/` lub rzadko w `apps/<capability>/`) jest
**obowiązkowy** dla:

| Przypadek | Przykład |
| --------- | -------- |
| Integracja zewnętrzna | `MailService`, storage, Stripe |
| Celery / management command | taski mailowe, generowanie tłumaczeń |
| Fasada capability app | `apps/files`, `apps/payments` |

Service jest **zabroniony jako domyślny wrapper REST**, gdy:

- istnieje ViewSet + Serializer dla zasobu,
- service robi wyłącznie `Serializer(...).is_valid(); save()`,
- jedyny caller to ViewSet.

Hook allauth **nie wymaga** klasy `*Service` — wystarczy dedykowany serializer
wołany z adaptera (patrz wyżej).

**Uwaga terminologiczna:** „Service zabroniony przy ViewSet” dotyczy **domenowego**
wrappera na serializer (`ProfileService.save()`). **Capability service** w
`apps/payments/services/`, `apps/files/services/` lub `core/integrations/mail/`
jest **wymagany** — orkiestruje adapter + modele capability. Konfiguracja adapterów:
`core/settings/` + registry w `core/integrations/` (`pattern:providers-and-settings`).

Atomowość (`transaction.atomic`): w `serializer.create()`/`update()` dla REST;
w adapterze/tasku wokół wywołania serializera, jeśli obejmuje wiele kroków.

## Selectors i filters — na żądanie

- Prosty CRUD: `get_queryset()` w viewsecie wystarczy (`filter(user=request.user)`).
- `selectors/` dopiero gdy QuerySet rośnie (prefetch, adnotacje, współdzielony
  między ≥3 viewsetami).
- `django-filter` na listach z query params — tak; ręczne parsowanie w view — nie.

## Kod oderwany od requestu (tasks, commands)

- Celery task i management command nie mają ViewSetu ani `request`.
- Przekazuj minimalne wejście (`id`, `model_label`).
- Walidację kształtu danych rób **tym samym serializerem** co API, zamiast
  drugiej definicji pól.
- Mapa `model → serializer` jest dopuszczalna jako konsekwencja braku requestu,
  nie jako równoległy system pól.

## Bezpieczeństwo i autoryzacja

- Globalny default w `core/settings/components/auth.py` to
  `DEFAULT_PERMISSION_CLASSES = (IsAuthenticated,)`. Endpoint publiczny wymaga
  jawnego `AllowAny`.
- Uwierzytelnianie: allauth headless `XSessionTokenAuthentication` (mobile) oraz
  `SessionAuthentication` (web). Nie zakładaj JWT.
- Reguły „kto może" → `permissions` (DRF). Nie mieszaj z walidacją biznesową w
  serializerze (tam: „co wolno zrobić z danymi", np. wiek 18+).
- Dla zasobów per-użytkownik filtruj QuerySet w `get_queryset()`, nie licz na
  frontend.
- Throttling na endpointach wrażliwych (logowanie, reset hasła, płatności).
- Nie ujawniaj w odpowiedzi: hashy haseł, tokenów, stacktrace. Sekrety tylko z
  `settings`/`.env`.

## Konwencje API i kontrakt

- API REST, właściwe status code (`200/201/204/400/401/403/404/409`). Walidacja
  DRF → `400`.
- Wersjonowanie URL (`URLPathVersioning`, domyślnie `v1`).
- Styk DRF z frontendem: **camelCase** (`djangorestframework-camel-case`). W
  Pythonie `snake_case`. Endpointy allauth (`/_allauth/`) **nie** są camelizowane
  — tam normalizacja w `to_internal_value` signup serializera.
- Paginacja globalna (`PageNumberPagination`). Throttling globalny + scoped na
  endpointach wrażliwych.
- Filtrowanie: `django-filter`, `OrderingFilter`.
- Po zmianie serializera/viewsetu/URL: `backend/src/schema.yaml` →
  `task ovral:generate` → `task lints:frontend:typecheck`.

## Obsługa błędów i format odpowiedzi

Szczegóły: **`arch:api-errors`**.

W projekcie: `drf-standardized-errors` jako `EXCEPTION_HANDLER`. Rzucaj wyjątki
(`ValidationError`, `PermissionDenied`), nie ręczny `Response(status=4xx)`.

## Schema / OpenAPI (drf-spectacular)

- Schemat dokładny — z niego Orval generuje frontend.
- `@extend_schema` gdy auto-inspekcja nie wystarcza.
- Po zmianie kontraktu: regeneracja schematu i klienta (`arch:api-contract`).

## Tłumaczenia treści (JSONField)

Szczegóły: **`arch:i18n`**. Helper odczytu + fallback; pola definiuje serializer wpisu.

## Baza danych, ORM i współbieżność

Szczegóły: **`arch:migrations`** (N+1, expand/contract, `select_for_update`).

- N+1: `select_related` / `prefetch_related` w `get_queryset()` lub selectorze.
- Constraints na poziomie bazy.
- Współbieżność (stock, płatności): `select_for_update` w `transaction.atomic`.

## Migracje

Szczegóły: **`arch:migrations`**. Nie edytuj zastosowanych; data-migration z
`reverse_code`; w migracjach `apps.get_model`.

## Celery i zadania asynchroniczne

- Argumenty serializowalne: `id`, nie instancje modeli.
- `transaction.on_commit` przed enqueue.
- Taski idempotentne; `autoretry_for` świadomie (`arch:observability` — logi retry).

## Pieniądze i wartości liczbowe

- `Decimal` / `PriceField`, nigdy `float`.
- Obliczenia cen w jednym miejscu (serializer wyceny lub moduł pricing).

## Pliki i media

- Upload przez `core/storage` / capability `files`, nie `ImageField` na modelu
  domenowym zamiast `fileId` (`arch:security` — walidacja uploadu).

## Audyt i historia

- `HistoricalRecords` (`django-simple-history`) tam, gdzie biznes tego wymaga.

## Sygnały — używaj oszczędnie

- Rdzeń flow (np. profil przy signupie) → jawny kod w adapterze allauth + serializer,
  **nie** `post_save` na User.
- Sygnały tylko na luźne efekty uboczne (enqueue task po `on_commit`).

## Internacjonalizacja komunikatów

Szczegóły: **`arch:i18n`**. Walidacja → `gettext_lazy`; treść dynamiczna → translations.

## Logowanie i observability

Szczegóły: **`arch:observability`**. Logger, nie `print`. Bez PII/secrets.

## Stałe i konfiguracja

Szczegóły: **`arch:configuration`**. Tylko `core/settings/**` i `.env`.
Bezpieczeństwo sekretów: **`arch:security`**.

## Struktura folderów (minimalna)

```text
apps/<domena>/
  models/
  serializers/       # w tym serializery signup/import jeśli potrzeba
  views/
  permissions/       # gdy rośnie
  filters/           # gdy lista ma filtry
  tasks/             # gdy jest Celery
  urls.py
```

**Nie twórz** z góry: `services/`, `selectors/`, `utils.py` w każdej appce.
`utils.py` nie jest domyślnym miejscem na logikę — preferuj serializer lub
nazwany moduł (`helpers/` tylko dla czystej transformacji danych bez HTTP).

## Type hints i docstringi

- Type hints wymagane (Python z `pyproject.toml`, obecnie `>=3.12`).
- Docstringi po polsku dla publicznych klas, serializerów, viewsetów, modeli.

## Testy

Szczegóły: **`stack:django-drf:testing`** oraz **`arch:testing`**.

Priorytet (DRF-first): serializery → viewsety/auth → permissions → integracje/Celery.
Stack: `pytest`, `pytest-django`, `factory-boy`; taski z `taskfiles/test.yml`.
Nie pisz osobnych testów dla cienkiego wrappera `service → serializer.save()`.

## Kontrola jakości

- `task lints:backend:ruff:check`, `task lints:backend:typecheck`.
- Po zmianie API: `task ovral:generate`, `task lints:frontend:typecheck`.

## Antywzorce — czego nie robić

- **Service-per-CRUD** — `UserService.update()` owijający serializer używany z ViewSetu.
- **get_or_create w service + partial update serializera** — zamiast jednego `create()`/
  `update_or_create` w serializerze.
- **Logika w trzech miejscach** — model + serializer + view + service naraz.
- **Gruby viewset** z mutacją wielu rekordów zamiast serializera/modelu.
- **Manager jako warstwa API** — manager tylko dla fabryk ORM.
- **`utils.py` jako szuflada** — bez nazwy domenowej i bez uzasadnienia.
- **Folder `services/` w każdej appce „na zapas".**
- Wymyślanie rejestru/spec gdy wystarczy serializer.
- Hardcode stałych zamiast settings/.env.
- Mieszanie permissions z walidacją biznesową.
- `post_save` zamiast jawnego flow w adapterze/serializerze.
- Równoległa architektura obok DRF (własny dispatch, własna walidacja).
- Ręczny camelCase na endpointach DRF (parser to robi).
- Ręczne parsowanie query params zamiast `django-filter`.
- `float` do pieniędzy.
- Przekazywanie instancji modelu do Celery.
- Enqueue przed `transaction.on_commit`.

## Źródła standardu (zewnętrzne)

- Dokumentacja **Django** i **Django REST Framework** — podstawowe źródło.
- OWASP REST / DRF Cheat Sheet — paginacja, throttling, jawne pola (`arch:security`).
- RFC 9457 + `drf-standardized-errors` — `arch:api-errors`.
- `capability-provider-architecture.md` — integracje zewnętrzne.
- `providers-and-settings.md` / `arch:configuration` — settings, registry.
- HackSoft Django Styleguide — **opcjonalna inspiracja** dla selectorów; **nie**
  domyślny service layer dla CRUD.
