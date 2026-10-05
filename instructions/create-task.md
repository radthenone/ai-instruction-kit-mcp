# `/create-task` — od pomysłu przez ocenę do zaakceptowanego issue

> **Czym jest ten dokument.** Makietą skilla, którego **jeszcze nie ma**.
> Wcześniejszy szkic był formularzem: cztery stałe pytania i gotowy szablon.
> Ta wersja dokłada dwie rzeczy, których tam brakowało:
>
> 1. **agent ocenia pomysł na tle prawdziwego repo** i ma prawo powiedzieć
>    „to nie ma sensu" albo „to już jest";
> 2. **nic nie powstaje bez pętli akceptacji** — widzisz pełną kartę issue,
>    zmieniasz co chcesz, agent weryfikuje Twoją zmianę i pokazuje kartę
>    jeszcze raz, aż powiesz „tak" albo „anuluj".
>
> Sąsiedzi: budowanie po utworzeniu zadania → [start-feat.md](start-feat.md) ·
> zgłoszenie błędu → [start-fix.md](start-fix.md).

---

## Po co to jest

Wersja pierwsza zakładała, że pomysł jest dobry, i pytała tylko, jak go
zapisać. To załatwia formatowanie, ale nie ratuje przed najdroższym błędem:
starannie opisanym issue na coś, czego nie warto robić, co już istnieje albo co
kłóci się z tym, jak ten projekt jest zbudowany. Taki błąd wychodzi dopiero
w trakcie implementacji — czyli po tym, jak zapłaciłeś za niego czasem.

Druga rzecz: w wersji pierwszej agent po zebraniu odpowiedzi pokazywał treść
issue i pytał „tworzę?". Odpowiedź inna niż „tak" nie miała zdefiniowanej
ścieżki. W praktyce zawsze chcesz coś podmienić — etykietę, tytuł, zakres — i
potrzebujesz, żeby agent tę podmianę **sprawdził**, a nie przyjął na słowo.

Ta wersja jest więc o dwóch rzeczach: **ocena przed zapisem** i **negocjacja
przed utworzeniem**.

### Czym to nadal NIE jest

- **Nie jest planowaniem implementacji.** Karta issue zawiera skrócony plan
  (3–5 punktów), ale to szkic kierunku, nie projekt. Rozpisanie kroków należy
  do `to-spec` i `to-tickets`.
- **Nie zakłada brancha i nie pisze kodu.** Wyjściem jest issue.
- **Nie jest triage'em cudzych zgłoszeń.** To Twoje pomysły.
- **Nie jest code review.** Agent czyta repo po to, żeby ocenić pomysł, a nie
  żeby oceniać kod, który już tam jest.

---

## Przebieg w całości

```text
Twoj pomysl (jedno zdanie, moze byc mgliste)
   │
   ▼
FAZA 0  rozpoznanie repo          agent czyta, nic nie pyta
   │
   ▼
FAZA 1  ocena sensu               agent mowi wprost: tak / tak, ale / nie
   │                              ← tu temat moze upasc
   ▼
FAZA 2  dopytywanie               tylko o to, czego naprawde brakuje
   │
   ▼
FAZA 3  karta issue               pelny podglad: tytul, body, etykiety, plan
   │
   ▼
FAZA 4  petla akceptacji  ◄──┐    tak / anuluj / zmien
   │                         │
   │  zmiana ────────────────┘    agent weryfikuje zmiane i wraca do FAZY 3
   │
   ├─ tak    ──► gh issue create + dopiecie do projektu
   └─ anuluj ──► nic nie powstaje
```

Do końca FAZY 4 **żadna komenda `gh`, która coś zmienia, nie leci**. W fazach
0–3 agent używa wyłącznie odczytów (`gh issue list`, `gh label list`, `grep`,
`cat`).

---

## `--help` — gdyby to była komenda

```markdown
# /create-task — pomoc

## Co robi
Ocenia pomysl na tle repo, dopytuje o braki, sklada karte issue
(tytul EN, opis PL, etykiety, kryterium ukonczenia, skrocony plan)
i tworzy issue dopiero po Twojej akceptacji. Nie zaklada brancha.

## Wywolanie
/create-task                       Pyta o pomysl od zera
/create-task "eksport CSV"         Zaczyna od tego zdania
/create-task --from-chat           Bierze temat z biezacej rozmowy
/create-task --split               Jeden pomysl rozbija na kilka issue
/create-task --dry-run             Konczy na karcie, nie tworzy niczego
/create-task --no-assign           Nie przypisuje @me (backlog)
/create-task --parent #88          Tworzy jako sub-issue pod #88
/create-task --quick               Pomija FAZE 1, zaklada ze pomysl jest ok

## Wyjscie
Numer issue + link. Przy --dry-run lub anulowaniu: sama karta.
```

| Wywołanie | Kiedy tego używasz |
| --- | --- |
| `/create-task` | Masz pomysł i chcesz wiedzieć, czy w ogóle warto |
| `/create-task "…"` | Masz jedno zdanie, chcesz z niego zrobić zadanie |
| `/create-task --from-chat` | Rozmawialiście o czymś i wyszedł konkret |
| `/create-task --split` | Pomysł jest za duży na jedno issue |
| `/create-task --dry-run` | Chcesz zobaczyć kartę, nic nie tworząc |
| `/create-task --no-assign` | Zapisujesz na kiedyś |
| `/create-task --parent #88` | Pomysł jest częścią większej rzeczy |
| `/create-task --quick` | Ocenę już masz z głowy, chcesz tylko zapisać |

**Flag `--label`, `--title`, `--body` nadal nie ma.** Etykietę i tytuł zmieniasz
w FAZIE 4, gdzie agent może je sprawdzić. Podanie ich z góry omijałoby
weryfikację, a to jedyny powód, dla którego ta komenda w ogóle istnieje.

---

## FAZA 0 — rozpoznanie repo

Zanim agent cokolwiek powie, czyta. Nie pyta Cię o nic, czego może się
dowiedzieć sam. To jest cała różnica między „ocenia pomysł" a „udaje, że
ocenia".

Zakres odczytu, w tej kolejności, z twardym limitem:

| Co | Po co | Komenda |
| --- | --- | --- |
| Konwencje repo | Czy pomysł nie łamie ustalonych zasad | `cat CLAUDE.md`, `ls docs/` |
| Istniejące issue | Czy to już zgłoszone | `gh issue list --state all --search "<slowa kluczowe>" --limit 20` |
| Istniejące etykiety | Żeby nie wymyślać nieistniejących | `gh label list --limit 50` |
| Kod dotykany przez pomysł | Czy to już istnieje, czy jest gdzie to wpiąć | `grep -r`, `ls` po katalogach |
| Świeże commity | Czy ktoś tego właśnie nie robi | `git log --oneline -20` |

**Limit: pięć odczytów, żadnego czytania plików w całości poza `CLAUDE.md`.**
Bez limitu ta faza zjada kontekst i kończy się tym, że agent zna repo, ale nie
ma już miejsca na rozmowę. Jeśli po pięciu odczytach nadal nie wie, gdzie
pomysł by wylądował — to jest informacja sama w sobie i ląduje w ocenie jako
„nie wiem, gdzie to wpiąć".

Agent **nie mówi**, co przeczytał, linijka po linijce. Streszcza w jednym
zdaniu i przechodzi dalej.

---

## FAZA 1 — ocena sensu

Agent wydaje **jeden z pięciu werdyktów**. Zawsze wprost, zawsze w pierwszym
zdaniu, przed uzasadnieniem.

| Werdykt | Co znaczy | Co się dzieje dalej |
| --- | --- | --- |
| **Ma sens** | Pomysł pasuje, nie ma go, jest wykonalny | FAZA 2 |
| **Ma sens, ale** | Pasuje, ale coś trzeba przestawić | FAZA 2, uwagi w karcie |
| **Już istnieje** | To jest zrobione albo zgłoszone | Link, pytanie czy mimo to |
| **Nie w tej formie** | Cel dobry, ujęcie złe | Propozycja innego ujęcia |
| **Nie w tym projekcie** | To nie należy tutaj | Uzasadnienie, koniec |

Werdykt „nie" musi być **realną możliwością**, inaczej cała faza jest teatrem.
Agent, który zawsze mówi „świetny pomysł", nie ma po co czytać repo.

### Na czym agent opiera werdykt

Cztery pytania, które zadaje **sobie**, nie Tobie:

1. **Czy to już jest?** Kod, issue, PR, zamknięte zgłoszenie sprzed pół roku.
   Duplikat zamkniętego issue z etykietą `wontfix` to najważniejsze
   znalezisko — ktoś już raz zdecydował, że tego nie robimy.
2. **Czy da się to wpiąć?** Jest miejsce w strukturze, czy pomysł wymaga
   nowego bytu, o którym nikt nie mówił?
3. **Czy to nie kłóci się z zasadami repo?** `CLAUDE.md` i `docs/` opisują, jak
   ten projekt jest robiony. Pomysł sprzeczny z tym nie jest zły — ale musi to
   powiedzieć wprost, bo to zmiana zasady, nie zadanie.
4. **Czy to jedno issue?** Skala. Trzy niezależne rzeczy złączone „i" to trzy
   zadania.

### Uwagi agenta — format

Uwagi idą jako lista, każda w jednej linii, każda z konsekwencją. Bez
zmiękczania.

```text
Werdykt: ma sens, ale.

- W repo nie ma warstwy eksportu; to bylby pierwszy taki endpoint,
  wiec issue zaklada rowniez ustalenie wzorca dla nastepnych.
- Zamkniete #64 "Eksport do XLSX" ma etykiete wontfix z powodem
  "za duzo zaleznosci". CSV tego powodu nie ma, ale warto wiedziec.
- Twoje sformulowanie "eksport danych" obejmuje trzy listy w aplikacji.
  Proponuje zawezic do zamowien, reszte jako osobne issue pozniej.

Idziemy dalej czy odpuszczamy?
```

Ostatnie pytanie jest obowiązkowe. Po uwagach zawsze masz wyjście — temat może
upaść **tutaj**, zanim ktokolwiek napisze zdanie do issue.

### Dopytywanie

Agent pyta **tylko o to, czego nie wyczytał z repo**. To odwrócenie wersji
pierwszej: tam pytania były stałe, tu są resztą po odjęciu tego, co już wie.

W praktyce zostają zwykle dwa:

- **Co ma być prawdą, gdy to będzie skończone?** — jeśli Twoje zdanie było
  czasownikiem („poprawić", „ogarnąć"), a nie stanem.
- **Czego nie jesteś pewien?** — jedna niewiadoma, trafia do issue jako
  `Otwarte pytanie`.

Zakres, warstwy i etykietę agent **proponuje sam** z tego, co przeczytał, i
pokazuje w karcie. Poprawiasz w FAZIE 4, jeśli trafił źle.

**Limit: cztery pytania.** Piąte oznacza, że pomysł nie jest gotowy na issue —
wtedy agent mówi to wprost i odsyła do `grill-with-docs`.

---

## FAZA 3 — karta issue

Karta jest **pełnym podglądem tego, co się wydarzy**: nie tylko treść, ale też
każde pole, które agent ustawi w GitHubie. Zasada: nic, co nie jest na karcie,
nie zostanie ustawione.

```text
╭─ KARTA ISSUE ────────────────────────────────────────────────╮

Tytul      Add CSV export to orders list
Etykieta   type: feature                        [istnieje w repo]
Assignee   @me
Projekt    4 (radthenone) — kolumna Todo
Rodzic     brak
Blokuje    brak

──────────────────────── TRESC ────────────────────────────────

## Co ma dzialac

Uzytkownik na liscie zamowien klika "Eksportuj" i dostaje plik CSV
zawierajacy dokladnie te kolumny, ktore ma wlaczone w widoku.

## Zakres

- backend: nowy endpoint eksportu na istniejacym viewsecie zamowien
- frontend: przycisk na liscie + pobranie pliku

Poza zakresem: XLSX, eksport w tle przez Celery, harmonogramy,
eksport z innych list niz zamowienia.

## Kryterium ukonczenia

Recznie: filtruje liste, klikam Eksportuj, otwarty plik ma te same
wiersze i te same kolumny co ekran.
Automatycznie: test endpointu sprawdza naglowek Content-Type
i zgodnosc kolumn z parametrem zapytania.

## Plan skrocony

1. Endpoint eksportu obok istniejacego widoku listy zamowien.
2. Serializacja kolumn wedlug parametru z zapytania.
3. Przycisk na froncie + obsluga pobrania pliku.
4. Test endpointu na naglowek i zgodnosc kolumn.

To szkic kierunku, nie specyfikacja. Szczegoly ustala sie przy robocie.

## Otwarte pytanie

Czy eksport ma respektowac paginacje (tylko biezaca strona), czy zawsze
caly wynik filtra? Domyslnie zakladam caly wynik filtra.

## Kontekst

Wyszlo z rozmowy o raportowaniu 2026-09-02. Pierwszy endpoint eksportu
w tym repo — wzorzec ustalony tutaj bedzie kopiowany dalej.
Powiazane: #64 (XLSX, zamkniete jako wontfix).

╰──────────────────────────────────────────────────────────────╯

[t] tworze   [a] anuluj   albo napisz, co zmienic
```

### Sekcje treści i po co która jest

| Sekcja | Po co jest |
| --- | --- |
| **Co ma działać** | Zdanie, które przetrwa miesiąc leżenia w backlogu |
| **Zakres** | Razem z „poza zakresem" — ta druga połowa powstrzymuje rozjazd |
| **Kryterium ukończenia** | Bez tego nie da się zamknąć issue bez kłótni z sobą |
| **Plan skrócony** | 3–5 punktów; mówi, że wiadomo **jak**, nie tylko **co** |
| **Otwarte pytanie** | Mówi wykonawcy, gdzie ma przystanąć zamiast zgadywać |
| **Kontekst** | Skąd się to wzięło + co agent znalazł w repo |

**Napięcie do rozstrzygnięcia:** wersja pierwsza świadomie nie miała planu —
„od tego jest `to-spec`". Tu jest, bo bez niego nie widać, czy agent naprawdę
zrozumiał, gdzie to wpiąć. Ryzyko: plan zestarzeje się szybciej niż reszta
issue i za miesiąc będzie mylił. Dlatego stoi przy nim zdanie o szkicu, a limit
to pięć punktów. Jeśli po kilku prawdziwych zadaniach okaże się, że plan zawsze
odpada przy implementacji — wyleć go i wróć do wersji pierwszej.

---

## FAZA 4 — pętla akceptacji

Trzy wyjścia i tylko jedno kończy się utworzeniem issue.

### `t` — tworzę

Dopiero tutaj lecą komendy zapisujące, w tej kolejności, i agent raportuje
każdą:

```bash
gh issue create \
  --title "Add CSV export to orders list" \
  --label "type: feature" \
  --assignee @me \
  --body-file - <<'BODY'
...tresc z karty...
BODY

gh project item-add 4 --owner radthenone --url <link-do-issue>

# tylko przy --parent
gh api --method POST \
  repos/radthenone/ai-instruction-kit-mcp/issues/88/sub_issues \
  -F sub_issue_id=<db-id-nowego-issue>
```

Jeśli którakolwiek po pierwszej padnie — agent mówi, że **issue już istnieje**,
podaje numer i co się nie udało dopiąć. Nie zaczyna od zera i nie tworzy
drugiego.

Nie zakłada brancha. Branch powstaje, gdy siadasz do roboty: `/git-start #N`.

### `a` — anuluj

Temat upada. Nic nie powstaje. Agent **nie** próbuje ratować pomysłu ani pytać
„na pewno?".

Jedyne, co proponuje: zapis karty do `.scratch/` jako pliku, jeśli chcesz
wrócić. Też tylko za zgodą — anulowanie ma być tanie, a nie zamieniać się
w drugą decyzję.

### Cokolwiek innego — zmiana

Piszesz zwykłym zdaniem, co ma być inaczej. Agent **weryfikuje zmianę, zanim
ją przyjmie**, i wraca do FAZY 3 z nową kartą i jedną linijką o tym, co
zmienił.

To jest sedno tej wersji: zmiana nie jest przyjmowana na słowo.

| Zmieniasz | Co agent sprawdza |
| --- | --- |
| Etykietę | Czy taka istnieje (`gh label list`); czy pasuje do treści |
| Tytuł | Czy po angielsku, czy opisuje stan a nie czynność |
| Zakres | Czy „poza zakresem" nadal się zgadza; czy to nie robi się dwoma issue |
| Kryterium | Czy da się je sprawdzić bez pytania Ciebie |
| Assignee | Czy user ma dostęp do repo |
| Projekt | Czy projekt i kolumna istnieją |
| Rodzica | Czy issue istnieje i jest otwarte |
| Plan | Czy nadal mieści się w pięciu punktach |

### Weryfikacja etykiety — trzy przypadki

Etykieta jest najczęstszą zmianą, więc ma rozpisane zachowanie.

**1. Istnieje i pasuje** — agent podmienia i mówi jednym zdaniem:

```text
> daj type: refactor zamiast feature

Zmienione. type: refactor istnieje. Uwaga: refactor znaczy "bez zmiany
zachowania", a opis mowi o nowym przycisku dla uzytkownika. Zostawiam
Twoj wybor, ale tytul zmienilem na "Refactor export layer" — powiedz,
jesli chodzilo o cos innego.
```

**2. Istnieje, ale nie pasuje** — agent podmienia i **mówi, dlaczego to
podejrzane**. Nie blokuje. To Twoje repo.

**3. Nie istnieje** — agent nie zmyśla i nie tworzy po cichu:

```text
> dodaj etykiete ready-for-agent

Takiej etykiety nie ma w repo. Istnieja tylko: type: * (9 sztuk),
duplicate, invalid, question, wontfix.

docs/agents/triage-labels.md ja opisuje, ale nigdy nie zostala
utworzona. Moge utworzyc:

  gh label create ready-for-agent \
    --description "W pelni opisane, gotowe dla agenta AFK" --color 0E8A16

Tworze etykiete czy pomijam?
```

**Tworzenie etykiety to osobna zgoda.** Etykieta jest bytem repo, nie polem
issue — powstaje raz i zostaje dla wszystkich przyszłych zgłoszeń.

### Zmiana, która wywraca ocenę

Jeśli Twoja zmiana rozszerza zakres na tyle, że werdykt z FAZY 1 przestaje
obowiązywać, agent mówi o tym, zanim pokaże kartę:

```text
> dorzuc jeszcze eksport z listy faktur i z listy klientow

To wywraca ocene. Jedno cienkie zadanie robi sie trzema wertykalnymi
plasterkami — kazdy da sie zamknac osobno, zaden nie zalezy od reszty.
Podzielic na trzy issue (jak --split) czy zostawic jedno duze?
```

Bez tego pętla akceptacji staje się drogą do przemycenia zadania, którego agent
nigdy nie ocenił.

### Ile razy można kręcić

Bez limitu, ale przy **czwartym** obrocie agent to zauważa:

```text
Czwarta zmiana. Zwykle znaczy to, ze nie zgadzamy sie co do samego
pomyslu, a nie co do jego zapisu. Chcesz cofnac do FAZY 1 i ustalic
zakres od nowa?
```

---

## `--split` — kiedy jeden pomysł to nie jedno zadanie

Bez zmian względem wersji pierwszej, z jednym dodatkiem: propozycja podziału
pada w **FAZIE 1**, jako część oceny, a nie dopiero przy karcie.

Podział idzie **po pionie, nie po warstwach**:

```text
ZLE (po warstwach)              DOBRZE (po pionie)
#101 backend eksportu           #101 eksport CSV: lista zamowien
#102 frontend eksportu          #102 eksport CSV: lista faktur
```

`#101 backend` bez `#102` nie daje działającej funkcji, więc nie da się go
samodzielnie zamknąć ani zweryfikować. Przy podziale pionowym każde issue jest
cienkim, ale kompletnym plasterkiem.

Wyjątek, w którym podział po warstwach jest poprawny: kontrakt API musi
istnieć wcześniej, bo frontend nie ma czego konsumować. Wtedy dwa issue i jawna
krawędź blokująca:

```bash
gh api --method POST \
  repos/radthenone/ai-instruction-kit-mcp/issues/102/dependencies/blocked_by \
  -F issue_id=$(gh api repos/radthenone/ai-instruction-kit-mcp/issues/101 --jq .id)
```

`issue_id` to **numeryczne db id**, nie `#numer`.

Przy `--split` karta jest jedna na issue i akceptujesz je **pojedynczo**.
Zbiorcze „tak" na trzy karty naraz oznacza, że przeczytałeś jedną.

---

## Etykiety — stan faktyczny repo

Sprawdzone `gh label list`, stan na 2026-09-02:

```text
type: feature      Nowa funkcjonalnosc widoczna dla uzytkownika
type: fix          Poprawka bledu w kodzie
type: refactor     Zmiana kodu bez zmiany zachowania aplikacji
type: performance  Optymalizacja szybkosci, pamieci lub zapytan
type: security     Luka bezpieczenstwa lub podatnosc
type: test         Dodanie lub naprawa testow jednostkowych/e2e
type: docs         Zmiany wylacznie w dokumentacji
type: chore        Zaleznosci, konfiguracja, narzedzia, CI
type: style        Formatowanie, bez zmiany logiki

duplicate  invalid  question  wontfix
```

Agent wybiera **jedną** `type: *`. Etykieta idzie w parze z typem commita
i przedrostkiem brancha — `type: feature` oznacza `feat/N-slug` i commity
`feat:`. To jedyny powód, dla którego skill w ogóle wybiera etykietę: żeby
reszta przebiegu się nie rozjeżdżała.

**Etykiet triage nadal nie ma.** `docs/agents/triage-labels.md` opisuje
`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human` — w GitHubie
nie istnieje żadna z nich. Dopóki ich nie utworzysz, `gh issue list --label
ready-for-agent` zwraca zero.

```bash
gh label create needs-triage    --description "Do oceny przez maintainera" --color FBCA04
gh label create needs-info      --description "Czekamy na informacje od zglaszajacego" --color D876E3
gh label create ready-for-agent --description "W pelni opisane, gotowe dla agenta AFK" --color 0E8A16
gh label create ready-for-human --description "Wymaga czlowieka" --color 0052CC
```

---

## Przykład — cała rozmowa, z odrzuceniem po drodze

```text
> /create-task "chcialbym miec eksport danych z listy"

Czytam repo... (5 odczytow: CLAUDE.md, issue, etykiety, struktura, log)

Werdykt: ma sens, ale.

- "Eksport danych z listy" obejmuje trzy listy w aplikacji. Proponuje
  zawezic do zamowien; reszta jako osobne issue, gdy ta zadziala.
- W repo nie ma zadnej warstwy eksportu. To bedzie pierwszy taki
  endpoint, wiec zadanie ustala wzorzec dla nastepnych — warto o tym
  wiedziec, bo podnosi wage recenzji.
- Zamkniete #64 "Eksport do XLSX" ma wontfix z powodem "za duzo
  zaleznosci". CSV tego powodu nie ma.

Idziemy dalej czy odpuszczamy?

> dalej, zamowienia, CSV

Po czym poznasz, ze gotowe?

> ze plik ma te kolumny co widze na ekranie

Mam. Czego nie jestes pewien?

> paginacji — caly filtr czy tylko strona

Zapisuje jako otwarte pytanie z zalozeniem "caly wynik filtra".

╭─ KARTA ISSUE ──────────────────────────────────────────────╮
[pelna karta jak wyzej]
╰────────────────────────────────────────────────────────────╯

[t] tworze   [a] anuluj   albo napisz, co zmienic

> zmien etykiete na chore

Zmienione, type: chore istnieje. Uwaga: chore to zaleznosci, config
i CI. Opis mowi o przycisku widocznym dla uzytkownika, co jest
podrecznikowym type: feature. Zostawiam Twoj wybor.

╭─ KARTA ISSUE ──────────────────────────────────────────────╮
Etykieta   type: chore                      [istnieje w repo]
[reszta bez zmian]
╰────────────────────────────────────────────────────────────╯

> nie, jednak feature, i wywal punkt 4 z planu

Etykieta z powrotem type: feature. Punkt 4 usuniety z planu — ale
kryterium ukonczenia dalej wymaga testu endpointu. Zostawiam
kryterium, bo bez niego nie ma jak zamknac issue.

╭─ KARTA ISSUE ──────────────────────────────────────────────╮
[karta z 3-punktowym planem]
╰────────────────────────────────────────────────────────────╯

> t

#127 utworzone.
https://github.com/radthenone/ai-instruction-kit-mcp/issues/127
Dopiete do projektu 4, kolumna Todo.

Gdy siadziesz: /git-start 127
```

---

## Gdzie to siedzi w całości

```text
pomysl
  │
  ├─ /create-task ──► ocena ──┬─ odrzucone ──► koniec, nic nie powstaje
  │                           │
  │                           └─ issue #127
  │                                │
  │                                └─ siadasz sam ──► /git-start 127
  │                                                   → start-feat od kroku 5
  │
  └─ pomysl za duzy ──► grill-with-docs
                        (wracasz z 3-4 zadaniami, kazde przez
                         /create-task osobno)
```

Granica jest ostra: **`/create-task` kończy się na issue albo na jego braku.**

---

## Pułapki

1. **Ocena jako teatr.** Jeśli agent nigdy nie mówi „nie", FAZA 1 tylko kosztuje
   tokeny i daje fałszywe poczucie sprawdzenia. Przy pierwszych zadaniach
   patrz, czy werdykt bywa inny niż „ma sens".

2. **Ocena bez czytania.** Agent, który wydaje werdykt na podstawie samej nazwy
   pomysłu, brzmi tak samo pewnie jak ten, który przeczytał repo. Karta ma
   w `Kontekst` odwoływać się do **konkretów** — numeru issue, ścieżki, commita.
   Ogólniki tam („pasuje do architektury projektu") to sygnał, że nie czytał.

3. **Pętla akceptacji jako obejście oceny.** Dokładanie zakresu po kolejnej
   zmianie omija werdykt. Stąd reguła o wywróconej ocenie — pilnuj, żeby
   działała.

4. **Plan, który udaje specyfikację.** Pięć punktów to sufit. Plan na
   piętnaście kroków znaczy, że to zadanie jest za duże albo że robisz `to-spec`
   w złym miejscu.

5. **`ready-for-agent` na kredyt.** Etykieta znaczy „w pełni opisane". Zadanie
   z otwartym pytaniem, które naprawdę trzeba rozstrzygnąć, nie jest gotowe dla
   agenta — nocna sesja utknie i przepali budżet na czekaniu.

6. **Tworzenie zadań szybciej, niż je zamykasz.** Ocena trochę spowalnia, ale
   nie na tyle, żeby to naprawić. Backlog, którego nikt nie przegląda, jest
   gorszy niż jego brak, bo udaje plan.

7. **Podział po warstwach z przyzwyczajenia.** „Backend osobno, front osobno"
   wygląda porządnie i prawie zawsze jest błędem.

---

## Czego ten skill nie zrobi

- **Nie oszacuje czasu.** Nie zna Twojego tygodnia.
- **Nie ustali priorytetu.** Kolejność wynika z tego, co blokuje co, a to widać
  dopiero na mapie, nie przy pojedynczym pomyśle.
- **Nie wyłapie duplikatu „tym samym innymi słowami".** `gh issue list --search`
  znajduje słowa, nie znaczenia.
- **Nie napisze specyfikacji.** Issue to akapit, kryterium i szkic planu.
- **Nie zastąpi rozmowy przy naprawdę trudnym pomyśle.** Ocena po pięciu
  odczytach jest oceną po pięciu odczytach.
- **Nie oceni jakości kodu, który zastanie.** Czyta repo, żeby zrozumieć
  pomysł, nie żeby recenzować.

---

## Czy warto to budować

**Za:** największa wartość nie jest w utworzeniu issue (`gh` to potrafi), tylko
w dwóch rzeczach, których ręcznie nigdy nie robisz: **sprawdzeniu, czy to już
istnieje**, i **wymuszeniu kryterium ukończenia**. Pętla akceptacji z
weryfikacją etykiet dokłada trzecią: nigdy nie utworzysz issue z etykietą,
której nie ma.

**Przeciw:** FAZA 0 kosztuje pięć odczytów przy każdym pomyśle, także przy
takim, o którym z góry wiesz, że jest dobry — stąd `--quick`. I dopóki nie
sprawdzisz na kilku prawdziwych pomysłach, czy werdykt bywa negatywny, nie
wiesz, czy ocena cokolwiek wnosi.

**Propozycja:** zrób najbliższe trzy zadania ręcznie tą procedurą, w tym
jedno, o którym podejrzewasz, że jest złym pomysłem. Sprawdzasz dwie rzeczy:
czy agent to wyłapał i czy karta wymagała więcej niż dwóch obrotów pętli. Jeśli
oba wychodzą dobrze — zapisz jako skill.

---

## Do przemyślenia

- **Ile odczytów w FAZIE 0.** Pięć to zgadywanka. Za mało, żeby ocenić duży
  pomysł; za dużo przy oczywistym. Może zależnie od tego, czy podałeś pomysł
  jednym zdaniem, czy akapitem.
- **Czy `--quick` nie zje całej wartości.** Jeśli po tygodniu używasz wyłącznie
  `--quick`, ocena nie była potrzebna i lepiej wrócić do wersji pierwszej.
- **`--from-chat` nadal najtrudniejsza flaga:** agent musi sam zdecydować,
  **który** wątek rozmowy jest zadaniem.
- **Błędy potrzebują innych pytań** (repro, oczekiwane vs faktyczne,
  środowisko) — patrz [start-fix.md](start-fix.md). Prawdopodobnie osobna
  komenda, nie flaga.
- **Czy karta powinna pokazywać, co agent przeczytał.** Pełna lista buduje
  zaufanie do werdyktu, ale zaśmieca podgląd. Może tylko przy `--dry-run`.
