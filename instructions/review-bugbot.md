# `/review-bugbot` — bramka przed pushem

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-bugbot.md`.
> Format wspólny wszystkim reviewerom: patrz [[review-format]] (na razie tylko
> tu opisany).

## Format wspólny dla wszystkich `/review-*`

Każdy z siedmiu reviewerów zwraca **tylko tabelę**, po polsku, bez eseju:

| Severity | Location | Finding | Fix |
|----------|----------|---------|-----|
| high \| medium \| low \| info | `path:line` | problem (1–2 zdania) | konkretna naprawa |

Znaczenie wag: **high** = napraw przed pushem · **medium** = w scope tego PR ·
**low**/**info** = opcjonalne.

**Niska pewność = pytanie, nie finding.** Auth, ACL, billing, migracje,
concurrency, breaking API — jeśli nie ma dowodu w diffie, ma zapytać, a nie
zgadywać. Krytyczny finding bez pewności ma być oznaczony jako pytanie.

---

**To nie jest jeden z siedmiu. To ten, który idzie zawsze.**

Manualny odpowiednik Cursor BugBota — natywny BugBot to usługa chmurowa Cursora,
czyta `BUGBOT.md` sam przy PR i nie działa poza Cursorem. Ta komenda robi to
samo ręcznie, w Claude Code / Codex / gdziekolwiek.

**Fokus:** blokujące bugi, sekrety, bezpieczeństwo, oczywiste dziury.
**Inny format:** `Blocking? | Location | Finding | Reguła`.

Szuka pliku reguł w kolejności: `BUGBOT.md` w root → `.cursor/BUGBOT.md` → brak
pliku, wtedy tylko reguły ogólne z `AGENTS.md`. **W tym repo `BUGBOT.md` jest
w roocie** — 2.8K.

**Sekrety flaguje zawsze**, niezależnie od `BUGBOT.md`: `password\s*=`,
`api[_-]?key\s*=`, `Bearer\s+…`, `sk_live_`, `pk_live_`, `AWS_SECRET`.

**Nie wymyśla reguł spoza pliku.** Jak reguła odsyła do komendy — poda ją
w kolumnie Finding, ale sam nie odpali.

## Ściąga — kogo wołać

| Zmiana dotyka | Kolejność |
|---|---|
| cokolwiek, przed pushem | `/review-bugbot` — **zawsze** |
| serializery, ACL, Celery, migracje | [review-backend](review-backend.md) |
| ekrany, klient Orval, `.web`/`.native` | [review-frontend](review-frontend.md) |
| kontrakt API, układ monorepo, capability-provider | [review-architecture](review-architecture.md) |
| formularze, flow użytkownika, wspólne komponenty | [review-ui](review-ui.md) |
| duża zmiana, dużo warunków, async | [review-edge](review-edge.md) |
| po każdym „zrobione" | [review-tests](review-tests.md) |

Zwykły PR: **bugbot + jeden stackowy**. Duży PR: **+ edge**. Po deklaracji
gotowości: **+ tests**.

## Pułapki (wspólne dla całej rodziny `/review-*`)

1. **Wołanie wszystkich siedmiu na mały diff.** Dostaję siedem tabel, z czego
   pięć pustych, i przestaję je czytać. Dwóch reviewerów przeczytanych bije
   siedmiu przewiniętych.
2. **`/review-*` zamiast CI.** Wszyscy mogą przejść, a build się wywali.
   Review jest **przed** pushem, nie zamiast pipeline'u.
3. **Mylenie z `/code-review` Matta.** Tamten porównuje diff do **punktu
   odniesienia** (`master`, SHA) na dwóch osiach: Standards i Spec, w dwóch
   równoległych subagentach. Ci tutaj patrzą na bieżący diff przez pryzmat
   konwencji stacku z MCP. Nie zastępują się — Matt sprawdza *czy robi to,
   o co prosiło issue*, moi sprawdzają *czy pasuje do tego repo*.
