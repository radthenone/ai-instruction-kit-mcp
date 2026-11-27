# Doctor: zgodność reguł z repo

Doctor sprawdza, czy reguły projektu wskazują rzeczy, które istnieją. Ścieżka w regule, która zniknęła po refaktorze, po cichu przestaje działać. Doctor to zgłasza.

## Co sprawdza

Czyta `BUGBOT.md`, `.ai/project.md`, `AGENTS.md` i `CODING_STANDARDS.md`.

- **Ścieżki w backtickach** muszą istnieć w drzewie repo. Globy i placeholdery są pomijane.
- **Zakres Tieru**: ścieżka w sekcji `## Backend` albo w linii z prefiksem `backend:` liczy się tylko wewnątrz katalogu tego Tieru.
- **Klucze `## Ścieżki`** w overlayu, np. `backend:`, `web:`, `routes-web:`: katalog albo plik musi istnieć.
- **Komendy `/nazwa`**: muszą mieć agenta, komendę albo skill u któregoś z klientów z `clients:`.
- **Pakiety workspace'ów** (Bun, npm, pnpm, uv), których overlay nie opisuje: informacja, nie ostrzeżenie.

Linie skopiowane z szablonu kita są pomijane. To treść kita, nie reguły projektu.

## Komendy

```bash title="Git Bash · bash"
kit-ai doctor              # linie doctor:, kod wyjścia 0
kit-ai doctor --json       # maszynowo: {"warnings", "infos", "findings": [...]}
kit-ai doctor --verbose    # plus INFO, gdy ścieżka pasuje do kilku miejsc
```

Przykładowy wynik:

```text
doctor: 1 ostrzeżenie, 1 informacja
doctor: OSTRZEŻENIE BUGBOT.md:12 — ścieżka `src/auth/` nie istnieje
doctor: INFO .ai/project.md — katalog `packages/ui/` z workspace'u nie jest opisany
```

## Rodzaje zgłoszeń

| `kind` | Poziom | Co znaczy |
|---|---|---|
| `stale-path` | ostrzeżenie | ścieżka w regule albo w `## Ścieżki` wskazuje coś, czego nie ma |
| `negated-path-exists` | ostrzeżenie | overlay pisze, że ścieżki nie ma, a ona istnieje |
| `stale-kit-content` | ostrzeżenie | `AGENTS.md` albo `BUGBOT.md` ma linie ze starej wersji szablonu |
| `stale-project-brief` | ostrzeżenie | blok `kit:brief` nie pasuje do Profilu i overlayu. Reload go odświeży |
| `uncertain-migration` | ostrzeżenie | migracja pliku bez bloku projektu jest niepewna. Propozycja w polu `value` |
| `missing-path-key` | ostrzeżenie | brak klucza w `## Ścieżki`, a domyślna ścieżka nie istnieje |
| `missing-command` | ostrzeżenie | komenda `/nazwa` bez agenta, komendy ani skilla |
| `undescribed-package` | info | pakiet workspace'u bez opisu w `.ai/project.md` |
| `invalid-clients` | info | nieprawidłowe `clients:` w Profilu |
| `path-candidates` | info | tylko z `--verbose`: ścieżka pasuje do kilku miejsc |

Doctor **nigdy nie blokuje** reloadu. Raport wychodzi zawsze, a kod wyjścia to 0.

## Po reloadzie

`kit-ai reload` i MCP `reload_workspace` zapisują ostrzeżenia do `.ai/.kit-doctor.json`. Raport kończy się linią `doctor: N do naprawy → /kit-ai:kit-project-edit "napraw zgłoszenia doctora"`. Czysty przebieg usuwa ten plik.

## Naprawa

`/kit-ai:kit-project-edit "napraw zgłoszenia doctora"` (tryb C) proponuje poprawki w overlayu, w bloku `project:rules` w `BUGBOT.md` i w bloku `project:agents` w `AGENTS.md`. Pokazuje jeden podgląd na całą partię i zapisuje po akceptacji.

Ścieżki w szablonowych częściach `BUGBOT.md` i `AGENTS.md` oraz w `CODING_STANDARDS.md` wymagają ręcznej decyzji. Reload nadpisałby szablon.
