# React — przegląd Stacku (web)

Tier `web: react` (aktualne podejście, React 19+) albo `web: react@legacy` (React 16–18).
Ten moduł jest wspólny dla obu; szczegóły podejścia: `stack:react:modern` albo
`stack:react:legacy`. Katalog kodu: klucz `web:` w sekcji `## Ścieżki` w `.ai/project.md`
(dalej: `<web>`).

## Typowy zestaw

| Obszar | Typowo | Gdzie decyzja |
|--------|--------|---------------|
| Build / dev server | Vite | `<web>/package.json` |
| Routing | React Router albo TanStack Router | overlay / repo |
| Stan serwera | TanStack Query (hooki z wygenerowanego klienta przy `codegen: orval`) | Profil `codegen:` |
| Stan lokalny / globalny | `useState` / `useReducer`; globalny tylko gdy trzeba (Context, Zustand) | repo |
| Formularze | `stack:react:modern` / `stack:react:legacy` | — |
| Testy | Vitest + Testing Library + MSW; e2e Playwright | `arch:testing` |
| Typowanie | TypeScript strict | `core:typing-typescript` |

Wersje sprawdzaj w lockfile `<web>` — React 18 i 19 różnią się API, nie zgaduj z pamięci.

## Układ katalogów

```text
<web>/
  src/
    app/                 # routing, layouty, providery (QueryClientProvider, router)
    features/<feature>/  # ekrany, komponenty, hooki jednego obszaru
    shared/
      ui/                # komponenty bez wiedzy o domenie
      lib/               # helpery
    api/
      generated/         # klient z OpenAPI — nie edytuj ręcznie
  index.html
  vite.config.ts
  package.json
```

Feature nie importuje z wnętrza innego feature'a — wspólne przenieś do `shared/`.

## Zasady wspólne

- **Komponenty to funkcje.** Bez komponentów klasowych w nowym kodzie (wyjątek: error
  boundary w React < 19 bez biblioteki).
- **Reguły hooków** — tylko na najwyższym poziomie komponentu / hooka; lint
  `eslint-plugin-react-hooks` włączony i nie wyciszany.
- **Stan w najniższym wspólnym rodzicu.** Nie kopiuj propsów do stanu; wartości pochodne
  licz w renderze.
- **Efekt to synchronizacja z systemem zewnętrznym** (subskrypcja, DOM, timer), nie
  sposób na przeliczenie stanu ani na obsługę zdarzenia.
- **Dane z API to stan serwera** — cache, ponowienia i unieważnianie robi biblioteka
  (TanStack Query), nie ręczny `useEffect` + `useState` w każdym komponencie.
- **Klucze list** stabilne z danych (`id`), nigdy indeks przy listach zmiennych.
- **Granice błędów i ładowania**: `<Suspense>` + error boundary na poziomie trasy /
  sekcji, nie spinner w każdym liściu.
- **Dostępność**: semantyczny HTML (`button`, `label` + `htmlFor`, nagłówki), focus po
  nawigacji i w modalach.

## Kontrakt API

Przy `codegen: orval` (MCP `get_codegen`) klient i hooki są w `<web>/src/api/generated/` —
nie piszesz ręcznie `fetch` do własnego API ani typów odpowiedzi. Zmiana kontraktu po
stronie backendu = regeneracja w tym samym PR (`arch:api-contract`).

## Powiązane

- `stack:react:modern` — React 19+: actions, `use()`, kompilator
- `stack:react:legacy` — React 16–18: hooki, ręczna memoizacja, migracja
- `arch:api-contract`, `arch:api-errors`, `arch:testing`, `arch:i18n`, `core:typing-typescript`
