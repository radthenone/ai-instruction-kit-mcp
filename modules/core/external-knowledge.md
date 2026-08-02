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

## Meta-skills i pluginy (poza instruction-kit)

Instruction-kit dostarcza **Waszą** architekturę (moduły + MCP `project-guides`). Nie bundluje Matt/Superpowers.

### Trzy warstwy

| Warstwa | Narzędzie | Montaż | Odpowiada za |
|---------|-----------|--------|----------------|
| Fundament | ten kit (`project-guides`, `/review-*`) | `.cursor/mcp.json`, agents z bootstrap | stack, overlay, review przed push |
| Proces | [mattpocock/skills](https://github.com/mattpocock/skills) | `npx skills@latest add mattpocock/skills` (+ Cursor) | `/grill-me`, `/tdd`, PRD |
| Meta | superpowers, caveman, … | user / plugin Cursor | brainstorm, debug, finishing |

W projekcie trzymaj cienkie `.cursor/agents` z kita. Matt możesz mieć per-repo lub globalnie. Superpowers trzymaj user-level.

### Instalacja Matt (Cursor)

```bash
cd <repo-aplikacji>
npx skills@latest add mattpocock/skills
# zaznacz Cursor + setup-matt-pocock-skills
# potem w czacie: /setup-matt-pocock-skills
```

### Wyrównanie (żeby się nie gryzły)

1. Stack / Taskfile / ścieżki → **zawsze** MCP kita, nigdy Matt/Superpowers.  
2. Scope feature → Matt `/grill-me`.  
3. TDD → **jeden** path: Matt `/tdd` *albo* superpowers TDD (domyślnie Matt na nowe feature’e).  
4. Review diffu stacku → `/review-backend` / `/review-frontend` (kit).  
5. Bugbot → `/review-bugbot`.  

Pełny opis priorytetów: szablon `templates/AGENTS.md` (kopiowany do `AGENTS.md` w projekcie).


## Jak odpowiadać

Oddziel w odpowiedzi:

- **potwierdzone w repo**
- **potwierdzone w docs / web**
- **niepewne**

Gdy źródła się różnią — wskaż konflikt i co obowiązuje w tym projekcie (repo + wersja z lockfile).
