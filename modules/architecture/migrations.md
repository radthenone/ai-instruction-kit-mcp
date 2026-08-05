# Migrations & ORM performance

## Migracje (Django)

| Zasada | Opis |
|--------|------|
| Generowanie | `task db:migrations:make -- <app>` (lub równoważne) |
| Aplikacja | `task db:migrate` |
| Zastosowane pliki | **nie edytuj** po merge na wspólną gałąź — nowa migracja |
| Data migration | `RunPython` + `reverse_code` (nawet `noop` świadomie) |
| Modele w migracji | `apps.get_model` — **nie** importuj logiki z `models.py` |

### Expand / contract (breaking schema)

1. **Expand** — dodaj kolumnę null/default, deploy kodu piszącego obie formy.
2. Backfill data-migration (osobny deploy jeśli duży).
3. **Contract** — usuń starą kolumnę / constraint w kolejnym release.

Unikaj jednej migracji „drop column + rewrite all readers” na produkcji bez planu.

### Deploy

- Migracje przed lub z rolling deploy według strategii hostingu — opisz w overlay.
- Nie polegaj na `migrate` w request path aplikacji.

## Wydajność ORM (N+1)

- Listy / detail z relacjami: `select_related` / `prefetch_related` w
  `get_queryset()` lub selectorze.
- Test regresji N+1: `django_assert_num_queries` / `django_assert_max_num_queries`
  (`stack:django-drf:testing`).
- Paginacja list — bez `count(*)` koszmarów bez świadomej decyzji.
- Współbieżność (stock, płatności): `select_for_update` w `transaction.atomic`
  wewnątrz `serializer.create()` / integracji — nie w luźnym sygnale.

## Indeksy i constraints

- Unikalność biznesowa → constraint DB, nie tylko walidacja serializera.
- Indeks pod filtry list (`status`, `user_id`, FK często joinowane).

## Antywzorce

- `Model.objects.create` w pętli bez `bulk_create` gdy nie potrzeba `save()`.
- Usuwanie migracji z historii shared branch.
- Import `from apps.x.models import Y` w `RunPython` (pęka przy zmianie modelu).

## Powiązane

- `stack:django-drf:backend-standard` — skrót ORM
- `stack:django-drf:testing` — assert zapytań
- `infra:database:postgres`
- `arch:testing`
