# VPS — lekki tryb agenta

Ten moduł dokleja się automatycznie do każdego bundle'a, gdy host wygląda na
słaby VPS (heurystyka zasobów + wirtualizacja, bez nazw hostów) albo gdy
`KIT_HOST_PROFILE=vps`. Na mocnej maszynie dewelopera i w CI moduł się nie pojawia.

## Wykrywanie

- Nadpisanie: `KIT_HOST_PROFILE=vps|local` (alias `GUIDES_HOST_PROFILE`). Puste /
  nierozpoznane = heurystyka.
- Heurystyka VPS: Linux, brak CI, brak WSL, małe zasoby (CPU ≤ 2, RAM ≤ 8 GB,
  brak swapu) i sygnał serwerowy (wirtualizacja przez `systemd-detect-virt`
  albo brak desktopu: brak `DISPLAY` / `WAYLAND_DISPLAY` / `XDG_CURRENT_DESKTOP`).
- Bez hardkodowanych hostname'ów. CI (`CI=true`, GitHub Actions, GitLab CI, …)
  zawsze dostaje profil `local` — pełna weryfikacja należy do CI.

## Zakazane na VPS (kategorie, bez względu na stack)

- Kontenery: `docker compose up/build/run`, `docker build`, `docker run` z buildem.
- Dev serwery: `next dev`, `runserver`, `vite dev`, `ng serve` i odpowiedniki.
- Buildy produkcyjne frontu / backendu oraz testy e2e.
- Operacje na demonie i cudzych kontenerach: restart `dockerd`, `docker system prune`,
  stop / restart kontenerów spoza bieżącego projektu.

## Dozwolone na VPS

- Lint, typecheck, format-check.
- Testy unit / in-memory bez zewnętrznych usług (bez bazy, brokera, S3, sieci).
- Czytanie logów i plików, `git`, edycja kodu.

## Pełna weryfikacja w CI

Ciężkie rzeczy zostaw dla CI: push → checki PR (kontenery testowe, migracje,
integracje, e2e, build produkcyjny). Lokalnie na VPS nie próbuj odtwarzać CI.

## Overlay projektu (`.ai/project.md`)

Kit nie wie, które taski Twojego repo są lekkie. Dopisz to w overlay, np.:

```markdown
## VPS — podział tasków

- Lekkie (wolno na VPS): `task lint`, `task typecheck`, `task test:unit`.
- Ciężkie (tylko CI): `task test:e2e`, `task build`, `docker compose up`.
```

Podział edytujesz przez `/kit-project-edit` (jedna zmiana na wywołanie),
np. `/kit-project-edit "w VPS lekkie to…"`. Overlay ma pierwszeństwo przed bundlem.

## Bez hooka blokującego

Świadomie brak twardego hooka — reguła jest tekstowa. Hook mógłby zablokować
celowe operacje (deploy, ręczny restart, automatyzację), a tu chodzi o domyślne
zachowanie agenta, nie o zakaz systemowy.

## Powiązane

- `arch:ci-cd` — gdzie ląduje pełna weryfikacja
- `arch:docker-structure` — czego nie ruszać na VPS
- `arch:testing` — co znaczy unit vs integracja vs e2e
