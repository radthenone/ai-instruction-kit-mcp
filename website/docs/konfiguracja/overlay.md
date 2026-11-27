# Overlay: `.ai/project.md`

Overlay zawiera **fakty tego jednego repo**: ścieżki, porty, nazwy zadań, komendy testów. Leży w repo aplikacji. Agent czyta go przez narzędzie MCP `get_overlay` przed pierwszą edycją. Overlay jest dołączany do Bundle, nigdy w nim nie scalany, i nigdy nie jest wklejany do briefu.

## Kto go zakłada i kto go zmienia

- `kit-ai install` tworzy `.ai/project.md`, ale tylko gdy go nie ma.
- Kolejne `kit-ai reload` **nie rusza** tego pliku.
- Zmieniasz go ręcznie albo przez `/kit-ai:kit-project-edit`.

## Co tu wpisać

Fakty repo, których nie da się wywnioskować z modułów:

- **Ścieżki** w sekcji `## Ścieżki`: klucze `backend:`, `web:`, `mobile:` i opcjonalne `routes-web:`, `design-tokens:`. Każdy wskazuje katalog albo plik, który musi istnieć.
- **Komendy**: testy, lint, typecheck, nazwy zadań Taskfile.
- **Porty i usługi lokalne**, np. baza na porcie, kolejka, dev server.
- **Odstępstwa od modułów** w sekcji `## Odstępstwa od modułów`. Zapisujesz tu świadome „nie stosujemy tej reguły”.
- **Gałąź bazowa** w linii `base: <gałąź>`, używana przez `git-start` i `git-end`.

## Czego tu nie wpisywać

Reguły architektoniczne, które mogłyby działać w innym projekcie, nie należą do overlayu. Zaproponuj je jako zmianę w kicie przez `/kit-ai:create-task` w repo kita. Overlay trzyma tylko to, co prawdziwe wyłącznie dla tego repo.

## Przykład (fikcyjny)

```markdown title=".ai/project.md (przykład)"
# Overlay projektu

base: dev

## Ścieżki

backend: apps/
web: frontend/web/

## Komendy

- Testy backendu: `task test:backend`
- Lint: `task lint`

## Odstępstwa od modułów

- Migracje piszemy ręcznie, bez `makemigrations --check` w lokalnym runnerze. Pełna weryfikacja w CI.
```

## Doctor sprawdza overlay

`kit-ai doctor` czyta overlay i porównuje ścieżki z drzewem repo. Ścieżka, której nie ma, daje ostrzeżenie `stale-path`. Zob. [Doctor](../diagnostyka/doctor.md).
