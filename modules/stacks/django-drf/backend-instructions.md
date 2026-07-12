# Backend instructions — Django + DRF

## Zakres

Te instrukcje dotyczą zmian w `backend/**`.

## Kontekst technologiczny

Backend to Django + Django REST Framework. Typowa struktura monorepo:

- `backend/src/core/` — settings, urls, celery, envs, storage
- `backend/src/apps/` — aplikacje domenowe
- `backend/src/common/` — współdzielone elementy i abstrakcje
- `backend/src/core/integrations/` — adaptery providerów (storage, payments, mail, allauth, notifications)

Szczegóły layoutu: `stack:django-drf:structure`.

## Moduły MCP — przeczytaj przed zmianą

| Temat | Moduł |
|-------|-------|
| Standard kodu (DRF-first) | `stack:django-drf:backend-standard` |
| Capability vs domena | `pattern:capability-provider` |
| Providers, settings, webhooki | `pattern:providers-and-settings` |
| Kontrakt API | `arch:api-contract` |
| CI backendu | `arch:ci-cd` |

## Capability + provider (obowiązkowe)

Przed integracją zewnętrzną:

- App domenowa **nie importuje** `stripe`, `boto3` ani modeli obcych app — woła capability.
- Konfiguracja integracji **tylko** w `core/settings/` + `.env` (bez hardcode bucketów/providerów).
- Adapter vendora: `core/integrations/<capability>/providers/`; webhooki: `.../webhooks/`.
- **Capability service** (`apps/payments/services/`, `apps/files/services/`) ≠ zabroniony domenowy service-CRUD.
- `apps/files`, `apps/payments`, `apps/notifications` — capability z własnymi URL-ami.
- Ciężkie operacje → Celery; taski idempotentne.

## Zasady obowiązkowe

- ZAWSZE odpowiadaj po polsku.
- ZAWSZE pisz docstringi po polsku.
- Najpierw wskaż pliki związane z problemem.
- Nie zakładaj dodatkowych warstw, jeśli repo ich nie potwierdza.
- Nie rozlewaj logiki biznesowej po wielu warstwach bez wyraźnej potrzeby.

## DRF-first (skrót)

Pełna specyfikacja: `stack:django-drf:backend-standard`.

- Domyślny CRUD = `Model` → `Serializer` → `ViewSet`.
- Serializer = źródło prawdy o polach API; walidacja i zapis REST w serializerze.
- ViewSet cienki — HTTP, permissions, wstrzyknięcie FK.
- Service tylko dla: `core/integrations/`, Celery, management commands.
- Nie zakładaj folderów `services/`, `selectors/` w każdej appce — dodawaj na żądanie.
- Stałe globalne tylko w `core/settings/**` albo `.env`.

Istniejący kod może być sprzeczny ze standardem — przy zmianach stosuj moduł MCP, nie „jak jest w repo”.

## Architektura i odpowiedzialności

- Domyślna struktura appki: `models/`, `serializers/`, `views/`, `urls.py`; opcjonalnie `permissions/`, `filters/`, `tasks/`.
- Logika REST w **jednym** miejscu — serializer (+ ewentualnie krótka metoda modelu).
- User (hasło, email) → allauth; Profile/Address → API DRF jako osobne zasoby.
- Integracje zewnętrzne — `pattern:capability-provider` (nie koliduje z DRF-first dla CRUD).

## ORM, API, testy

- Oceń ryzyko N+1; rozważ `select_related` / `prefetch_related` gdy uzasadnione.
- Zmiana endpointu → oceń wpływ na `schema.yaml`, frontend i Orval.
- Testy: pytest + factory_boy; mockuj integracje zewnętrzne, nie capability wewnętrzne.

## Overlay projektu

Taski, Docker, porty i ścieżki specyficzne dla repo — w `.ai/project.md` (overlay profilu).
