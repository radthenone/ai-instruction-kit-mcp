# Język i codegen

## Język

Profil ma klucz `language:` z wartością `pl` albo `en`. Dotyczy **prozy**: odpowiedzi agenta, docstringów, treści issue i PR, komunikatów commitów.

Zawsze po angielsku, niezależnie od języka: **tytuły** issue, PR i branchy, wszystkie identyfikatory w kodzie, w tym nazwy testów.

Kolejność, z której serwer MCP bierze język:

1. flaga `--language` albo zmienna `GUIDES_LANGUAGE`,
2. klucz `language:` w Profilu,
3. domyślnie `pl`.

Moduł językowy w bundlach to `core:language-pl` albo `core:language-en`. Wartość sprawdzisz narzędziem `get_language`.

## Codegen

`codegen:` mówi, jak klient dostaje typy API. Ustawiasz go **tylko** w Profilu, na najwyższym poziomie:

| Wartość | Efekt |
|---|---|
| `orval` (domyślnie) | klient generowany przez Orval z OpenAPI. Moduł `arch:api-contract` |
| `none` | generyczny klient bez Orval. Moduł `arch:api-contract:none` |
| `graphql` | kontrakt GraphQL zamiast REST. Moduł `arch:api-contract:graphql` |

Codegen zastępuje moduł ogólny wariantem. To substytucja, nie wariant. Zob. [Sloty i decyzje](sloty-i-decyzje.md).

Bez pary **backend plus klient** (web albo mobile) efektywny codegen to zawsze `none`, niezależnie od wpisu. Reviewery frontendu i backendu honorują tę wartość. Przy `orval` po zmianie API trzeba zregenerować klienta, zanim zakończysz pracę. Odczyt wartości: narzędzie MCP `get_codegen`.
