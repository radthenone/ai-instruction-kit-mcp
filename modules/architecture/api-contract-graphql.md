# Kontrakt API — GraphQL

Wariant `codegen: graphql`. Wybieraj świadomie — nie domyślny, nie migruj istniejącego REST+Orval
bez konkretnego powodu (patrz "Kiedy to ma sens" niżej).

## Różnica vs REST (`arch:api-contract`)

REST: kształt odpowiedzi ustala backend per endpoint (`/api/products/5/` zawsze zwraca te same
pola). Potrzebujesz węższego JSONa (np. lista produktów na mobile) → nowy endpoint albo query
param.

GraphQL: klient sam deklaruje w zapytaniu jakich pól chce (`{ product(id: 5) { name price } }`),
serwer zwraca dokładnie to. Jeden endpoint (`/graphql`) zamiast wielu REST endpointów.

## Kiedy to ma sens

- Wiele bardzo różnych klientów (web, mobile, partner API) potrzebujących różnych podzbiorów
  tych samych danych — bez mnożenia REST endpointów/serializerów per widok.
- Głęboko zagnieżdżone dane w jednym query (produkt + warianty + recenzje + rekomendacje)
  zamiast kaskady kilku REST requestów.

Gdy tego nie ma — REST+Orval (`arch:api-contract`) jest prostszy i tańszy operacyjnie. Nie
wybieraj GraphQL "bo popularne" (Saleor go używa, ale to inna skala i inny zespół).

## Backend

- `strawberry-django` (typed, dataclass-first) albo `graphene-django` — wybierz jedno,
  udokumentuj w `.ai/project.md`.
- **Problem N+1**: każde zagnieżdżone pole może odpalić osobny query per wiersz. Obowiązkowo
  DataLoader (batching) dla relacji — inaczej jedno query listy = setki zapytań do DB.
- Autoryzacja per pole/typ, nie tylko per endpoint jak w DRF permissions — łatwo przeoczyć
  pole zwracające dane innego usera w zagnieżdżonym query.

## Frontend

- Klient: Apollo Client albo urql (nie fetch + Orval — inny model cache'owania, cache po
  polach/ID obiektu, nie po URL).
- Codegen: `graphql-codegen` generuje typy z `.graphql` query + schema — inny pipeline niż
  Orval z OpenAPI, osobna komenda w Taskfile (`task graphql:generate`, nazwa do ustalenia
  w `.ai/project.md`).
- Przy 401: interceptor na poziomie link/exchange (Apollo `errorLink` / urql `authExchange`),
  nie standardowy HTTP interceptor jak w REST.

## Sekwencja po zmianie API

```text
backend (typ/resolver/schema) → task graphql:generate → task lints:frontend:typecheck
```

## Testowanie bez frontendu

GraphiQL / Apollo Sandbox zamiast Swagger UI — backend musi być testowalny samodzielnie przed
powstaniem UI, tak samo jak w REST.

## Powiązane moduły

- `arch:api-contract` — REST+Orval, default; przeczytaj przed wyborem GraphQL
- `arch:api-errors` — GraphQL zwraca błędy inaczej (`errors[]` w response, nie HTTP status) —
  ujednolić z resztą API jeśli monorepo miesza oba podejścia
- `capability:auth` — autoryzacja per pole, nie tylko per endpoint
