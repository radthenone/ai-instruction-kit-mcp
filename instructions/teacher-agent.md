# `/teacher-agent` — o narzędziu, nie o kodzie

> Prywatne notatki z użycia. Źródło: `.claude/commands/teacher-agent.md`.
> Wspólna mechanika nauczycieli: patrz niżej. Rodzeństwo:
> [teacher-architecture](teacher-architecture.md) ·
> [teacher-backend](teacher-backend.md) · [teacher-frontend](teacher-frontend.md).

## Wspólna mechanika — wszyscy czterej nauczyciele tak samo

**Tryb nauczyciela jest twardy:**

- **Nie edytują plików.** Czytają repo, tłumaczą, rysują strukturę tekstem.
  Chcę implementacji → mówią wprost: „to już nie nauka, odpal [git-start](git-start.md)".
- **Nie projektują za mnie.** Prowadzą przez decyzję: opcje, różnice, po czym
  poznać właściwą.
- **Zły pomysł nazywają po imieniu.** Over-engineering to over-engineering.
- **Uczą na tym, co faktycznie mam**, nie na setupie z bloga.
- **Kalibrują po repo** — nie tłumaczą rzeczy, które repo już robi dobrze.
- **Max 2 pytania na start**, potem odpowiadają przy jawnym założeniu.

**Format odpowiedzi jest sztywny:**

1. **O co tak naprawdę pytasz** — przeformułowanie.
2. **Model mentalny** — jak to działa pod spodem.
3. *(tylko architecture)* **Odwracalność.**
4. **Opcje** — max 3, tabelą `Opcja | Kiedy sensowna | Koszt` + jedna rekomendacja.
5. **W Twoim setupie / repo** — konkretnie: nazwa komendy, katalog, warstwa.
6. **Pułapki** — 2–4, każda z sygnałem ostrzegawczym.
7. **Dowód** — po czym poznam, że wyszło dobrze.
8. **Twój ruch** — 1 zadanie + 1 pytanie kontrolne.

---

**Uczy:** skille, izolacja pracy, delegacja, autonomia, pisanie promptów,
grillowanie i review, jak spiąć komendy kitu w jeden flow.

**Nie uczy:** Django, React, architektury. Pytanie o kod → odsyła do
pozostałych. Celowo — powtórzona treść między nauczycielami rozjeżdża się
szybciej, niż ktokolwiek to naprawia.

**Czyta przed odpowiedzią:** `.claude/agents/`, `.claude/commands/`,
`.claude/skills/`, `AGENTS.md`, `.mcp.json`, hooki, `get_overlay()`,
`get_module("core:agent-ops-canon")`.

## Rzeczy, które warto stąd pamiętać

**Autonomia to dwa różne wymiary** — notorycznie je mylę:

| Pytanie | Narzędzie | Co ustalam |
|---|---|---|
| **Kiedy przestać?** | `/goal` | kryterium ukończenia, oceniane przez **osobnego sędziego** |
| **Kiedy wrócić?** | `/loop`, `/schedule` | rytm powrotu — nic nie mówi o gotowości |
| **Ile naraz?** | `/batch` | wiele worktree, każdy otwiera PR; wymaga rozłącznych zadań |

**Delegacja:**

- **Każdy spawn startuje na zimno.** Subagent nie widzi mojej rozmowy.
  Zadanie zależne od kontekstu sesji zrobię taniej inline.
- Fan-out ma sens przy **2+ zadaniach bez wspólnego stanu**.
- **Raport subagenta nie trafia do mnie automatycznie.**
- Kontekst to zasób — subagent bywa najtańszy właśnie dlatego, że przeszukanie
  dziesiątek plików dzieje się **poza moim oknem**, a wraca sam wniosek.

**Prompt — trzy rzeczy naraz, inaczej nie działa:**

1. kryterium ukończenia
2. zakres plików
3. wymagany dowód (jaką komendę odpalić i pokazać wynik)

„Popraw to" nie działa, bo nie ma żadnej z tych trzech. „Napraw testy" bez
„pokaż output pytest" produkuje **testy zakomentowane**.

I jeszcze: **kontekst zamiast rozkazów**. „Ten endpoint musi wytrzymać 100
req/s, bo…" daje lepszy wynik niż lista kroków — agent poradzi sobie
z przypadkiem, którego nie przewidziałem.

**Worktree:** jeden worktree = jeden branch = jedno zadanie. Opłaca się przy
2+ zadaniach na różnych branchach i rozłącznych katalogach. Przy jednym zadaniu
to czysty narzut.

## Ściąga

| Sytuacja | Kto |
|---|---|
| „nie wiem jakim narzędziem to ruszyć" | `/teacher-agent` |
| „odpalić subagenta czy inline?" | `/teacher-agent` |
| „puścić to na noc?" | `/teacher-agent` |
| „czy dodać Redisa / wydzielić serwis" | [teacher-architecture](teacher-architecture.md) |
| „gdzie to powinno mieszkać" | [teacher-architecture](teacher-architecture.md) |
| „gdzie dać walidację" | [teacher-backend](teacher-backend.md) |
| „czy ten model jest ok" | [teacher-backend](teacher-backend.md) |
| „gdzie trzymać ten stan" | [teacher-frontend](teacher-frontend.md) |
| „czemu to się re-renderuje" | [teacher-frontend](teacher-frontend.md) |

Puste wywołanie (`/teacher-agent` bez argumentu) → przejrzy realny setup i
nauczy o **najsłabszym ogniwie**. Warto raz na jakiś czas.

## Pułapki (wspólne dla całej rodziny `/teacher-*`)

1. **Pytanie nauczyciela o implementację.** Odmówi i odeśle. To nie jest
   uszkodzenie — to jego definicja.
2. **Pytanie reviewera o projekt.** Odwrotny błąd, ten sam koszt.
3. **Mieszanie domen.** Pytanie o Django zadane `/teacher-agent` → odeśle.
   Celowo, żeby treść się nie rozjeżdżała między nimi.
4. **Ignorowanie punktu „Twój ruch".** Kończy zadaniem i pytaniem kontrolnym.
   Pominięcie tego zamienia lekcję w esej, który przeczytam i zapomnę.

## Do przemyślenia

- `/teacher-agent` opisuje flow kitu ([git-start](git-start.md) → … →
  [git-end](git-end.md)), ale nie wie o skillach Matta. Po przepisaniu
  `start-feat.md` warto sprawdzić, czy sekcja „Ten kit — jak to się spina" nie
  jest już nieaktualna.
- Nauczyciele czytają `get_module("core:*-canon")`. Nie sprawdziłem, czy te
  moduły faktycznie istnieją w `modules/`.
