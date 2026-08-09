# Search — Postgres full-text (`tsvector`)

Wariant `decisions.search: postgres` (**default** rekomendowany dla małego/średniego katalogu —
nie dokładaj osobnego silnika search bez realnej potrzeby).

## Różnica vs `django-filter`

`django-filter` = **strukturalne** filtrowanie po polach (`price__gte=100`, `category=5`) —
dokładne dopasowanie, SQL `WHERE`, przyspieszone zwykłym DB index (`db_index=True`).

Full-text search = **inny problem**: zapytanie tekstowe użytkownika (literówki, ranking
trafności po wielu polach naraz — nazwa > opis > tagi), nie dokładne dopasowanie.
DB index na pojedynczej kolumnie tego nie daje.

## Implementacja

```python
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.contrib.postgres.indexes import GinIndex

class Product(models.Model):
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [GinIndex(fields=["search_vector"])]
```

- Aktualizuj `search_vector` sygnałem `post_save` albo trigger DB (nie w każdym query).
- Ranking: `SearchRank` + wagi per pole (`A` nazwa, `B` opis, `C` tagi).
- Literówki: `pg_trgm` (`TrigramSimilarity`) jako fallback gdy `tsvector` nic nie zwróci.

## Kiedy to nie wystarczy

Przy dużym katalogu i realnej potrzebie facetów liczonych na żywo (agregacje po wielu
atrybutach jednocześnie, sub-100ms) → `decisions.search: meilisearch`
(`infra:search:meilisearch`). Nie przełączaj się zanim `tsvector` faktycznie nie wystarcza —
dodatkowy serwis to dodatkowy operacyjny koszt.

## Powiązane

- `arch:migrations` — indeksy i performance ORM
- `domain:shop` — katalog produktów
- `infra:search:meilisearch` — alternatywa przy większej skali
