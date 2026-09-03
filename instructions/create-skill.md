# `/create-skill` — od pomysłu na skill przez rozstrzygnięcie do zaakceptowanego issue

> **Czym jest ten dokument.** Opisem skilla, który **już istnieje**:
> `templates/shared/agents/create-skill.md` (plus wrapper komendy
> `.claude/commands/create-skill.md`). Dokument tłumaczy, po co ta komenda
> powstała, jak przebiega rozmowa i gdzie najłatwiej się nią skaleczyć.
>
> `/create-skill` jest rodzeństwem `/create-task`. Różnica jest jedna, ale
> nietrywialna: zanim cokolwiek oceni, musi **rozstrzygnąć, czy to w ogóle
> jest skill** — bo w praktyce co drugi „pomysł na skill" jest agentem.
>
> Sąsiedzi: zwykłe zadanie → [create-task.md](create-task.md) · budowanie po
> utworzeniu issue → [start-feat.md](start-feat.md) · rzemiosło pisania
> `SKILL.md` → skill `skill-authoring`.

---

## Po co to jest

Skill to plik, który model wczytuje **sam**, gdy uzna, że pasuje do sytuacji.
To znaczy, że skill zepsuty źle działa dwukrotnie: albo nie odpala się nigdy
(leży w repo, kosztuje utrzymanie, nie robi nic), albo odpala się wszędzie
(zaśmieca kontekst przy zadaniach, których nie dotyczy). Obie awarie są ciche —
nie ma testu, który by je złapał, i nie ma momentu, w którym coś zaświeci na
czerwono.

Dlatego najdroższy błąd przy skillach nie leży w treści, tylko **przed nią**:
w decyzji, że to w ogóle ma być skill, i w `description`, po którym model ma
zdecydować, czy go wczytać. `gh issue create` załatwia formatowanie; nie
załatwia żadnej z tych dwóch rzeczy.

`/create-skill` robi trzy rzeczy, których ręcznie nie robisz nigdy:

1. **rozstrzyga skill kontra agent** i ma prawo powiedzieć „to agent, idź do
   `/create-task`";
2. **ocenia pomysł na tle prawdziwego repo** — czy taki skill już jest, czy
   nazwa nie koliduje z agentem, czy jest gdzie go wpiąć;
3. **wymusza kryterium odpalenia i nieodpalenia**, czyli jedyny sposób
   sprawdzić `description` bez zgadywania.

### Czym to NIE jest

- **Nie pisze `SKILL.md`.** Wyjściem jest issue. Pisanie zaczyna się od
  `/git-start <N>`, a rzemiosłem (frontmatter, sufit długości, `references/`,
  degradacja u klientów bez natywnych skilli) zajmuje się skill
  `skill-authoring`. `/create-skill` **odsyła** do niego i świadomie nie
  powtarza jego treści.
- **Nie zakłada brancha i nie commituje.**
- **Nie jest przeglądem istniejących skilli.** Czyta je, żeby ocenić jeden
  pomysł, a nie żeby recenzować to, co już leży.
- **Nie jest planowaniem implementacji.** Karta ma plan na 3–5 punktów; to
  szkic kierunku, nie specyfikacja.

---

## Przebieg w całości

```text
Twoj pomysl na skill (jedno zdanie, moze byc mgliste)
   │
   ▼
FAZA 0  rozpoznanie repo          agent czyta, nic nie pyta
   │                              skille, agenci, AGENTS.md, issue, etykiety
   ▼
FAZA 1  skill czy agent + ocena   werdykt wprost, jeden z szesciu
   │                              ← tu temat moze upasc
   │                              ← tu pomysl moze wyjsc jako AGENT
   ▼
FAZA 2  dopytywanie               max 4 pytania, pierwsze o zdania odpalajace
   │
   ▼
FAZA 3  karta issue               pelny podglad: pola GitHuba + tresc
   │
   ▼
FAZA 4  petla akceptacji  ◄──┐    tak / anuluj / zmien
   │                         │
   │  zmiana ────────────────┘    agent weryfikuje zmiane i wraca do FAZY 3
   │
   ├─ tak    ──► gh issue create (+ sub_issues przy --parent)
   └─ anuluj ──► nic nie powstaje
```

Do końca FAZY 4 **żadna komenda `gh`, która zmienia stan, nie leci**. W fazach
0–3 wyłącznie odczyty (`ls`, `cat`, `gh issue list`, `gh label list`). Jedyny
wyjątek od tej reguły opisuje FAZA 4 (`gh label create`, po osobnej zgodzie).

---

## `--help`

`--help`, `help` i `-h` **kończą działanie** — agent nie ocenia i nie tworzy,
wypisuje pomoc i milknie.

```markdown
# /create-skill — pomoc

## Co robi
Rozstrzyga czy pomysl to skill czy agent, ocenia go na tle repo, dopytuje
o braki, sklada karte (nazwa, description, zasoby, klienci, kryterium)
i tworzy issue dopiero po Twojej akceptacji. Nie pisze SKILL.md.

## Wywolanie
/create-skill                      Pyta o pomysl od zera
/create-skill "konwencje migracji" Zaczyna od tego zdania
/create-skill --dry-run            Konczy na karcie, nie tworzy niczego
/create-skill --no-assign          Nie przypisuje @me (backlog)
/create-skill --parent #88         Tworzy jako sub-issue pod #88
/create-skill --quick              Pomija FAZE 1, zaklada ze to skill i ma sens

## Wyjscie
Numer issue + link. Przy --dry-run lub anulowaniu: sama karta.
Potem: /git-start <N>
```

| Wywołanie | Kiedy tego używasz |
| --- | --- |
| `/create-skill` | Masz przeczucie, że coś powinno być skillem |
| `/create-skill "…"` | Masz jedno zdanie i chcesz wiedzieć, czy to skill |
| `/create-skill --dry-run` | Chcesz zobaczyć kartę, nic nie tworząc |
| `/create-skill --no-assign` | Zapisujesz na kiedyś |
| `/create-skill --parent #88` | Skill jest częścią większej zmiany w kicie |
| `/create-skill --quick` | Wiesz, że to skill i że ma sens — chcesz tylko zapis |

**Flag `--label`, `--title`, `--body` nie ma i nie należy ich dodawać.** Tytuł
i etykietę weryfikujesz w FAZIE 4; podanie ich z góry omijałoby tę weryfikację,
a to połowa powodu, dla którego ta komenda istnieje.

Flagi spoza tej listy agent **nazywa i pyta**, zamiast zgadywać, co miałeś na
myśli.

---

## FAZA 0 — rozpoznanie repo

Zanim agent cokolwiek powie, czyta. Nie pyta o nic, czego może dowiedzieć się
sam. To cała różnica między „ocenia pomysł" a „udaje, że ocenia".

| Co | Po co | Komenda |
| --- | --- | --- |
| Istniejące skille | Czy to już jest; jak wyglądają sąsiedzi | `ls templates/shared/skills/ templates/cursor/skills/` |
| Agenci | Kolizja nazw — u części klientów lądują w tym samym katalogu | `ls templates/shared/agents/` |
| Konwencje kita | Czy pomysł nie łamie ustalonych zasad | `cat AGENTS.md` |
| Istniejące issue | Czy to już zgłoszone | `gh issue list --state all --search "<słowa>" --limit 20` |
| Etykiety | Żeby nie wymyślać nieistniejących | `gh label list --limit 50` |

**Limit: pięć odczytów, żadnego czytania plików w całości poza `AGENTS.md`.**
Bez limitu faza zjada kontekst i kończy się tym, że agent zna repo, ale nie ma
już miejsca na rozmowę.

Odczyt agentów jest tu ważniejszy niż w `/create-task` i ma konkretny powód:
w kicie skille i agenci trafiają u części klientów do **tego samego katalogu**.
Skill o nazwie, którą nosi już agent, nie jest niezręcznością — jest kolizją
przy instalacji.

Agent **nie relacjonuje**, co przeczytał, linijka po linijce. Streszcza jednym
zdaniem i idzie dalej.

---

## FAZA 1 — skill czy agent, i czy w ogóle

Agent wydaje **jeden z sześciu werdyktów**. Zawsze wprost, zawsze w pierwszym
zdaniu, przed uzasadnieniem.

| Werdykt | Co znaczy | Co się dzieje dalej |
| --- | --- | --- |
| **Ma sens** | To skill, nie ma go, da się wpiąć | FAZA 2 |
| **Ma sens, ale** | To skill, ale coś trzeba przestawić | FAZA 2, uwagi w karcie |
| **To nie skill, to agent** | Wiedza ma sens tylko wywołana ręcznie | Odesłanie do `/create-task`, koniec |
| **Już istnieje** | Zrobione albo zgłoszone | Link, pytanie czy mimo to |
| **Nie w tej formie** | Cel dobry, ujęcie złe | Propozycja innego ujęcia |
| **Nie w tym projekcie** | To nie należy do kita | Uzasadnienie, koniec |

Werdykt „nie" **i** werdykt „to agent" muszą być realnymi możliwościami,
inaczej cała faza jest teatrem. Agent, który zawsze mówi „świetny skill", nie
ma po co czytać repo.

### Rozstrzygnięcie skill vs agent

To najważniejsza rzecz, którą ta komenda robi, bo w potocznym języku „skill"
znaczy jedno i drugie.

| | Skill | Agent |
| --- | --- | --- |
| Kto odpala | model sam, po `description` | człowiek, przez `/nazwa` |
| Kiedy | gdy rozpozna pasujący kontekst | gdy ktoś zdecyduje |
| Wynik | zmienia sposób pracy nad czymś innym | konkretny artefakt tu i teraz |
| Kształt | wiedza, konwencje, kryteria | przebieg, fazy, kroki |
| Zasoby | `references/`, `scripts/`, `assets/` | jeden plik |

**Test rozstrzygający: czy ta treść ma sens, gdy nikt jej nie wywoła?**

Konwencje migracji przydają się w chwili, gdy ktoś pisze migrację — choćby nie
wiedział, że skill istnieje. To skill. „Zbierz diff, oceń go, zrób PR" nie
zadzieje się bez czyjejś decyzji. To agent.

**Drugi sygnał:** jeśli pomysł da się zapisać jako fazy i kroki z pętlą
akceptacji — to agent. Skill nie ma faz, bo nie wie, w którym momencie pracy
został wczytany.

### Uwagi agenta — format

Lista, każda pozycja w jednej linii, każda z konsekwencją, bez zmiękczania:

```text
Werdykt: ma sens, ale.

- W templates/shared/skills/ jest dzis jeden skill (skill-authoring).
  Ten bedzie drugi, wiec ustala wzorzec dla nastepnych.
- Nazwa "migrations" koliduje z niczym, ale "migrate" juz tak — jest
  agent o tej nazwie i u czesci klientow lada w tym samym katalogu.
- Polowa tego, co opisujesz, to kroki ("najpierw zrob makemigrations,
  potem sprawdz"). Kroki nalezy wyrzucic — skill nie wie, w ktorym
  momencie go wczytano.

Idziemy dalej czy odpuszczamy?
```

Ostatnie pytanie jest obowiązkowe. Temat ma móc upaść **tutaj**, zanim
ktokolwiek napisze zdanie do issue.

`--quick` pomija tę fazę w całości — i razem z nią całą wartość komendy.

---

## FAZA 2 — dopytywanie

Agent pyta **tylko o to, czego nie wyczytał z repo**. Przy skillu zostają
w praktyce cztery niewiadome, i pierwsza jest nieusuwalna:

1. **Jakie zdania użytkownika mają go odpalić?** Konkretne sformułowania, nie
   temat. To wprost materiał na `description`. Modele **niedoodpalają** skille
   — bez listy zdań skill będzie leżał nietknięty.
2. **Co jest wynikiem?** Zmieniony sposób pracy, format wyjścia, kryteria
   oceny.
3. **Czy potrzebuje czegoś obok `SKILL.md`?** `references/`, `scripts/`,
   `assets/`.
4. **Czy ma się odpalać sam?** `disable-model-invocation: true` tylko wtedy,
   gdy skill jest związany z jednym klientem albo przypadkowe odpalenie byłoby
   szkodliwe.

**Limit: cztery pytania.** Piąte znaczy, że pomysł nie jest gotowy na issue —
agent mówi to wprost i odsyła do `/grill-me`.

Nazwę, klientów i etykietę agent **proponuje sam** z tego, co przeczytał, i
pokazuje w karcie. Poprawiasz w FAZIE 4, jeśli trafił źle.

---

## FAZA 3 — karta issue

Karta jest **pełnym podglądem tego, co się wydarzy**: nie tylko treść, ale każde
pole, które agent ustawi w GitHubie. Zasada: **nic, czego nie ma na karcie, nie
zostanie ustawione.**

```text
╭─ KARTA ISSUE (skill) ─────────────────────────────────────────╮
Tytul      Add django-migrations skill for migration conventions
Etykieta   type: feature                  [istnieje w repo]
Assignee   @me                            [brak przy --no-assign]
Rodzic     brak                           [#88 przy --parent]
Katalog    templates/shared/skills/django-migrations/
Zasoby     references/
Klienci    wszyscy (3 natywnie, 5 przez degradacje do komendy)
──────────────────────── TRESC ─────────────────────────────────

## Co ma dzialac
Gdy ktos w tym repo pisze albo recenzuje migracje Django, model zna
konwencje projektu bez proszenia o nie.

## Frontmatter
name: django-migrations
description: Konwencje migracji Django w tym repo — nazewnictwo,
  migracje danych, kolejnosc, rollback. Use when piszesz migracje,
  robisz makemigrations, zmieniasz model, recenzujesz katalog
  migrations/.

## Zakres
- templates/shared/skills/django-migrations/SKILL.md — nazewnictwo,
  migracje danych, kolejnosc deployu, rollback
- references/przyklady.md — trzy migracje z tego repo z komentarzem
Poza zakresem: konfiguracja bazy, tuning zapytan, wybor silnika.

## Kryterium ukonczenia
Odpala sie: "dodaj pole status do modelu Order"
Nie odpala sie: "napisz zapytanie liczace zamowienia po statusie"
Instalacja: bootstrap --clients all instaluje go u wszystkich klientow

## Plan skrocony
1. SKILL.md: nazewnictwo + migracje danych + kolejnosc.
2. references/przyklady.md z trzech istniejacych migracji.
3. Sprawdzenie sufitu dlugosci wg skill-authoring.
4. Test odpalenia i nieodpalenia na dwoch zdaniach z kryterium.

## Otwarte pytanie
Czy skill ma obejmowac rollback produkcyjny, czy to osobna sprawa?
Domyslnie zakladam, ze obejmuje jednym akapitem.

## Kontekst
Wyszlo z rozmowy o migracji #112, gdzie agent zaproponowal nazwe
niezgodna z reszta katalogu. Drugi skill w templates/shared/skills/.
Rzemioslo: skill skill-authoring.
╰───────────────────────────────────────────────────────────────╯

[t] tworze   [a] anuluj   albo napisz, co zmienic
```

### Sekcje karty i po co która jest

| Sekcja | Po co jest |
| --- | --- |
| **Katalog / Klienci / Zasoby** | Pola instalacyjne — widać, co realnie powstanie i gdzie |
| **Co ma działać** | Zdanie stanu, które przetrwa miesiąc leżenia w backlogu |
| **Frontmatter** | `description` jest produktem, nie ozdobą — musi być widoczny przed utworzeniem |
| **Zakres** | Razem z „poza zakresem"; druga połowa powstrzymuje rozjazd |
| **Kryterium ukończenia** | Zdanie odpalające **i** nieodpalające — jedyny sposób sprawdzić `description` |
| **Plan skrócony** | 3–5 punktów; mówi, że wiadomo **jak**, nie tylko **co** |
| **Otwarte pytanie** | Mówi wykonawcy, gdzie ma przystanąć zamiast zgadywać |
| **Kontekst** | Skąd się to wzięło + konkret z repo (ścieżka, numer issue) |

**Kryterium nieodpalenia jest tu ważniejsze niż w `/create-task`.** Skill, który
wchodzi wszędzie, jest tak samo zepsuty jak ten, który nie wchodzi nigdy — a bez
zdania „po tym skill ma zostać w spokoju" nikt tego drugiego przypadku nie
sprawdzi.

`Kontekst` z ogólnikiem („pasuje do kita", „przyda się") to sygnał, że FAZA 0
nie zadziałała i agent ocenia po samej nazwie pomysłu.

---

## FAZA 4 — pętla akceptacji

Trzy wyjścia; tylko jedno kończy się utworzeniem issue.

**Przy `--dry-run` wyjścia `t` nie ma.** Zmiany agent przyjmuje dalej, na `t`
odmawia i przypomina, żeby powtórzyć bez flagi. Zero komend `gh`
zmieniających cokolwiek.

### `t` — tworzę

Dopiero tutaj lecą komendy zapisujące, i agent raportuje każdą. Repo bierze
z klona, `<owner>/<repo>` z `gh repo view --json nameWithOwner -q .nameWithOwner`.

```bash
gh issue create \
  --title "<title EN>" \
  --label "<etykieta z karty>" \
  --assignee @me \
  --body-file - <<'BODY'
…tresc z karty…
BODY

# tylko przy --parent; w sciezce numer issue, w sub_issue_id numeryczne db id
gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues \
  -F sub_issue_id=$(gh api repos/<owner>/<repo>/issues/<N> --jq .id)
```

Przy `--no-assign` znika `--assignee @me`; karta ma wtedy `Assignee brak`.

Numer issue agent bierze **wyłącznie z outputu `create`**, nigdy z
`gh issue list --limit 1` — przy równoległej pracy to pomyłka o cudze zadanie.
Jeśli druga komenda padnie, mówi, że **issue już istnieje**, podaje numer i
czego nie dopiął. Nie zaczyna od zera.

Kończy raportem: numer, link, `/git-start <N>`.

### `a` — anuluj

Temat upada, nic nie powstaje. Agent **nie** ratuje pomysłu i nie pyta „na
pewno?". Jedyne, co proponuje: zapis karty do `.scratch/` — też tylko za zgodą.

### Cokolwiek innego — zmiana

Piszesz zwykłym zdaniem, co ma być inaczej. Agent **weryfikuje zmianę, zanim ją
przyjmie**, i wraca do FAZY 3 z nową kartą i jedną linijką o tym, co zmienił.

| Zmieniasz | Co agent sprawdza |
| --- | --- |
| Nazwę | kebab-case; brak kolizji w `shared/skills` **i** `shared/agents` |
| `description` | Czy mówi **kiedy odpalić**, czy tylko o czym jest |
| Zasoby | Czy skill przeżyje degradację do jednego pliku bez nich |
| Etykietę | Czy istnieje (`gh label list`); czy pasuje do treści |
| Tytuł | Czy po angielsku; czy opisuje stan, nie czynność |
| Kryterium | Czy da się je sprawdzić bez pytania Ciebie |
| Rodzica | Czy issue istnieje i jest otwarte |
| Plan | Czy nadal mieści się w pięciu punktach |

### Dwie weryfikacje, które są tu specyficzne

**`description` bez „kiedy".** Najczęstsza poprawka użytkownika brzmi „napisz
to krócej", a najczęstszy efekt to opis tematu bez zdań odpalających:

```text
> skroc description do "Konwencje migracji Django"

Skrocone, ale to zabija skill. Tak zapisany description mowi, o czym
skill jest, i nie mowi, kiedy go wczytac — model nie ma po czym
rozpoznac sytuacji i skill nie odpali sie prawie nigdy. Zostawiam
Twoja wersje, ale kryterium odpalenia z karty przestaje byc spelnialne.
Proponuje: temat + "Use when <trzy zdania uzytkownika>".
```

**Zasoby, które ktoś obiecuje na później.** `references/` ma sens tylko wtedy,
gdy `SKILL.md` bez nich nadal działa — u klientów bez natywnych skilli zostaje
jeden plik:

```text
> wywal SKILL.md do minimum, reszta pojdzie do references/

Wtedy skill nie przezyje degradacji. U 5 z 8 klientow instaluje sie
jako pojedyncza komenda i references/ nie jedzie razem z nim. SKILL.md
musi byc kompletny sam w sobie; references/ to przyklady i szczegoly,
nie tresc glowna.
```

### Etykieta — trzy przypadki

1. **Istnieje i pasuje** — agent podmienia i mówi jednym zdaniem.
2. **Istnieje, ale nie pasuje** — podmienia i **mówi, dlaczego to podejrzane**.
   Nie blokuje. To Twoje repo.
3. **Nie istnieje** — nie zmyśla i nie tworzy po cichu. Proponuje
   `gh label create` i **pyta osobno**.

Tworzenie etykiety to **jedyny zapis dozwolony przed `t`** — i nie przy
`--dry-run`. Etykieta jest bytem repo, nie polem issue: powstaje raz i zostaje
dla wszystkich przyszłych zgłoszeń.

### Zmiana, która wywraca werdykt

Jeśli po Twojej zmianie pomysł jest już agentem, a nie skillem, agent mówi to
**zanim** pokaże kartę:

```text
> dorzuc jeszcze, zeby to samo odpalalo makemigrations i pokazywalo diff

To wywraca werdykt. Skill nie wykonuje krokow — z tym dodatkiem opisujesz
przebieg z decyzja czlowieka na starcie, czyli agenta. Przenosimy calosc
do /create-task czy zostawiamy skill i wycinamy ten punkt?
```

Bez tej reguły pętla akceptacji staje się drogą do przemycenia agenta
w przebraniu skilla — czyli dokładnie tego, co FAZA 1 miała odsiać.

### Ile razy można kręcić

Bez limitu, ale przy **czwartym** obrocie agent to zauważa: „Zwykle znaczy to,
że nie zgadzamy się co do samego pomysłu, a nie co do jego zapisu. Wracamy do
FAZY 1?"

---

## Etykiety

Agent wybiera **jedną** istniejącą etykietę — tę, która odpowiada typowi
Conventional z `.cursor/rules/git-branch-pr.mdc`, żeby `/git-start` →
`/git-commit` → `/git-end` się nie rozjechało.

```text
type: feature      nowy skill
type: fix          poprawka istniejacego skilla (nie odpala sie / odpala za czesto)
type: docs         zmiana wylacznie w tresci opisowej
```

To jedyny powód, dla którego ta komenda w ogóle wybiera etykietę.

---

## Przykład — cała rozmowa, z werdyktem „to agent"

```text
> /create-skill "chcialbym skill, ktory robi porzadek przed commitem"

Czytam repo... (5 odczytow: skille, agenci, AGENTS.md, issue, etykiety)

Werdykt: to nie skill, to agent.

- Opisujesz przebieg: zbierz zmiany, oceni je, usun smieci, zaproponuj
  commit. Skill nie wie, w ktorym momencie pracy zostal wczytany, wiec
  nie ma jak wykonac kroku "najpierw".
- Test: czy ta tresc ma sens, gdy nikt jej nie wywola? Nie — porzadek
  przed commitem zaczyna sie od Twojej decyzji, ze konczysz prace.
- W templates/shared/agents/ jest juz /cleanup, ktory robi polowe tego.
  Reszte robi /git-commit.

To zadanie na /create-task albo poprawka /cleanup. Konczę tutaj.

> to inaczej: skill o konwencjach nazywania migracji

Werdykt: ma sens.

- Nie ma takiego skilla; w templates/shared/skills/ jest dzis tylko
  skill-authoring, wiec ten bedzie drugi i ustali wzorzec.
- Nazwa django-migrations nie koliduje z zadnym agentem.
- Tresc jest deklaratywna (konwencje, nie kroki) — pasuje na skill.

Po jakich zdaniach ma sie odpalac?

> jak dodaje pole do modelu albo robie makemigrations

Co ma byc obok SKILL.md?

> przyklady z repo

╭─ KARTA ISSUE (skill) ──────────────────────────────────────╮
[pelna karta jak wyzej]
╰────────────────────────────────────────────────────────────╯

[t] tworze   [a] anuluj   albo napisz, co zmienic

> skroc description do "Konwencje migracji Django"

Skrocone, ale to zabija skill: description mowi, o czym jest, i nie
mowi, kiedy go wczytac. Kryterium odpalenia z karty przestaje byc
spelnialne. Zostawiam Twoj wybor.

╭─ KARTA ISSUE (skill) ──────────────────────────────────────╮
[karta ze skroconym description]
╰────────────────────────────────────────────────────────────╯

> ok wroc do poprzedniego i t

Description przywrocony.

#131 utworzone.
https://github.com/radthenone/ai-instruction-kit-mcp/issues/131

Gdy siadziesz: /git-start 131
```

---

## Gdzie to siedzi w całości

```text
pomysl "chce miec skill na X"
  │
  ├─ /create-skill ──► werdykt ──┬─ to agent ──► /create-task
  │                              ├─ odrzucone ──► koniec
  │                              │
  │                              └─ issue #131
  │                                   │
  │                                   └─ /git-start 131
  │                                        │
  │                                        └─ skill skill-authoring
  │                                           (frontmatter, sufit dlugosci,
  │                                            zasoby, degradacja)
  │
  └─ pomysl mglisty ──► /grill-me
                        (wracasz z konkretem albo bez pomyslu)
```

Granica jest ostra: **`/create-skill` kończy się na issue albo na jego braku.**
Ani jednej linijki `SKILL.md`.

---

## Zakazy wpisane w agenta

- Nie tworzyć issue ani niczego w GitHubie przed `t` w FAZIE 4. Jedyny wyjątek:
  `gh label create` po osobnej zgodzie, i nie przy `--dry-run`.
- Nie pisać `SKILL.md` i nie zakładać katalogu skilla.
- Nie powtarzać w issue treści skilla `skill-authoring` — odesłać do niego.
- Nie przyjmować zmiany z FAZY 4 na słowo, bez weryfikacji.
- Nie zakładać skilla o nazwie kolidującej z agentem.
- Nie rozpisywać specyfikacji — plan to sufit pięciu punktów.

---

## Pułapki

1. **Wszystko wygląda na skill.** „Skill" w potocznym użyciu znaczy „coś, co
   agent umie". Jeśli po kilku wywołaniach werdykt „to agent" nie padł ani razu,
   sprawdź, czy FAZA 1 naprawdę działa — bo statystycznie powinien padać często.

2. **`description` pisany jak tytuł rozdziału.** „Konwencje migracji" opisuje
   temat i nie mówi, kiedy skill wczytać. Skill z takim opisem leży nietknięty
   i wygląda dokładnie tak samo jak skill działający.

3. **Kryterium tylko odpalenia.** Łatwo napisać zdanie, po którym skill ma
   wejść, i pominąć to, po którym ma zostać w spokoju. Wtedy nie masz jak
   wykryć skilla, który wchodzi wszędzie.

4. **`SKILL.md` wydrążony do spisu treści.** Skill, którego treść siedzi
   w `references/`, przestaje działać u klientów bez natywnych skilli — a to
   większość instalacji kita.

5. **Kolizja nazwy z agentem.** Wychodzi dopiero przy instalacji, u konkretnego
   klienta, i wygląda jak błąd bootstrapu, a nie jak błąd nazwy.

6. **Ocena bez czytania.** Werdykt wydany po samej nazwie pomysłu brzmi tak
   samo pewnie jak ten po pięciu odczytach. `Kontekst` na karcie ma odwoływać
   się do konkretu — ścieżki, numeru issue, istniejącego skilla.

7. **`--quick` jako domyślne wywołanie.** Pomija FAZĘ 1, czyli jedyną rzecz,
   której `gh issue create` nie potrafi.

8. **Skille tworzone szybciej, niż są używane.** Każdy skill to stały koszt
   przy każdym starcie sesji — opis wchodzi do kontekstu niezależnie od tego,
   czy skill kiedykolwiek odpali.

---

## Czego ten skill nie zrobi

- **Nie napisze `SKILL.md`.** Od tego jest `/git-start` i `skill-authoring`.
- **Nie sprawdzi, czy skill faktycznie się odpala.** Kryterium z karty to
  zdanie do ręcznego przetestowania po napisaniu, nie test automatyczny.
- **Nie oszacuje, ile skilli to za dużo.** Widzi jeden pomysł, nie budżet
  kontekstu całej instalacji.
- **Nie wyłapie duplikatu „tym samym innymi słowami".** `ls` i `--search`
  znajdują nazwy i słowa, nie znaczenia.
- **Nie zdecyduje za Ciebie w przypadkach granicznych.** Część pomysłów jest
  równie sensowna jako skill i jako agent; agent powie, co widzi, i zostawi
  wybór.

---

## Do przemyślenia

- **Czy sześć werdyktów to nie o jeden za dużo.** „Nie w tej formie" i „nie
  w tym projekcie" w praktyce mogą schodzić do jednego zdania uzasadnienia.
- **Czy karta powinna pokazywać sąsiadów.** Lista trzech najbliższych
  istniejących skilli obok `description` ułatwiłaby wyłapanie zachodzenia na
  siebie — kosztem dłuższej karty.
- **Kryterium nieodpalenia da się częściowo sprawdzić maszynowo** — zderzając
  `description` nowego skilla z opisami już istniejących. Dziś tego nie ma.
- **`--quick` a wartość komendy.** Jeśli po tygodniu używasz wyłącznie
  `--quick`, znaczy to, że rozstrzygnięcie skill/agent masz już w głowie i
  komenda jest tylko szablonem.
- **Poprawka istniejącego skilla to inna rozmowa** („odpala się za często"),
  a dziś przechodzi tą samą ścieżką co nowy. Może osobna flaga, może osobna
  komenda.
