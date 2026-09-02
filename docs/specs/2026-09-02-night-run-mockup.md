# `/night-run` — zlecanie pracy na czas Twojej nieobecności

> **Czym jest ten dokument.** Makietą skilla, którego **jeszcze nie ma**.
> Opisuje, jak wyglądałaby rozmowa `/night-run` i co dokładnie by z niej
> wyszło — żebyś mógł ocenić, czy warto to zamieniać w prawdziwy skill,
> zanim ktokolwiek go napisze.
>
> Dopóki skilla nie ma, ten dokument da się wykonać ręcznie: to po prostu
> procedura. Wklejasz jej fragmenty do rozmowy i dochodzisz do tego samego
> pliku zlecenia.
>
> Mechanika pod spodem (`/goal`, `/loop`, worktree, `/batch`, `/schedule`):
> [loop-and-goal.md](loop-and-goal.md). Skille, które robią właściwą robotę:
> [matt-instruction.md](matt-instruction.md).

---

## `--help` — gdyby to była komenda

Tak wyglądałby `/night-run --help`. Ta sekcja jest jednocześnie specyfikacją
interfejsu: jeśli skill powstanie, ma przyjmować dokładnie to.

```markdown
# /night-run — pomoc

## Co robi
Ustala zlecenie pracy na czas Twojej nieobecnosci i zapisuje je do
docs/plans/night/YYYY-MM-DD-<slug>.md. Po Twojej akceptacji zaklada worktree,
ustawia /goal i /loop, odpala. Nic nie dotyka repo przed akceptacja.

## Wywolania
| Komenda | Efekt |
|---------|-------|
| `/night-run` | Pyta o pomysl i prowadzi do zlecenia od zera |
| `/night-run #88` | Czyta issue #88, dopytuje o braki |
| `/night-run #88 #91 #94` | Kolejka z trzech issue |
| `/night-run <url-issue>` | To samo co numer |
| `/night-run --label ready-for-agent` | Bierze wszystkie issue z etykieta |
| `/night-run --dry-run` | Pokazuje zlecenie, nie zapisuje i nie odpala |
| `/night-run --plan <sciezka>` | Odpala gotowe zlecenie bez rozmowy |
| `/night-run --status` | Co dziala teraz: worktree, branche, aktywny /goal |
| `/night-run --stop` | Zdejmuje /loop i /goal, zostawia branche nietkniete |
| `/night-run --help` | Ta pomoc |

## Czego nie robi
- Nie tworzy issue (to osobna robota — patrz "Wejscie, dwa warianty")
- Nie mergeuje i nie pushuje na chronione branche
- Nie odpala niczego przed Twoim "akceptuje"
- Nie sprzata worktree — to robisz rano

## Trzy wyjscia z rozmowy
akceptuje → zapis + worktree + start
zmien X   → poprawka i PYTANIE PONOWNIE, nie cichy start
anuluj    → nic nie powstaje

## Recznie, bez skilla
gh issue view 88
git worktree add ../wt-88 -b feat/88-coupon-model master
/goal <komenda konczaca sie kodem 0>
/loop 45m kontynuuj wedlug docs/plans/night/2026-09-02-kupony.md
```

---

## Problem

Wychodzisz od komputera. Śpisz, jesteś w pracy, jedziesz gdzieś. Limit tokenów
się odnawia i przepada, jeśli nikt go nie zużyje. Agent mógłby w tym czasie
pracować — ale w połowie zadania zapyta „czy mam dodać zależność?" i będzie stał
do rana.

Kliknięcie „potwierdź" nie jest jedyną rzeczą, którą dajesz agentowi w ciągu
dnia. Dajesz też cztery inne, i wszystkie musisz dać **tekstem z góry**, jeśli
Cię nie będzie:

| W dzień dajesz przez | Musi być zapisane jako | Bez tego |
|---|---|---|
| „tak, rób" | zgoda z góry (tryb uprawnień) | agent stoi na pierwszym pytaniu |
| „nie, nie to" | lista katalogów, których wolno dotknąć | rano diff na 100 plików |
| „to jeszcze nie jest gotowe" | `/goal` — warunek sprawdzalny komendą | agent ogłasza sukces po 7 minutach |
| „wróć do tego za godzinę" | `/loop` — rytm powrotu | jedna tura i cisza do rana |
| „stój, zapytaj mnie" | lista bramek | agent zgaduje w miejscu, w którym nie powinien |

Ostatni wiersz jest tym, którego zwykle brakuje. Trzy pierwsze mówią agentowi,
co ma robić. Czwarty — kiedy ma wracać. **Piąty mówi, kiedy ma przestać
i poczekać na Ciebie** — i bez niego wszystkie pozostałe nie chronią przed
nocą, w której agent podjął decyzję, której nie miał prawa podjąć.

`/night-run` istnieje po to, żeby zebrać te pięć rzeczy w jednej rozmowie
i zapisać je w jednym pliku.

---

## Dwa artefakty, nie jeden

To rozróżnienie jest sednem. Jeśli je pominiesz, nocna praca zostaje w historii
czatu, a historia czatu umiera razem z sesją.

**Rozmowa** — `/night-run`. Jednorazowa. Ustalamy, co ma się stać.

**Zlecenie** — `docs/plans/night/YYYY-MM-DD-<slug>.md`. Artefakt. Czyta go agent
nocny, nie Ty. Rano czytasz je Ty i porównujesz z tym, co agent faktycznie
zrobił.

Bez pliku nie masz rano z czym porównać PR-ów. „Miało być inaczej" bez
zapisanego „miało być" to nie jest zarzut, tylko wrażenie.

---

## Rozmowa — jak by wyglądała

### Wejście, dwa warianty

**A. Podajesz issue.**

```
/night-run #88
/night-run https://github.com/radthenone/ai-instruction-kit-mcp/issues/88
/night-run --label ready-for-agent
/night-run #88 #91 #94
```

Agent robi `gh issue view` na każdym i sprawdza jedną rzecz: **czy da się z tego
zrobić warunek stopu**. Zwykle nie da się od razu, bo issue mówi „dodaj kupony",
a nie „`uv run pytest tests/coupons -q` kończy się kodem 0". Wtedy dopytuje.

**B. Nie podajesz nic.**

```
/night-run
```

Agent pyta o pomysł i prowadzi do tego samego miejsca. Ale **nie tworzy issue po
drodze** — od tego jest osobna procedura. Jeśli z rozmowy wyjdzie, że issue nie
ma, mówi wprost: najpierw zrób issue, potem wracamy tutaj.

### Pięć rzeczy, których nie odpuszcza

Bez każdej z nich noc jest stracona — nie „gorsza", tylko stracona.

**1. Warunek stopu.** Komenda, która kończy się kodem 0 albo 1. Nie zdanie.

```
✅ uv run pytest tests/coupons -q konczy sie kodem 0
✅ kazde issue z listy ma otwarty PR
❌ kupony maja dzialac
❌ kod ma byc dobrej jakosci
```

Powód, dla którego to jest tak ostre: w nocy nie ma nikogo, kto powie „to
jeszcze nie to". Model, który przeoczył wymaganie przy pisaniu, przeoczy je
również przy samoocenie. Warunek musi dać się rozstrzygnąć **bez sądu**.

**2. Zakres.** Jawna lista katalogów. Nie „backend", tylko `src/coupons/`,
`tests/coupons/`. Wszystko poza listą to bramka (patrz punkt 5), nie zakaz —
agent ma się zatrzymać i zapytać, a nie po cichu ominąć.

**3. Baza.** Z czego odbijamy branche. `master`? `dev`? Zły wybór to nie błąd
w kodzie, tylko konflikt, który rano rozwiązujesz ręcznie zamiast oglądać PR-y.

**4. Budżet.** Ile tur, do której godziny. Limit tokenów jest Twój — agent nie
wie, ile go zostało i ile chcesz zostawić na jutro.

**5. Bramki.** Co ma go zatrzymać i **obudzić Ciebie** zamiast zgadywać.
Domyślna lista, którą warto brać w całości:

- test padał trzy tury z rzędu z tego samego powodu
- trzeba dodać zależność do `pyproject.toml`
- zadanie wymaga decyzji, której nie ma w issue
- zmiana wychodzi poza listę katalogów z punktu 2
- pojawia się cokolwiek z sekretami, migracjami albo CI

### Wyjście z rozmowy — trzy drogi

Agent pokazuje **gotowe zlecenie** i pyta. Trzy odpowiedzi:

| Mówisz | Co się dzieje |
|---|---|
| `akceptuję` | zapisuje plik, tworzy worktree i branche, odpala |
| `zmień X` | poprawia i **pyta ponownie** — nie odpala po cichu po jednej poprawce |
| `anuluj` | nic nie powstaje: żadnego pliku, brancha, worktree |

**Twarda reguła: nic nie dotyka repo przed „akceptuję".** Sam plik zlecenia też
nie. Do tego momentu rozmowa jest tylko rozmową — możesz z niej wyjść bez
sprzątania.

---

## Zlecenie — pełny szablon

```markdown
---
utworzono: 2026-09-02
zakonczyc-do: 2026-09-03 07:00
zrodlo: "#88, #91"
baza: master
status: zaakceptowany
---

# Kupony rabatowe — model i endpoint

## Cel

Rano maja byc dwa PR-y: model kuponu z migracja (#88) i endpoint
POST /api/coupons/apply (#91), oba z zielonymi testami.

## Warunek stopu

    uv run pytest tests/coupons -q

konczy sie kodem 0 ORAZ oba issue maja otwarty PR.

## Worktree

| katalog | branch | issue | zadanie | czeka na |
|---|---|---|---|---|
| ../wt-88 | feat/88-coupon-model | #88 | model + migracja | — |
| ../wt-91 | feat/91-coupon-api | #91 | endpoint + serializer | plik src/coupons/models.py na feat/88 |

## Wolno dotknac

    src/coupons/
    tests/coupons/

## Nie wolno, nigdy

- merge do master
- force push (`git push --force`, `--force-with-lease`)
- `gh label delete`, `gh issue close`
- migracje na produkcji
- pliki poza lista wyzej

## Zatrzymaj sie i czekaj, gdy

- test padal trzy tury z rzedu z tego samego powodu
- trzeba dodac zaleznosc do pyproject.toml
- zadanie wymaga decyzji, ktorej nie ma w issue
- zmiana wychodzi poza `Wolno dotknac`

Zatrzymanie znaczy: dopisz komentarz do issue, zostaw branch jak jest,
przejdz do nastepnego zadania. Nie czekaj bezczynnie.

## Rytm

    /loop 45m
    maks 12 tur

Po ostatniej turze: raport do docs/plans/night/2026-09-02-kupony-raport.md

## Rano do obejrzenia

- PR-y: <dopisze agent>
- raport: docs/plans/night/2026-09-02-kupony-raport.md
- zatrzymania: <dopisze agent, jesli byly>
```

Ten plik jest jednocześnie **promptem dla agenta** i **Twoją listą kontrolną
rano**. Sekcja „Zatrzymaj się i czekaj" jest tą, której nigdzie indziej nie
masz — i to ona odpowiada na pytanie „kiedy przerwać".

Zwróć uwagę na jedno zdanie: **zatrzymanie nie znaczy stania bezczynnie.**
Agent, który utknął na zadaniu 2, ma zostawić komentarz i wziąć zadanie 3.
Inaczej jedna zła decyzja zabiera całą noc, a nie jedno zadanie.

---

## Co agent robi po „akceptuję" — krok po kroku

To jest ta część, którą dziś musisz robić ręcznie i której najbardziej brakuje.

### 1. Zapisuje zlecenie

```bash
git add docs/plans/night/2026-09-02-kupony.md
git commit -m "docs(night): zlecenie na noc 2026-09-02"
```

Commit, nie luźny plik. Rano ma być w historii, także jeśli coś poszło źle.

### 2. Zakłada worktree

Worktree to **osobny katalog roboczy na ten sam repozytorium**. Dwa katalogi,
dwa branche, jedna historia gita, zero przełączania.

```bash
git worktree add ../wt-88 -b feat/88-coupon-model master
git worktree add ../wt-91 -b feat/91-coupon-api  master
```

Po co, skoro `git checkout` też potrafi zmienić branch: bo dwa agenty w jednym
katalogu nadpisują sobie pliki. `git checkout` w trakcie pracy drugiego agenta
to najprostszy sposób na noc, po której nie wiadomo, co jest czyje.

Sprawdzenie, co żyje:

```bash
git worktree list
```

Sprzątanie rano, po zmergowaniu:

```bash
git worktree remove ../wt-88
```

### 3. Ustawia warunek stopu

```
/goal uv run pytest tests/coupons -q konczy sie kodem 0
      ORAZ #88 i #91 maja otwarty PR
```

`/goal` odpowiada na pytanie **kiedy przestać**. Ocenia go **osobny sędzia**, nie
ten sam agent, który pisał kod — to jedyny mechanizm w całym zestawie, w którym
pracę ocenia ktoś inny niż jej autor.

### 4. Ustawia rytm

```
/loop 45m kontynuuj wedlug docs/plans/night/2026-09-02-kupony.md
```

`/loop` odpowiada na pytanie **kiedy wrócić**. To są dwa różne pytania i mylenie
ich jest najczęstszym błędem:

- sam `/loop` → agent budzi się co 45 minut i **za każdym razem ogłasza sukces**
- sam `/goal` → agent dociągnie jedno zadanie i **stanie na dwie godziny przed
  świtem**

Na noc potrzebujesz obu.

### 5. Odpala i milknie

Od tego momentu agent pracuje. Wraca do Ciebie tylko na bramce z sekcji
„Zatrzymaj się i czekaj".

---

## Trzy kształty nocy

Wybór zależy od tego, **jak wygląda robota**, nie od tego, ile jej jest.

### A. Kolejka — zadania nic o sobie nie wiedzą

Cztery issue, każde samodzielne, każde kończy się osobnym PR-em. Nikt na nikogo
nie czeka.

```bash
git worktree add ../wt-88 -b feat/88-coupon-model master
git worktree add ../wt-92 -b feat/92-admin-filter master
git worktree add ../wt-95 -b chore/95-bump-ruff   master
```

Warunek stopu jest zbiorczy:

```
/goal kazde z #88 #92 #95 ma otwarty PR z zielonymi testami
```

To jest domyślny kształt nocy. Najprostszy do zrozumienia i najtrudniejszy do
zepsucia. Jeśli wahasz się między kształtami — weź ten.

### B. Łańcuch — jedno czeka na drugie

Backend musi być przed frontendem, bo frontend generuje klienta z `openapi.json`,
który powstaje dopiero po backendzie.

Kluczowa decyzja: **punktem spotkania jest plik, nie człowiek.** Agent FE nie
czeka na Twoją zgodę — czeka, aż plik pojawi się na branchu BE.

```bash
# worktree BE
git worktree add ../wt-be -b feat/88-coupon-api master

# worktree FE — startuje pusty, czeka
git worktree add ../wt-fe -b feat/89-coupon-client master
```

W zleceniu FE:

```markdown
## Czekaj na

Plik src/api/openapi.json na branchu feat/88-coupon-api,
zawierajacy sciezke /api/coupons/apply.

Sprawdzaj co ture:

    git fetch origin feat/88-coupon-api
    git show origin/feat/88-coupon-api:src/api/openapi.json | grep -q coupons/apply

Dopoki nie ma: nie pisz kodu klienta, zrob to, co da sie zrobic bez
kontraktu (typy domenowe, testy na stalych danych).
```

Ostatnia linijka jest ważna: agent, który czeka, ma **robić coś innego**, a nie
spać. Inaczej płacisz tokeny za pustą pętlę.

### C. Pętla implementacja ↔ review

Jeden kod, dwie role. Worktree A pisze, worktree B recenzuje, A poprawia.

```bash
git worktree add ../wt-impl   -b feat/88-coupon-model master
git worktree add ../wt-review    feat/88-coupon-model   # ten sam branch, tylko do czytania
```

W B, co turę:

```
/code-review master
```

Wynik ląduje w pliku, który czyta A:

```markdown
## Rytm

Runda = A implementuje, B recenzuje do docs/plans/night/review-88.md,
A czyta i poprawia.

Koniec, gdy: review nie ma zadnego znaleziska o wadze wyzszej niz "nit"
ALBO po 4 rundach — cokolwiek nastapi pierwsze.
```

Limit rund jest obowiązkowy. Bez niego dwa agenty potrafią poprawiać sobie
nawzajem to samo aż do rana.

---

## Odpalanie spod telefonu

To zmienia jedną rzecz, i to fundamentalnie: **czy laptop musi żyć.**

| Sposób | Laptop | Kiedy |
|---|---|---|
| `/loop` lokalnie | musi być włączony i online przez całą noc | masz stały prąd i sieć, chcesz pełnego dostępu do repo |
| `/schedule` (chmura) | może być zamknięty | wychodzisz z domu, zabierasz laptopa |
| Remote Control z telefonu | musi być włączony | chcesz w nocy zajrzeć i coś dopowiedzieć |

Praktyczna kolejność: ustalasz zlecenie przy komputerze wieczorem, akceptujesz,
odpalasz `/loop`, i **z telefonu tylko oglądasz** — bramki z sekcji „Zatrzymaj
się i czekaj" pojawią się jako komentarze przy issue, więc widać je w aplikacji
GitHuba bez wchodzenia w terminal.

Ustalanie zlecenia z telefonu jest możliwe, ale nie polecam: rozmowa
`/night-run` ma pięć decyzji, a każda źle podjęta kosztuje całą noc. Pięć
decyzji na telefonie o 23:40 to nie jest dobry pomysł.

---

## Rano

Kolejność, w której warto patrzeć:

1. **Sekcja „zatrzymania" w raporcie** — najpierw to, na czym agent stanął.
   Tam jest informacja, której nie ma nigdzie indziej.
2. **PR-y** — po jednym, normalny review. `/code-review master` jeśli chcesz
   drugą parę oczu.
3. **Diff wobec „Wolno dotknąć"** — czy coś wyszło poza zakres:
   ```bash
   git diff master...feat/88-coupon-model --name-only
   ```
4. **Sprzątanie worktree** po zmergowaniu.

**Czego nie robić rano:** mergować bez czytania, bo „testy przeszły". Testy
przeszły to warunek stopu, a warunek stopu był tak dobry, jak go w nocy
napisałeś.

---

## Czego ten przebieg nie załatwia

Uczciwie, żebyś nie odkrył tego o czwartej nad ranem:

1. **`ready-for-agent` nie istnieje w tym repo.** `--label ready-for-agent`
   zwróci dziś zero issue. Etykiety trzeba raz utworzyć —
   [matt-instruction.md](matt-instruction.md), sekcja o konfiguracji.

2. **Worktree nie izoluje środowiska.** Dwa katalogi to dwa drzewa plików, ale
   jedna baza danych, jeden port, jedno `.venv`, jeden `docker compose`.
   Dwa agenty odpalające ten sam serwer deweloperski będą się bić o port.
   Jeśli zadania dotykają usług, to jest pierwsza rzecz do przemyślenia.

3. **`/goal` ocenia warunek, nie intencję.** Warunek „testy przechodzą" spełni
   też agent, który skasował test. Warto dopisać do „Nie wolno, nigdy": kasowanie
   ani wyłączanie istniejących testów.

4. **Nie ma automatycznego wznowienia po padzie.** Jeśli laptop się uśpi
   o trzeciej, rano zastajesz stan z trzeciej. Zlecenie przetrwa (jest
   zacommitowane), pętla nie.

5. **Zaakceptowane zlecenie się nie aktualizuje.** Jeśli w nocy zmienisz zdanie
   z telefonu, komentarz przy issue nie zmieni pliku, który agent czyta.

---

## Czy warto to robić skillem

**Za:**

- Pięć decyzji, które zawsze są te same, i zawsze łatwo o którejś zapomnieć.
  Skill nie zapomina.
- Trzy wyjścia (`akceptuję` / `zmień` / `anuluj`) to zachowanie, którego
  dokument nie wymusi — może je wymusić tylko instrukcja czytana przez agenta.
- Zakładanie worktree, ustawianie `/goal` i `/loop` to ta sama sekwencja komend
  za każdym razem.

**Przeciw:**

- Póki nie odpalisz tego kilku nocy z rzędu, nie wiesz, których pytań naprawdę
  brakuje. Skill zamrożony za wcześnie utrwala złą listę.
- Zlecenie jest artefaktem tekstowym — da się je napisać bez skilla, kopiując
  szablon z tego dokumentu.

**Rekomendacja:** przejedź tak trzy noce ręcznie, z szablonem z tego dokumentu.
Zapisz przy każdej, co poszło nie tak. Dopiero potem pisz skill — i wtedy będzie
o kilka pytań krótszy niż ten, który napisałbyś dziś.
