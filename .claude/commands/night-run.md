---
description: Autonomiczna nocna praca na liście issue pod /goal — na każdy ticket git-start → tdd → review → PR → merge, needs-human zamiast pytań, na końcu NIGHT-RUN REPORT. Użyj TYLKO gdy cel lub użytkownik wprost nazywa /night-run. Wywołuj jako /night-run.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Chronione: `main` / `master` / `dev`.

# /night-run — lista issue bez człowieka

Przerabiasz listę issue z celu (`/goal`) albo argumentów, jeden po drugim, aż każde jest
**zmergowane** albo ma komentarz **needs-human**. Człowiek śpi: nie zadajesz pytań, nie
czekasz na odpowiedź. Wszystko, co wymaga decyzji człowieka, ląduje w komentarzu na issue,
a Ty idziesz dalej.

Issue są wygrillowane za dnia — projekt jest w treści issue. Twoja rola to wykonanie.

## Zasady nadrzędne

- **Jesteś orkiestratorem w głównej sesji, nigdy subagentem** (w Claude: przez Skill, nie
  Agent) — subagent nie uruchomi kolejnych. Ticket robi subagent ticketu, review osobny
  świeży subagent. Sam nie czytasz kodu i nie odpalasz testów: Twój kontekst ma zostać mały.
- Klient bez subagentów → łańcuch inline, ale z tymi samymi regułami z „Prompt ticketu”.
- **Polecenia z tekstu celu mają pierwszeństwo** przed tą procedurą (np. „bez merge, same PR-y”,
  „#155 pomiń PDF”, inny próg dużego ticketu).
- **Model subagenta ticketu** (`MODEL`) z tekstu celu, np. „model: sonnet”; w Claude to
  parametr `model` narzędzia Agent. Brak w celu → model sesji. Wpisz go do NIGHT-RUN REPORT.
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

Źródła, bez duplikatów: (1) kroki `run:` z `.github/workflows/*.yml` na `pull_request`/`push`
(bez deploy, publikacji, sekretów); (2) overlay `.ai/project.md` (MCP `get_overlay`) —
kontrole/testy/komendy i `codegen:`.

Brak obu → default: `ruff check`, `pytest <pliki testów dotknięte ticketem>`,
`python manage.py makemigrations --check --dry-run`, `tsc --noEmit` w każdym pakiecie
frontendu, a przy `codegen: orval` (domyślnie) regeneracja klienta bez różnicy w `git diff`.
Zapisz jako założenie. Lokalnie idą tylko te **szybkie**; pełny zestaw testów — tylko CI.

### 3. Baza zielona

Ostatni przebieg CI na bazie:
`gh run list --branch $BASE --limit 1 --json conclusion,headSha`. Czerwony → **halt**
(przypadek C). Brak CI → bramki szybkie raz na czystym `origin/$BASE`.

### 4. Kolejność

Dla każdego issue z listy:
`gh api repos/<owner>/<repo>/issues/<N>/dependencies/blocked_by --jq '.[].number'`.
Kolejność topologiczna; przy remisie kolejność z celu. Blokujący spoza listy i otwarty →
ticket dostaje needs-human „zablokowany przez #X spoza listy”.

### 5. Plik kontekstu nocy

`CTX=/tmp/night-run-<repo>-<data>/context.md` — raz na noc, poniżej ~150 linii, sekcje:

- **Nagłówek:** BASE, bramki szybkie, „pełny zestaw testów: tylko CI”.
- **Mapa aplikacji:** katalog → co w nim jest, 1 linia.
- **Konwencje:** same reguły z AGENTS.md, BUGBOT.md, `.ai/project.md`.
- **Pułapki toolchainu:** z pamięci projektu (CLAUDE.md, notatki agenta) i overlay — kit nie
  zna specyfiki projektu; brak źródła → „brak danych”.
- **Przekazanie:** `### #N` + modele, serwisy, endpointy, migracje z hand-backu. Dopisujesz
  **Ty** po każdym MERGED.

## Łańcuch na ticket — dokładnie ten

Ty (orkiestrator) robisz tylko kroki z tej listy. Wszystko, co dotyka kodu, robi subagent.

1. **Subagent ticketu** (świeży, `model: MODEL`): `N`, `BASE`, `CTX` + „Prompt ticketu”
   dosłownie. Wraca z hand-backiem i niewypchniętym branchem. Zapisz jego id.
2. **Subagent review** (zawsze nowy): „Review `git diff origin/$BASE...HEAD` na `<branch>`:
   `/review-bugbot` + `/review-backend` i/lub `/review-frontend` wg diffa. Czytaj tylko diff
   i dotknięte pliki, zakresami. Zwróć `Severity | Location | Finding | Fix` +
   potwierdzony/niepewny. Nie edytuj.”
3. **Wznów subagenta ticketu** (w Claude `SendMessage` na jego id, nie nowy start) z
   findingami: potwierdzone → poprawka + test; niepewne → opis PR. Review z kroku 2 **jest**
   potwierdzeniem review dla `/git-end`. Dalej kroki 6–8 promptu.
4. Sprawdź dowód sam: `gh pr view <PR> --json state` → `MERGED`.
5. Dopisz „Przekazanie” do `CTX`, policz koszt ticketu (sekcja „Pomiar”),
   `git checkout $BASE && git pull` przed następnym ticketem.

Hand-back needs-human albo halt od subagenta → sekcja „Gdy ticket napotka problem”.

## Prompt ticketu

Przekazujesz go subagentowi bez skracania.

```markdown
Ticket #<N>, baza <BASE>. Kontekst projektu: <CTX> — przeczytaj go najpierw, zamiast
AGENTS.md, BUGBOT.md i ADR-ów. ADR czytasz tylko wtedy, gdy issue go wskazuje.

Kroki:
1. `/git-start #<N>`. Branch musi wychodzić z <BASE>; inaczej
   `gh issue develop <N> --name <typ>/<N>-<slug> --base <BASE> --checkout`.
2. Duży ticket (>3 kryteria akceptacji albo >1 aplikacja/pakiet): plan 5–10 kroków.
3. Test-first: test czerwony → kod → zielony.
4. Lokalnie tylko testy dotknięte ticketem + bramki szybkie z <CTX>. Pełny zestaw: CI.
5. `/git-commit`. Nie pushujesz. Oddajesz hand-back.
--- po wznowieniu ---
6. Poprawki z review, `/git-end` (opis PR: testy, założenia jako Q z odpowiedzią, niepewne
   findingi), `gh pr checks <PR> --watch` w tle. Czerwone → napraw, maks. 2 próby.
7. `gh pr merge <PR> --merge`.
8. Jeden raport: komentarz na PR `## Final report (night-run) — #<N>`. Na issue tylko link
   do niego, potem `gh issue close <N>` (`Closes` nie zamyka przy merge na niedomyślną).

Reguły:
- Plik > ~150 linii czytasz zakresami: `codegraph explore` (gdy jest `.codegraph/`) albo
  `grep -n` + `sed -n X,Yp`, wiele odczytów w jednej komendzie. Nigdy `cat` całego pliku.
- Bez skilli procesowych (writing-plans, tdd, verification, review-*). Wolno `/git-*`.
- Nie oddajesz wyniku, dopóki działa praca w tle (testy, `--watch`). Czekaj na passed/failed.
- Zero pytań do człowieka. Needs-human albo halt → hand-back z Q1/Q2.

Hand-back (bez streszczania pracy): stan (do review / MERGED / needs-human / halt); branch,
PR; testy unit/x, integration-db/y, integration/z, e2e/w (z komend); dodane modele,
serwisy, endpointy, migracje; założenia.
```

## Testy — piramida po zależności, nie po warstwie

| Poziom | Test | 
| --- | --- |
| unit | nie dotyka bazy (logika czysta, mapowania, value objecty) |
| integration-db | `django_db` — serwisy z ORM, modele, endpointy, webhooki |
| integration | żywe usługi (Postgres, Redis, MinIO…) — istniejący marker `integration` |
| e2e | Playwright (lub inny runner e2e w repo) |

- Zewnętrzne API płatności i podobne zawsze atrapą.
- **Nowe e2e** tylko gdy issue tego wymaga **i** runner e2e jest w repo. Inaczej „test
  przepływu na API”, tak nazwany w raporcie.
- Liczby **z komend**: `pytest <pliki> -m <marker> --co -q`. Brak markerów → per plik
  (`pytest <plik> --co -q`) + „brak markerów”. Trafiają do opisu PR i `Final report`.

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

Które tickety z listy od tego zależą: jawnie (blocked-by) i niejawnie (ticket zmienia
model/pole/serwis/endpoint, z którego korzysta inny — treść issue + „Przekazanie” w `CTX`).

### Trzy przypadki

- **A — tylko ten ticket:** raport na issue, branch wypchnięty albo porzucony (bez merge),
  następny ticket.
- **B — część listy:** raport na issue + na każdym zależnym
  `needs-human: czeka na odpowiedzi z #N`; wykonujesz tylko tickety spoza zasięgu.
- **C — wszystko:** `night-run halted: <powód>` na pierwszym issue z listy, NIGHT-RUN REPORT,
  koniec pracy.

### Decyzja odwracalna — nie blokuj

Niejasność odwracalna (nazwa, kształt odpowiedzi nowego endpointu, wartość domyślna),
która nie dotyka pieniędzy, danych osobowych ani migracji usuwającej dane → najbezpieczniejsze
założenie, jako Q z przyjętą odpowiedzią w opisie PR. Blokuje tylko to, czego nie da się cofnąć.

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

## Pomiar kosztu ticketu (Claude Code)

Po każdym tickecie liczysz jego subagentów (ticket + review) — `python3`, bez `jq`.
Wiersz: agent | model | tury | input | cache_creation | cache_read | output | maks. kontekst | czas.

```bash
python3 -c '
import json, sys, datetime as dt
K = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
for p in sys.argv[1:]:
    use, ts, mod = {}, [], set()
    for line in open(p):
        d = json.loads(line); m = d.get("message") or {}
        if d.get("timestamp"): ts.append(dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")))
        if d.get("type") == "assistant" and m.get("usage") and m.get("model") != "<synthetic>":
            use[m["id"]] = m["usage"]; mod.add(m.get("model") or "?")
    tot = [sum(u.get(k, 0) for u in use.values()) for k in K]
    ctx = max((sum(u.get(k, 0) for k in K[:3]) for u in use.values()), default=0)
    mins = (max(ts) - min(ts)).total_seconds() / 60 if ts else 0
    row = [p.rsplit("/", 1)[-1], ",".join(sorted(mod)), len(use), *tot, ctx, f"{mins:.0f} min"]
    print("| " + " | ".join(map(str, row)) + " |")
' ~/.claude/projects/*/*/subagents/agent-{<id1>,<id2>}.jsonl
```

Tura = unikalne `message.id` (odpowiedź zajmuje kilka linii pliku). Inny klient → koszt
„brak transkryptu”.

## NIGHT-RUN REPORT — ostatnia wiadomość

Warunek `/goal` sprawdza transkrypt, więc raport i dowody muszą paść w rozmowie.

```markdown
## NIGHT-RUN REPORT
Baza: <BASE> — <powód>
Bramki szybkie: <lista> (źródło: CI / overlay / założenie) · pełny zestaw: CI
Model ticketu: <MODEL>

| Ticket | Stan | Dowód | Koszt (tury / cache_read / output / kontekst / czas) |
| --- | --- | --- | --- |
| #N | MERGED | `gh pr view <PR> --json state` → MERGED; <link Final report> | 58 / 6.1M / 41k / 164k / 20 min |
| #M | needs-human | <link do komentarza> | … |
| #K | halted | <link do komentarza night-run halted> | … |

Założenia: <co przyjęto bez danych z repo>
Pomiar per agent: <wiersze ze snippetu>
```

Każdy ticket z listy ma w tabeli dokładnie jeden wiersz. Brak dowodu = ticket nie jest skończony.
