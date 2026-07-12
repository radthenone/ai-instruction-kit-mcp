# Capability — Files / Storage

## Zakres

Upload, przechowywanie i serwowanie plików (obrazy produktów, załączniki, PDF).

## Docelowy stan (capability app)

```text
apps/files/                    # capability app — własne URL-e
core/integrations/storage/     # adapter S3/MinIO/local
  providers/
  registry.py                  # get_storage_for_scope(scope)
```

- Model `StoredFile` w DB = **źródło prawdy** o pliku.
- Storage (MinIO/S3) = nośnik bajtów.
- Scope → bucket mapowany w `settings`, nie hardcode.

## Stan w olivin-app (przed migracją)

- **Brak** `apps/files/` — storage w `core/storage/storages.py`.
- MinIO (dev) / S3 (`USE_AWS=true`, prod) — buckety: static, media, profiles, products, private-media.
- `Product.image` = **`ImageField`** — obecna deviacja; docelowo `file_id` → `StoredFile`.
- Przy pracy nad olivin: nie zakładaj REST `/api/files/` dopóki capability nie istnieje — używaj istniejącego storage backendu.

## API (docelowy przykład)

| Metoda | URL | Opis |
|--------|-----|------|
| POST | `/api/files/` | upload (multipart) |
| GET | `/api/files/{id}/` | metadane + URL |
| DELETE | `/api/files/{id}/` | soft delete + cleanup task |

## Domain shop — jak używać

- `Product.image_file_id` → FK/UUID do `StoredFile`, **nie** `ImageField` na modelu produktu.
- Upload w adminie/API przez capability; domena trzyma tylko referencję.

## Frontend

```text
src/features/files/     # opcjonalny UI uploadu
src/core/integrations/  # helper presigned URL jeśli używany
```

Upload przez API backendu, nie bezpośrednio do MinIO z klienta (chyba że presigned z backendu).

## Celery

- Miniatury, konwersja WebP
- Cleanup osieroconych plików (`status=pending`)

## Powiązane

- `infra:storage:s3` — MinIO (dev), AWS (prod)
- `pattern:providers-and-settings`
