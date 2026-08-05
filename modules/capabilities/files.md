# Capability — Files

## Zakres

Upload, przechowywanie i serwowanie plików (obrazy produktów, załączniki, PDF).
Osobna capability app — **nie** część domeny shop; kategoria `shop` zawsze ją włącza,
bo katalog i zamówienia potrzebują referencji do plików.

## Layout (docelowy)

```text
apps/files/                    # capability app — własne URL-e REST
core/integrations/storage/     # adapter S3/MinIO/local (import boto3 TYLKO tutaj)
  providers/
  registry.py                  # get_storage_for_scope(scope)
```

- Model `StoredFile` w DB = **źródło prawdy** o pliku.
- Storage (MinIO/S3) = nośnik bajtów.
- Scope → bucket mapowany w `settings`, nie hardcode.
- Adapter w `core/integrations/storage/` (lub tymczasowo `core/storage/` przy migracji) —
  domena i `apps/files` wołają registry, nie SDK.

## API

| Metoda | URL | Opis |
|--------|-----|------|
| POST | `/api/files/` | upload (multipart) |
| GET | `/api/files/{id}/` | metadane + URL |
| DELETE | `/api/files/{id}/` | soft delete + cleanup task |

## Relacja z domeną (np. shop)

- Modele domenowe trzymają `file_id` / FK do `StoredFile` — **nie** `ImageField` z uploadem inline.
- Upload w adminie/API przez capability; domena tylko referencję.
- Bez włączonej capability `files` w profilu — nie zakładaj REST `/api/files/` (użyj overlay / fork).

## Frontend

```text
src/features/files/     # opcjonalny UI uploadu
src/core/integrations/  # helper presigned URL jeśli używany
```

Upload przez API backendu, nie bezpośrednio do MinIO z klienta (chyba że presigned z backendu).

## Celery

- Miniatury, konwersja WebP
- Cleanup osieroconych plików (`status=pending`)

## Testy

- Unit: uprawnienia uploadu, soft delete, scope → bucket.
- Integration: mock storage adapter + multipart upload.

## Powiązane

- `infra:storage:s3` — MinIO (dev), AWS (prod)
- `domain:shop` — zdjęcia produktów przez `file_id`
- `pattern:providers-and-settings`
