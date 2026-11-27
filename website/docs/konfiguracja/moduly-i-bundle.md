# Moduły i bundle

**Instruction Module** to jeden plik Markdown z instrukcjami. Ma stabilne **Module ID** w formie `warstwa:kategoria:wariant`, np. `infra:queue:redis`. **Bundle** to nazwany zestaw modułów dla jednego rodzaju pracy. Rejestr modułów to **Manifest** (`manifest.yaml`).

## Bundle

| Bundle | Zastosowanie |
|---|---|
| `backend` | stack z Tieru backend, capabilities backendu |
| `frontend` | stacki z Tierów web i mobile, UI i UX |
| `architecture` | monorepo, kontrakt API, capability-provider |
| `infra` | Postgres, Redis, kolejki, S3, Celery |
| `devops` | CI/CD i infra |
| `payments` | Stripe, webhooki |
| `full` | wszystko, z infra |

Bundle składane są z tagów modułów i Tierów z Profilu. Pusty Profil daje sam core.

## Katalog modułów

- **core**: repo-first, workflow AI, język PL lub EN, wiedza zewnętrzna, kanon inżynierski, kanon pracy z agentami, code review, RTK, CodeGraph, typowanie Python i TypeScript.
- **architecture**: układ monorepo, kontrakt API (Orval, generyczny klient, GraphQL), rozdział frontend i backend, CI/CD, testy, security, błędy API, observability, konfiguracja, migracje, i18n, UI/UX Expo, platformy, Taskfile, Docker.
- **stacks**: Django + DRF, Django HTML, FastAPI, Flask, React (bieżący i legacy), Angular (bieżący i RxJS), React Native, Expo Router oraz warianty split (React + Expo, React + RN).
- **capabilities**: auth (allauth, JWT, custom), files, payments (Stripe w Expo).
- **patterns**: capability-provider, providers i settings, gateway Nginx, auth między mikroserwisami, webhooki.
- **infra**: PostgreSQL, Redis (cache i broker), RabbitMQ, S3, wyszukiwanie (Postgres, Meilisearch), Celery, lekki tryb VPS.

Listę z opisami zwraca MCP `list_modules`. Treść jednego modułu: `get_module(module_id)`.

## Tagi

Każdy moduł ma tagi, np. `core`, `architecture`, `backend`, `frontend`, `web`, `mobile`, `infra`, `devops`, `security`, `testing`. Bundle wybiera moduły po tagach i Tierach. Dlatego dodanie modułu z właściwym tagiem sam trafia do odpowiedniego Bundle.

Profil może też dołożyć moduły po ID przez klucz `include:`. Routing po tagach działa wtedy obok Tierów.

## Warianty i substytucje

- **Variant** dokłada się obok modułu ogólnego. Przykład: `capability:auth:jwt` obok `capability:auth`. Ogólny zostaje.
- **Substitution** zastępuje moduł ogólny. Przykład: `arch:api-contract:graphql` zamiast `arch:api-contract`.

Wariant dodaje, substytucja podmienia. Zob. [Sloty i decyzje](sloty-i-decyzje.md).

## Jak czytać bundle

```text
list_bundles                 # nazwy bundli i ich zakres
get_bundle backend           # treść bundla dla bieżącego Profilu
get_module infra:queue:redis # pojedynczy moduł
```

Jeśli chcesz dodać moduł albo stack, zob. [Dodawanie modułu, stacku i agenta](../autorzy/dodawanie-modulu-i-agenta.md).
