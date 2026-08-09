# Capability — Auth

## Zakres

Uwierzytelnianie użytkownika: login, rejestracja, MFA, social login, sesja.

## Wybór wariantu backendu

Wariant wybierasz przez `decisions.auth` w profilu (`allauth` / `jwt` / `custom`,
domyślnie **`custom`**). Ładuje odpowiedni moduł:

| `decisions.auth` | Moduł | Kiedy |
|-------------------|-------|-------|
| `allauth` | `capability:auth:allauth` | django-allauth headless, web + mobile Expo, MFA/social wbudowane |
| `jwt` | `capability:auth:jwt` | własny `/api/auth/*`, prosty access+refresh, brak potrzeby MFA/social z pudełka |
| `custom` (default) | `capability:auth:custom` | inny/istniejący mechanizm — opisz kontrakt w `.ai/project.md` |

Nie mieszaj wariantów w tym samym API bez jasnego podziału (np. `pattern:microservices-auth`).

## Frontend (wspólne dla wszystkich wariantów)

```text
src/core/auth/        # session, platform (browser/app), storage native/web
src/features/auth/    # login, register, MFA, OAuth redirect
src/features/account/ # profil po zalogowaniu
```

## Testy

- Unit: adapterzy, uprawnienia CRUD profilu.
- Integration: pełny flow login → autoryzowany request → refresh/expiry.

## Powiązane

- `capability:auth:allauth`, `capability:auth:jwt`, `capability:auth:custom` — wariant backendu
- `pattern:microservices-auth` — gdy wiele serwisów
- `domain:shop` — zamówienia wymagają zalogowanego usera
- `stack:django-drf:structure`
- `arch:api-contract` — Orval per wariant (patrz moduł wariantu)
