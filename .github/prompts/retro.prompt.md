---
mode: "agent"
description: "Klasyfikacja znalezisk z wyniku skanu sesji agentów (`kit-ai retro scan`, zapisy JSONL w ~/.cache/kit-ai/retro/<repo>/) na kategorie kit / projekt / agent / zewnętrzne z oceną. Z flagą `/retro --kit` (w repo kita) klasyfikuje propozycje z agregacji `kit-ai retro report` z wielu repo. Użyj zawsze, gdy użytkownik pisze `/retro`, „retro”, „przejrzyj sesję”, „co poszło źle w sesji”, „sklasyfikuj znaleziska”, „sygnały z guardów”, „co wyszło z nocy”, albo gdy po sesji lub przebiegu headless czeka wynik skanu do oceny — także wtedy, gdy użytkownik nie użyje słowa „retro”. Nie edytuje plików."
---

# Retro — klasyfikacja znalezisk

Czytasz wynik skanu sesji, przypisujesz każde znalezisko do jednej z czterech kategorii i
podajesz ocenę w rozmowie. Wynik to propozycje dla człowieka, a nie poprawki, więc niczego
nie zapisujesz. Terminy (Sesja, Sygnał, Znalezisko, Fingerprint, Propozycja) są z `CONTEXT.md`.

Degradacja: u klientów bez natywnych skilli ten plik działa jako komenda `/retro`. Wykonaj te
same kroki; zasobów do wczytania nie ma.

## Wejście

1. Katalog wyniku: `${XDG_CACHE_HOME:-~/.cache}/kit-ai/retro/<repo>/`. Pliki `<sesja>.jsonl` to
   wyniki skanu. Weź te, które wskazał użytkownik, albo pliki z ostatniego przebiegu nocnego.
   Nie szukaj po całym dysku.
2. Każda linia to JSON. `"type": "session"` niesie metryki sesji (`source`, `files`, `metrics`,
   `scanned_at`, `kit_sha`). `"type": "finding"` to jedno Znalezisko, czyli sygnały o tym samym
   fingerprincie, z polami:
   - `kind` — rodzaj sygnału (tabela niżej),
   - `fingerprint` — klucz deduplikacji,
   - `count` — liczba wystąpień,
   - `guard` i `tool` — gdy dotyczą,
   - `replay` — decyzja **aktualnego** guarda na zapisanym wejściu: `deny`, `allow`, `unknown`
     albo `n/a` (nie dotyczy),
   - `evidence` — dowód po maskowaniu.
3. Zapis sesji czytasz tylko przy oznaczonych miejscach. Weź fragment `evidence` (bez
   zamaskowanych wartości), wyszukaj go w zapisie sesji i przeczytaj
   10–20 wierszy wokół trafienia. Reszty zapisu nie czytasz. Pole `files` to tylko liczba plików;
   zapis wskazuje `session` i `source`: dla `claude` to `~/.claude/projects/<projekt>/<session>.jsonl`
   (plus `<session>/subagents/*.jsonl`), dla `headless` to `.ai/headless-runs/<session>/headless.log`.

`replay=allow` oznacza, że aktualny guard przepuściłby to wejście: odrzucenie pochodzi z
przeszłości. `replay=deny` oznacza, że guard nadal odrzuca je, a ocena zależy od tego, czy
polecenie było zgodne z procedurą.

## Kategorie

Każde Znalezisko dostaje dokładnie jedną kategorię:

- **kit** — procedura, guard, szablon albo skrypt kitu zawodzi albo prowadzi agenta w błąd, np.
  guard odrzuca poprawne polecenie albo reguła procedury jest niejednoznaczna. Poprawka leży w
  kicie (`templates/`, `modules/`, `src/`).
- **projekt** — problem w konfiguracji albo kodzie tego repo, np. brak narzędzia w środowisku,
  błędny overlay, test zależny od lokalnej ścieżki. Poprawka leży w repo projektu.
- **agent** — agent odszedł od procedury, którą miał w kontekście, np. nie wczytał overlay przed
  edycją, zapętlił to samo wywołanie, zignorował hand-back. Poprawka leży w prompcie, skillu albo
  agencie, nie w kodzie.
- **zewnętrzne** — poza kontrolą repo i kitu, np. limit API, przeciążenie usługi, przerwane
  połączenie, blokada harnessu. Poprawki w repo nie ma.

Wskazówki dla rodzajów `kind`. Dowód z zapisu sesji rozstrzyga przy sprzecznościach:

| `kind` | Zwykle | Jak rozstrzygnąć |
| --- | --- | --- |
| `guard_deny` | kit albo agent | `replay=deny` przy poleceniu zgodnym z procedurą → kit (guard za ostry); niezgodnym → agent; `replay=allow` → kit, prawdopodobnie już naprawione |
| `mcp_compliance` | agent | edycja kodu bez wcześniejszego `get_overlay`; sprawdź, czy procedura w kontekście to wymagała |
| `repeated_tool_use` | agent | to samo wywołanie co najmniej 3 razy; gdy wynik się zmieniał → agent; gdy narzędzie zwraca stale błąd → projekt albo zewnętrzne |
| `questioning_tool` | agent | wywołanie narzędzia pytającego człowieka (np. `confirm_repository_trust`, `AskFollowupQuestion`); w trybie autonomicznym niedozwolone |
| `tool_error` | projekt albo zewnętrzne | błąd ścieżki, zależności albo konfiguracji → projekt; błąd sieci lub usługi → zewnętrzne |
| `api_error` | zewnętrzne | limit, przeciążenie, błąd po stronie dostawcy |
| `harness_block` | zewnętrzne | blokada harnessu, nie guard kitu |
| `headless_exit` | zależnie od przyczyny | ostatnie wiersze `headless.log` podają przyczynę; kod wyjścia bez przyczyny → kit, pewność niska |
| `headless_no_change` | agent | kod 0 i czyste drzewo po przebiegu: zadanie niewykonane |

## Ocena

Jedna tabela, jeden wiersz na Znalezisko, bez wstępu:

| Kategoria | Znalezisko | Ocena | Pewność |
| --- | --- | --- | --- |
| **kit** | `guard_deny` · `<fingerprint>` · ×3 | Guard odrzuca polecenie, które procedura dopuszcza; `replay=deny`, zapis sesji potwierdza zgodność. | wysoka |

Pewność:
- `wysoka` — dowód z zapisu sesji i `replay` zgadzają się;
- `niska` — brak zapisu do sprawdzenia albo `replay=unknown`. Napisz „do potwierdzenia”, nie
  stwierdzaj faktu.

Na końcu jedna linia podsumowania:
`Retro: <N> znalezisk — kit <n> · projekt <n> · agent <n> · zewnętrzne <n>.`
Gdy wynik skanu nie ma Znalezisk, podajesz tylko `Retro: 0 znalezisk.`

## Tryb `--kit`

`/retro --kit` uruchamiasz w repo kita. Zamiast jednego skanu czytasz agregację z wielu repo:

1. Uruchom `kit-ai retro report` w repo kita. Komenda czyta zapisy z cache każdego repo, grupuje
   znaleziska po `fingerprint`, stosuje progi (co najmniej 3 sesje albo 2 repo) i pomija te,
   których marker `<!-- retro-fingerprint: … -->` jest już w issue, otwartym albo zamkniętym
   (ADR-0017). Zamknięte issue, także odrzucone, wycisza propozycję na stałe.
2. Każdą propozycję klasyfikujesz jak w sekcji Kategorie. Dowód bierz z `evidence`, `replay`
   i `kit` (commit kita z chwili skanu). Przy sprzeczności czytasz zapis sesji jak w punkcie 3
   z Wejścia. Starszy `kit` przy `replay=deny` oznacza, że problem mógł już zniknąć: „do
   potwierdzenia”.
3. Propozycje robisz tylko dla `kit` i `agent`, z trasą `/create-task` w repo kita. Marker
   z raportu idzie do karty, żeby kolejny raport tę propozycję pominął. `projekt` nie dostaje
   propozycji, bo `/kit-project-edit` nie zakłada issue i marker nie miałby gdzie trafić.
   Zamiast tego jedna linijka na repo: „<N> znalezisk projektowych, uruchom `/retro` w repo <repo>”.
   `zewnętrzne` → bez karty i bez linijki.
4. Wynik: jedna tabela z kolumnami Kategoria, Fingerprint, Sesje, Repo, Trasa karty, Ocena,
   Pewność, pod nią linijki odesłania dla `projekt`.

Propozycje to tylko propozycje: karty tworzy człowiek przez `/create-task` po akceptacji.
Zmianę w projekcie robi `/kit-project-edit` po lokalnym `/retro` w tym repo.

## Zasady

- Nie edytuje plików: ani kodu, ani konfiguracji, ani wyniku skanu. Nie czyścisz katalogu cache.
- Skill nie zakłada issue i nie pisze w GitHubie. Każda poprawka to Propozycja, którą człowiek
  akceptuje przed jakimkolwiek zapisem (karty robi `/create-task` albo `/kit-project-edit`;
  w trybie `--kit` tylko `/create-task`).
  Jedynym kontaktem z GitHubem jest odczyt issue (w każdym stanie) przez `kit-ai retro report`
  w trybie `--kit`.
- Dane zamaskowane zostają zamaskowane. Nie odtwarzaj sekretów, adresów e-mail ani ścieżek
  domowych, nawet gdy je widzisz w zapisie sesji.
- Nie wysyłasz treści sesji na zewnątrz: bez zapytań sieciowych i bez wklejania fragmentów do
  issue czy komentarzy.
- Znalezisko bez pewności to pytanie, nie fakt (AGENTS.md). Przy `replay=unknown` i braku
  dowodu pisz „do potwierdzenia”.
