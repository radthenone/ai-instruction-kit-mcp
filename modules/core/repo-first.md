# Repo-first

## Zasada nadrzędna

Przy każdym pytaniu technicznym i każdej propozycji zmian:

1. Najpierw przeanalizuj realną strukturę repozytorium projektu.
2. Wskaż konkretne pliki i ścieżki związane z problemem.
3. Oddziel to, co potwierdzone, od tego, czego nie udało się potwierdzić.
4. Dopiero potem przedstaw diagnozę, ryzyka i plan zmian.
5. Nie zakładaj istnienia plików, warstw ani wzorców, których nie widać w repo.

Repo-first **nie wyłącza** weryfikacji w dokumentacji frameworków i paczek — patrz moduł `core:external-knowledge`.

## Priorytet instrukcji

Stosuj instrukcje w tej kolejności:

1. Bezpośrednie polecenie użytkownika.
2. Overlay projektu (`.ai/project.md`) — unikalne dla tego repo.
3. Bundle z instruction-kit (MCP `project-guides`).
4. Lokalny `AGENTS.md` (cienki bootstrap).
5. Reguły Cursor (bootstrap `use-guides.mdc`).

Jeśli instrukcje są sprzeczne, pierwszeństwo ma poziom wyższy.

## Format odpowiedzi technicznej

1. Krótka diagnoza.
2. Co dokładnie znaleziono w repo.
3. Lista problemów, ryzyk lub ograniczeń.
4. Rekomendowany plan zmian krok po kroku.
5. Propozycja implementacji (jeśli ma sens).
6. Jeśli czegoś nie dało się potwierdzić — napisz wprost.

## Nowa zasada architektoniczna — dokąd ją zapisać

Zanim zapiszesz nową regułę/wzorzec (nie fakt jednego produktu) — rozstrzygnij:

| Pytanie | TAK → `.ai/project.md` (fakt produktu) | TAK → instruction-kit (reużywalna zasada) |
| --- | --- | --- |
| Dotyczy tylko tego repo (nazwa, porty, konkretny provider bez uzasadnienia architektonicznego)? | ✓ | — |
| Zadziałałaby tak samo w innym projekcie tej samej kategorii (`shop`, `_base`)? | — | ✓ |
| To nowy wzorzec/standard, nie jednorazowa decyzja biznesowa tego klienta? | — | ✓ |

Reużywalna zasada → **nie** zapisuj wyłącznie w `.ai/project.md`. Zaproponuj zmianę w instruction-kit:

1. Znajdź najbliższy istniejący moduł (`modules/**`) — rozszerz go, jeśli tematycznie pasuje.
2. Brak pasującego modułu → zaproponuj nowy (+ wpis w `manifest.yaml`, ew. `profiles/*.yaml`).
3. Instruction-kit to **osobne repo** — przed edycją zapytaj użytkownika, gdzie ono lokalnie leży
   (ścieżka z `--from` w `mcp.json`, albo wprost zapytaj) i potwierdź zanim tam coś zmienisz.
4. W `.ai/project.md` zostaw wtedy tylko odnośnik, nie kopię treści:
   `patrz instruction-kit: capability:X` — nie duplikuj tekstu w dwóch repo naraz.

Bez tego kroku reguły reużywalne rozjeżdżają się po projektach jako lokalne kopie w `.ai/project.md`
zamiast żyć w jednym miejscu, które inne projekty dziedziczą przez `--preset`/`extends`.

## Higiena repozytorium

- Nie commituj cache, coverage, logów, `.env`, `.venv`, `node_modules`, build outputów.
- Nie edytuj ręcznie plików generowanych (np. klientów Orval/OpenAPI).
- Przy dużej liczbie zmian roboczych — nazwij ten fakt przed analizą.
