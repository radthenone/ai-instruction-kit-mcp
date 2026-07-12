# External Knowledge — frameworki, paczki, architektura

Repo-first **nie oznacza** odpowiadania wyłącznie z pamięci modelu. Gdy temat dotyczy API frameworka, struktury projektu, konwencji biblioteki albo wzorców architektonicznych — **najpierw potwierdź** w źródłach zewnętrznych, potem dopasuj do projektu.

## Kiedy szukać na zewnątrz

- API / hooki Django, DRF, Celery, django-allauth, Expo, React Native, TanStack Query, Zustand, Orval, NativeWind.
- Umiejscowienie kodu (middleware, settings, warstwy) — konwencje frameworka.
- Zachowanie zależne od **wersji** (breaking changes, deprecations).
- Komunikaty błędów z narzędzi zewnętrznych (pip, uv, bun, expo, eslint).
- Paczki własne — gdy w projekcie brak implementacji.

## Kolejność źródeł

1. **Projekt** — overlay (`.ai/project.md`), kod, lockfile.
2. **Instruction-kit** — bundle z MCP `project-guides`.
3. **Lokalne repo paczek** — jeśli ścieżki podane w overlay projektu.
4. **Oficjalna dokumentacja** — z wersją z lockfile.
5. **Repozytorium / release notes** pakietu na GitHubie.
6. **Stack Overflow** — z tagiem wersji; jako uzupełnienie.
7. **Artykuły** — wzorce architektury; zweryfikuj w docs przed rekomendacją.

## Dokumentacja bibliotek (Context7)

Do oficjalnych docs vendorów używaj **Context7** (`npx ctx7 setup --cursor`) — nie duplikuj dokumentacji Django/Expo w instruction-kit.

Przykład: „use context7 — Django 5.2 middleware”.

## Jak odpowiadać

Oddziel w odpowiedzi:

- **potwierdzone w repo**
- **potwierdzone w docs / web**
- **niepewne**

Gdy źródła się różnią — wskaż konflikt i co obowiązuje w tym projekcie (repo + wersja z lockfile).
