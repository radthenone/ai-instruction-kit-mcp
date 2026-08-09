# Taskfile — jedyny punkt wejścia komend

## Zasada

`Taskfile.yml` w rootcie monorepo to **jedyne** źródło prawdy komend dev/test/CI/deploy.
Nie surowy `docker compose ...`, nie `cd backend && uv run ...` z pamięci —
zarówno człowiek jak i agent uruchamiają `task <namespace>:<nazwa>`.

`task --list` musi zwracać kompletną, czytelną listę — to jest kontrakt discoverability,
nie opcjonalny dodatek.

## Namespacing

Grupuj po warstwie/domenie, nie płasko:

```text
backend:*     # backend:run, backend:shell, backend:migrate
frontend:*    # frontend:run, frontend:build
docker:*      # docker:up, docker:down, docker:logs
db:*          # db:migrate, db:seed, db:reset
lints:*       # lints:backend:ruff:check, lints:frontend:lint:check
test:*        # test:backend, test:frontend
ovral:*       # ovral:generate (jeśli codegen: orval)
```

Task złożony (np. pełny setup) woła inne taski, nie duplikuje kroków.

## Wymagania

1. Każdy task ma `desc:` — to jest treść którą pokazuje `task --list`.
2. Taski Docker/DB nigdy nie hardkodują sekretów — czytają z `.env` / `docker/.envs/*`.
3. CI woła te same taski co dev (`arch:ci-cd`: "Taskfile jest źródłem prawdy komend —
   CI wywołuje taski, nie kopiuje składni ad hoc").
4. Zmiana nazwy/zachowania taska = zmiana w jednym miejscu (Taskfile), nie w docs + CI + README osobno.

## Antywzorce

- Komenda działa tylko "bo ktoś ją zna z historii shella" — brak taska = brak komendy.
- Różne nazwy tej samej operacji w Taskfile vs Docker vs docs (`arch:configuration`).
- Task bez `desc:` — niewidoczny w `task --list`, więc nieodkrywalny.

## Powiązane

- `arch:ci-cd` — CI woła taski, nie ad-hoc komendy
- `arch:docker-structure` — taski `docker:*` operują na strukturze `docker/`
- Overlay projektu (`.ai/project.md`) — konkretne nazwy tasków tego repo
