# Przegląd komend

Komendy kita mają neutralne nazwy, np. `git-start`. Każdy klient wywołuje je swoim przedrostkiem:

| Klient | Wywołanie | Uwagi |
|---|---|---|
| Claude Code | `/kit-ai:<komenda>` | |
| Codex | `$kit-ai:<komenda>` | w T3: `/skill:kit-ai:<komenda>` |
| VS Code (Copilot) | `/<komenda>` | odłożone (#522) |
| Antigravity | `/kit-ai:<komenda>` | w T3: `/skill:kit-ai:<komenda>` |
| opencode | `/kit-ai/<komenda>` | |

Zewnętrzne skille (`/tdd`, `/grill-me`, `/goal`) wywołujesz bez zmian. Cursor ma osobny skill `/compact`, który działa tylko w Cursorze.

!!! tip "Pomoc przy każdej komendzie"
    Wpisz `--help` po nazwie komendy, np. `/kit-ai:git-start --help` albo `/kit-ai:create-task --help`. Flagi są tam opisane.

## Git

| Komenda | Co robi |
|---|---|
| `git-start` | issue i branch w konwencji `typ/N-slug` |
| `git-check` | dopasowuje tytuł i body issue do realnego diffa |
| `git-commit` | Conventional Commit albo kilka commitów z diffa |
| `git-end` | push i PR z `Closes #N` |

Szczegóły: [Git](git.md).

## Review

| Komenda | Kiedy |
|---|---|
| `review-bugbot` | przed każdym pushem, manualny odpowiednik BugBota |
| `review-backend`, `review-frontend` | zmiany w backendzie i w kliencie |
| `review-ui` | ekrany, formularze, flow użytkownika |
| `review-architecture` | kontrakt API, struktura monorepo |
| `review-security` | auth, uprawnienia, płatności, sekrety |
| `review-tests` | dowód, że testy i komendy faktycznie przechodzą |
| `review-edge` | przypadki brzegowe, regresje, brakująca walidacja |
| `review-council` | rada trzech delegatów w rundach, dla dużych decyzji |

Szczegóły: [Review](review.md).

## Zadania, skille i konfiguracja

| Komenda | Co robi |
|---|---|
| `create-task` | ocena pomysłu i karta issue, bez brancha |
| `create-skill` | rozstrzyga skill czy agent, potem karta issue |
| `kit-project-begin` | pierwsza konfiguracja projektu |
| `kit-project-edit` | jedna zmiana konfiguracji albo naprawa zgłoszeń doctora |

Szczegóły: [Zadania, skille i konfiguracja](zadania-i-konfiguracja.md).

## Praca nocna i headless

| Komenda | Co robi |
|---|---|
| `night-run` | nocna praca na liście issue: orkiestrator i subagent na ticket |
| `night-run-ticket` | subagent pojedynczego ticketu, używany przez `night-run` |
| `headless` | zleca zadanie innemu klientowi bez interfejsu |

Szczegóły: [Praca nocna i headless](praca-nocna-i-headless.md).

## Nauka, subagenty i narzędzia

| Komenda | Co robi |
|---|---|
| `teacher-backend`, `teacher-frontend`, `teacher-architecture`, `teacher-agent` | uczą przed kodem, nie edytują plików |
| `subagent-backend`, `subagent-frontend` | cross-review w dwóch oknach |
| `cleanup` | usuwa pliki tymczasowe z weryfikacji, po potwierdzeniu |
| `issue-stats`, `pr-stats` | raport o issues i PR: gotowość, ryzyka, blokery |
| `kit-retro` (skill) | klasyfikuje znaleziska z analizy sesji |

Szczegóły: [Nauka, subagenty i narzędzia](nauka-subagenty-narzedzia.md).

!!! note "Menu `/` w side chacie T3 Code"
    Raz menu nie podpowiedziało komend `/kit-ai:*` (#559). Wpisz pełną nazwę ręcznie, np. `/kit-ai:create-task --help`. T3 przekaże ją jako komendę.
