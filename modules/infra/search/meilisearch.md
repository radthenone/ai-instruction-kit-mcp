# Search — Meilisearch

Wariant `decisions.search: meilisearch`. Wybieraj świadomie, gdy Postgres `tsvector`
(`infra:search:postgres`) realnie nie wystarcza — duży katalog, faceted search z agregacjami
liczonymi na żywo, tolerancja literówek out-of-the-box.

## Struktura

- Osobny serwis w `docker-compose.dev/test/prod.yml` (`arch:docker-structure`) — kontener
  Meilisearch, wolumen na indeks.
- Indeksowanie: sygnał `post_save`/`post_delete` na modelu produktu → task Celery →
  `index.add_documents()`/`index.delete_document()`. Nie synchronicznie w request/response.
- Reindeks pełny jako osobny task/task management command — potrzebny po zmianie schematu
  atrybutów filtrowalnych.

## Zasady

1. Postgres pozostaje źródłem prawdy (system of record) — Meilisearch to tylko indeks do
   odczytu, zawsze odtwarzalny z DB. Nigdy nie pisz do Meilisearch jako jedynego miejsca danych.
2. Filtrowalne/sortowalne atrybuty (`filterableAttributes`, `sortableAttributes`) deklaruj
   explicit w konfiguracji indeksu — nie każde pole domyślnie.
3. Klucz API search-only (read-only) dla frontendu, klucz admin tylko po stronie backendu.

## Powiązane

- `infra:search:postgres` — prostszy default, sprawdź zanim tu przejdziesz
- `arch:docker-structure` — serwis w compose
