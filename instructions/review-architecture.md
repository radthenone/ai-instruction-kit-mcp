# `/review-architecture` — kontrakt API i układ monorepo

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-architecture.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

Najpierw czyta MCP (`get_bundle("architecture")`, `get_overlay()`), a
`BUGBOT.md` tylko po to, **żeby nie dublować** jego findingów.

Czego szuka:

- zgodność z capability-provider i układem monorepo z bundle
- zmiana kontraktu API przy `codegen: orval` bez regeneracji klienta
- **logika biznesowa przeciekająca do klienta**
- brak separacji platform (backend / web / mobile) w kodzie wspólnym

Zwraca standardową tabelę `Severity | Location | Finding | Fix` — patrz format
w [review-bugbot](review-bugbot.md).

**vs [teacher-architecture](teacher-architecture.md):** ten łapie naruszenie
granicy w gotowym diffie, po fakcie. `/teacher-architecture` uczy widzieć
granice zanim się kod napisze.
