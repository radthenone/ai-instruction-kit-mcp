# Docker — struktura i podział env

## Struktura folderu

```text
docker/
├── django/
│   └── Dockerfile
├── postgres/
│   └── Dockerfile          # jeśli custom (extensions, init scripts)
├── .envs/
│   ├── .django.env.example
│   ├── .postgres.env.example
│   └── .redis.env.example
docker-compose.dev.yml
docker-compose.test.yml
docker-compose.prod.yml
.env.example                # zmienne wspólne / root-level
```

## Zasady

1. **Jeden Dockerfile per serwis** w `docker/<serwis>/Dockerfile` — nie jeden monolityczny Dockerfile na cały monorepo.
2. **`.envs/` per serwis**, nie jeden płaski `.env` na wszystko — każdy serwis czyta tylko swój plik.
3. **Trzy pliki compose**, nie jeden z profilami udającymi środowiska:
   - `docker-compose.dev.yml` — hot-reload, volumes montowane, debug ports.
   - `docker-compose.test.yml` — izolowane dane, używane przez CI i `task test:*`.
   - `docker-compose.prod.yml` — bez bind-mountów kodu, healthchecks, restart policy.
4. **`.env.example` obok każdego prawdziwego pliku env** — placeholdery, zero realnych sekretów.
5. Realne `.env` / `docker/.envs/*.env` (bez `.example`) — **nigdy nie trafiają do gita, nigdy nie trafiają na GitHub**.
   `.gitignore` musi je łapać explicit (`docker/.envs/*.env`, nie tylko `*.env` — żeby `.env.example` nie wpadł przez pomyłkę w szerszy pattern).
6. Komendy Docker wołane przez Taskfile (`docker:*`), nie bezpośrednio — patrz `arch:taskfile`.

## Antywzorce

- Jeden `docker-compose.yml` + `profiles:` symulujące dev/test/prod — utrudnia czytelność diffu env.
- Sekrety prod w `.env.example` "tymczasowo, wykasuję potem".
- Dockerfile builduje FE i BE w jednym stage bez multi-stage separacji.

## Powiązane

- `arch:taskfile` — `docker:*` taski jako jedyny interfejs
- `arch:configuration` — commituj `.env.example`, nigdy `.env`
- `arch:ci-cd` — `docker-compose.test.yml` używany w testach integracyjnych
