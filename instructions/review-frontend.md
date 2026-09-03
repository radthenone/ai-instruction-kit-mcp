# `/review-frontend` — Expo Router / React / RN

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-frontend.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

Najpierw czyta MCP (`get_bundle("frontend")`, `get_overlay()`), a `BUGBOT.md`
tylko po to, **żeby nie dublować** jego findingów.

Czego szuka:

- **ręczne edycje w katalogu generowanego klienta Orval = high**
- zmiana API w PR bez regeneracji / bez commita outputu Orval = **high**
- import `react-native` w `.web.tsx`, DOM-only API w `.native.tsx`
- `any` na nowych publicznych interfejsach bez uzasadnienia
- TanStack Query (server state) mylone z Zustand (local state)

W kolumnie Fix ma wskazać komendę z overlay — np. `task ovral:generate`.

Zwraca standardową tabelę `Severity | Location | Finding | Fix` — patrz format
w [review-bugbot](review-bugbot.md).

**Kiedy wołać zamiast pary crossreview:** zmiana tylko po stronie frontendu.
Jeśli zmiana przechodzi przez kontrakt API do backendu, patrz
[subagent-frontend](subagent-frontend.md) (dwuokienkowy cross-review).

**Do przemyślenia:** czy [review-ui](review-ui.md) i `/review-frontend` nie
powinny się scalić — nakładają się na komponentach. Argument przeciw: UI patrzy
na UX i a11y, frontend na konwencje stacku i Orval. Na razie zostawiam.
