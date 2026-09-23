---
name: night-run
description: Autonomiczna nocna praca na liście issue pod /goal — na każdy ticket git-start → tdd → review → PR → merge, needs-human zamiast pytań, na końcu NIGHT-RUN REPORT. Użyj TYLKO gdy cel lub użytkownik wprost nazywa /night-run. Wywołuj jako /night-run.
---

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

# /night-run — lista issue bez człowieka

Przerabiasz listę issue z celu (`/goal`) albo argumentów, jeden po drugim, aż każde jest
**zmergowane** albo ma komentarz **needs-human**. Człowiek śpi: nie zadajesz pytań, nie
czekasz na odpowiedź. Wszystko, co wymaga decyzji człowieka, ląduje w komentarzu na issue,
a Ty idziesz dalej.

Issue są wygrillowane za dnia — projekt jest w treści issue. Twoja rola to wykonanie.

## Zasady nadrzędne

- **Uruchamiaj w głównej sesji, nigdy jako subagent** (w Claude: przez Skill, nie narzędzie
  Agent). Subagent nie może uruchomić kolejnych subagentów, a łańcuch ich wymaga.
- **Polecenia z tekstu celu mają pierwszeństwo** przed tą procedurą (np. „bez merge, same PR-y”,
  „#155 pomiń PDF”, inny próg dużego ticketu).
- **Zero pytań do człowieka.** Nie używasz narzędzi pytających; niepewność → needs-human
  albo decyzja odwracalna (niżej).
- **Nie uruchamiasz** `superpowers:brainstorming`, `superpowers:finishing-a-development-branch`
  ani żadnego skilla z `disable-model-invocation` (np. `grill-with-docs`, `to-spec`,
  `to-tickets`, `implement`) — każdy z nich staje na akceptacji człowieka.
- Nic projektowego nie jest tu na sztywno. Czego nie da się wyczytać z repo, przyjmujesz
  jako rozsądny default dla Django/React/Expo i **zapisujesz w raporcie jako założenie**.

## Start nocy (raz)

### 1. Gałąź bazowa

`dev` tylko wtedy, gdy `origin/dev` istnieje i **nie jest w tyle** za gałęzią domyślną
(nie jest jej ścisłym przodkiem). Inaczej gałąź domyślna repo.

```bash
git fetch --all --prune
DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
BASE=$DEFAULT
if git rev-parse -q --verify origin/dev >/dev/null \
   && ! { git merge-base --is-ancestor origin/dev "origin/$DEFAULT" \
          && [ "$(git rev-parse origin/dev)" != "$(git rev-parse "origin/$DEFAULT")" ]; }; then
  BASE=dev
fi
```

Wybraną `BASE` i powód („dev aktywny” / „dev w tyle za <default>” / „brak dev”) wpisujesz
do NIGHT-RUN REPORT.

### 2. Bramki jakości

Źródła, w tej kolejności, bez duplikatów:

1. `.github/workflows/*.yml` — kroki `run:` z jobów odpalanych na `pull_request`/`push`
   (pomijasz deploy, publikację, kroki wymagające sekretów).
2. Overlay `.ai/project.md` (MCP `get_overlay`) — sekcja o kontrolach/testach/komendach,
   jeśli jest, oraz `codegen:`.

Brak obu → default: `ruff check`, `pytest -m "not integration"`,
`python manage.py makemigrations --check --dry-run`, `tsc --noEmit` w każdym pakiecie
frontendu, a przy `codegen: orval` (domyślnie) regeneracja klienta bez różnicy w `git diff`.
Zapisz jako założenie.

### 3. Baza zielona

Odpal bramki raz na czystym `origin/$BASE`. Czerwone → **halt** (przypadek C).

### 4. Kolejność

Dla każdego issue z listy:
`gh api repos/<owner>/<repo>/issues/<N>/dependencies/blocked_by --jq '.[].number'`.
Kolejność topologiczna; przy remisie kolejność z celu. Blokujący spoza listy i otwarty →
ticket dostaje needs-human „zablokowany przez #X spoza listy”.

## Łańcuch na ticket — dokładnie ten

1. `/git-start #N`. Sprawdź bazę brancha: jeśli `/git-start` wybrał inną niż `BASE`, utwórz
   branch sam: `gh issue develop N --name <typ>/<N>-<slug> --base $BASE --checkout`.
2. **Duży ticket** (więcej niż 3 kryteria akceptacji albo zmiany w więcej niż jednej
   aplikacji/pakiecie): `superpowers:writing-plans`, wykonanie **zawsze** przez
   `superpowers:subagent-driven-development` — nie pytaj o wybór. Mały: bez planu.
3. Kod test-first przez Matt `/tdd`; gdy niedostępny w kliencie —
   `superpowers:test-driven-development`. Nie oba naraz. Testy wg piramidy (niżej).
4. `superpowers:verification-before-completion` + wszystkie bramki jakości lokalnie.
5. `/git-commit`.
6. `/review-bugbot` + minimalny stack: `/review-backend` gdy diff dotyka backendu,
   `/review-frontend` gdy frontendu. Findingi potwierdzone → poprawka + test + `/git-commit`.
   Niepewne → do opisu PR, nie do kodu.
7. `/git-end` — review z kroku 6 **jest** potwierdzeniem review, nie zatrzymuj się na bramce.
   W opisie PR: raport testów, założenia (Q z przyjętą odpowiedzią), niepewne findingi.
   PR na inną bazę niż `BASE` → `gh pr edit <PR> --base $BASE`.
8. `gh pr checks <PR> --watch`. Czerwone → napraw i pushnij, maks. 2 próby.
9. `gh pr merge <PR> --merge`, potem `gh pr view <PR> --json state` (dowód: `MERGED`).
10. `gh issue comment N` (PR, liczby testów, założenia) + `gh issue close N`
    — `Closes #N` nie zamyka issue przy merge na gałąź inną niż domyślna.
11. `git checkout $BASE && git pull` przed następnym ticketem.

## Testy — piramida po zależności, nie po warstwie

| Poziom | Test | 
| --- | --- |
| unit | nie dotyka bazy (logika czysta, mapowania, value objecty) |
| integration-db | `django_db` — serwisy z ORM, modele, endpointy, webhooki |
| integration | żywe usługi (Postgres, Redis, MinIO…) — istniejący marker `integration` |
| e2e | Playwright (lub inny runner e2e w repo) |

- Zewnętrzne API płatności i podobne zawsze atrapą.
- **Nowe e2e** tylko gdy issue wprost tego wymaga **i** runner e2e istnieje w repo. Inaczej
  piszesz test przepływu na API i w raporcie nazywasz go „test przepływu na API”, nie e2e.
- Liczby **z komend**, nie z pamięci: `pytest <pliki> -m <marker> --co -q`. Brak markerów
  poziomów → liczby per plik testowy (`pytest <plik> --co -q`) i adnotacja „brak markerów”.
- Raport: `unit/x, integration-db/y, integration/z, e2e/w` (albo per plik) — w opisie PR
  i w transkrypcie.

## Zakazy

- Nie skipujesz, nie usuwasz i nie osłabiasz testów, żeby CI było zielone.
- Nie `--no-verify`.
- Nie pushujesz bezpośrednio na `BASE` ani inną chronioną gałąź — na nią tylko merge PR po
  zielonym CI.

## Gdy ticket napotka problem

### Wyzwalacze

**needs-human** (przypadek A lub B): kryterium akceptacji niejasne albo sprzeczne
z ADR/`CONTEXT.md`; decyzja produktowa/prawna, której nie ma w issue ani docs; CI czerwone
po 2 próbach naprawy; merge zablokowany przez ochronę gałęzi (wymagane review itp.) — PR
zostaje otwarty.

**halt** (przypadek C): czerwona gałąź bazowa, awaria CI/infrastruktury, brak sekretów,
limit API.

### Zasięg — zanim cokolwiek zrobisz

Które pozostałe tickety z listy od tego zależą:

- jawnie: relacja blocked-by,
- niejawnie: ticket zmienia model/pole/serwis/endpoint, z którego korzysta inny ticket
  (sprawdź treść issue i kod).

### Trzy przypadki

- **A — tylko ten ticket:** raport na issue, branch wypchnięty albo porzucony (bez merge),
  następny ticket.
- **B — część listy:** raport na issue + na każdym zależnym
  `needs-human: czeka na odpowiedzi z #N`; wykonujesz tylko tickety spoza zasięgu.
- **C — wszystko:** `night-run halted: <powód>` na pierwszym issue z listy, NIGHT-RUN REPORT,
  koniec pracy.

### Decyzja odwracalna — nie blokuj

Niejasność, którą da się rozstrzygnąć odwracalnie (nazwa, kształt odpowiedzi nowego
endpointu, wartość domyślna), **i** która nie dotyka pieniędzy, danych osobowych ani migracji
usuwającej dane → przyjmij najbezpieczniejsze założenie, zrób ticket, wpisz je do opisu PR
jako Q z przyjętą odpowiedzią. Blokuje tylko to, czego nie da się cofnąć.

### Format raportu needs-human (komentarz na issue)

```markdown
needs-human: <jedno zdanie, co stoi>

Q1. <pytanie>
- Opcje: a) … b) …
- Moja rekomendacja: … bo …
- Konsekwencja wyboru: …

Q2. …

Sprawdzone: <pliki, ADR, testy, komendy z wynikiem>
Wpływ: blokuje #X, #Y · nie blokuje #Z
Stan kodu: branch <nazwa> wypchnięty / porzucony
```

## NIGHT-RUN REPORT — ostatnia wiadomość

Warunek `/goal` sprawdza transkrypt, więc raport i dowody muszą paść w rozmowie.

```markdown
## NIGHT-RUN REPORT
Baza: <BASE> — <powód>
Bramki: <lista> (źródło: CI / overlay / założenie)

| Ticket | Stan | Dowód |
| --- | --- | --- |
| #N | MERGED | `gh pr view <PR> --json state` → MERGED; testy unit/x, integration-db/y… |
| #M | needs-human | <link do komentarza> |
| #K | halted | <link do komentarza night-run halted> |

Założenia: <co przyjęto bez danych z repo>
```

Każdy ticket z listy ma w tabeli dokładnie jeden wiersz. Brak dowodu = ticket nie jest skończony.
