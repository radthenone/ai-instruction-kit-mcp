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

## Higiena repozytorium

- Nie commituj cache, coverage, logów, `.env`, `.venv`, `node_modules`, build outputów.
- Nie edytuj ręcznie plików generowanych (np. klientów Orval/OpenAPI).
- Przy dużej liczbie zmian roboczych — nazwij ten fakt przed analizą.
