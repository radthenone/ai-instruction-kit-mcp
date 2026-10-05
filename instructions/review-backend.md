# `/review-backend` — Django/DRF (albo overlay stacka)

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-backend.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

Najpierw czyta MCP (`get_bundle("backend")`, `get_overlay()`), a `BUGBOT.md`
tylko po to, **żeby nie dublować** jego findingów.

Czego szuka:

- brak testów dla zmian w kodzie backendu
- zmiana serializera / viewsetu / URL / schema przy `codegen: orval` **bez
  regeneracji klienta FE** — przy `manual`/`none` tego nie wymaga
- ACL / `permission_classes` — otwarte endpointy bez uzasadnienia
- Celery — taski nieidempotentne, argumenty jako **obiekty ORM zamiast ID**
- brak type hints / docstringów na nowych publicznych funkcjach

Zwraca standardową tabelę `Severity | Location | Finding | Fix` — patrz format
w [review-bugbot](review-bugbot.md).

**Kiedy wołać zamiast pary crossreview:** zmiana tylko po stronie backendu.
Jeśli zmiana przechodzi przez kontrakt API do frontendu, patrz
[subagent-backend](subagent-backend.md) (dwuokienkowy cross-review).
