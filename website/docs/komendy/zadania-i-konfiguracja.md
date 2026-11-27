# Zadania, skille i konfiguracja

Te komendy zaczynają pracę: od pomysłu do issue i od pustego projektu do działającej konfiguracji.

## `create-task`

Od pomysłu do karty issue. Agent ocenia pomysł na tle repo, przygotowuje kartę i zakłada issue po twojej akceptacji. **Nie zakłada brancha**, to robi `git-start`.

```text
/kit-ai:create-task                  # interaktywnie
/kit-ai:create-task "eksport CSV"    # z opisem
/kit-ai:create-task --help
```

| Flaga | Efekt |
|---|---|
| `--dry-run` | pokazuje kartę bez zakładania issue |
| `--quick` | szybki tryb |
| `--split` | tryb z podziałem na kilka issue |
| `--no-assign` | nie przypisuje issue do nikogo |
| `--parent #N` | podpina issue pod issue nadrzędne |

## `create-skill`

Pomysł na skill, czyli wiedzę, którą model ładuje **sam**, gdy opis pasuje do sytuacji. Komenda rozstrzyga, czy to skill, czy agent. Jeśli agent, odsyła do `create-task`. Potem zakłada kartę issue z nazwą, opisem i kryterium odpalenia. **Nie pisze pliku `SKILL.md`.**

```text
/kit-ai:create-skill "konwencje migracji"
```

Flagi są jak w `create-task`: `--dry-run`, `--quick`, `--no-assign`, `--parent #N`.

Skille kita leżą w `templates/shared/skills/<nazwa>/SKILL.md`. Piszesz je według skilla `skill-authoring`, który trzyma zasady frontmatter, długości i kryteriów odpalania.

## Skill czy agent

| | Skill | Agent |
|---|---|---|
| Kto go uruchamia | model sam, gdy `description` pasuje | człowiek przez `/nazwa` |
| Co zawiera | wiedzę: `SKILL.md`, opcjonalnie `scripts/` i `references/` | procedurę |
| U klientów bez natywnych skilli | zostaje komenda, która gubi wszystko poza `SKILL.md` | bez zmian |

Skill, którego sens leży w `scripts/`, u pięciu z ośmiu klientów będzie tylko wydmuszką. Wtedy to prawdopodobnie powinien być agent.

## `kit-project-begin`

Pierwsza konfiguracja po `kit-ai install`. Szczegóły: [Pierwsza konfiguracja](../start/pierwsza-konfiguracja.md).

```text
/kit-ai:kit-project-begin          # wywiad z propozycjami
/kit-ai:kit-project-begin --yes    # zaakceptuj propozycje wykryte w repo
```

## `kit-project-edit`

Jedna zmiana bez całego wywiadu. Działa w trzech trybach:

- **A: jedna odpowiedź**: Stack per Tier, codegen, klienci, język albo sekcja `project.md`. Agent pokazuje podgląd, zapisuje i robi reload.
- **B: spór z modułem**: gdy nie zgadzasz się z regułą modułu, agent prowadzi wywiad i zapisuje odstępstwo w `## Odstępstwa od modułów` w `.ai/project.md`. Moduły kita nie są zmieniane.
- **C: naprawa doctora**: poprawia zgłoszenia w overlayu, bloku `project:rules` w `BUGBOT.md` i bloku `project:agents` w `AGENTS.md`. Pokazuje jeden podgląd na całą partię.

```text
/kit-ai:kit-project-edit "zmień web na angular"
/kit-ai:kit-project-edit "nie zgadzam się z modułem X"
/kit-ai:kit-project-edit "napraw zgłoszenia doctora"
```

Zmiana dla **wszystkich** projektów nie idzie tą drogą. Agent proponuje szkic `create-task` w repo kita. Komenda nigdy nie edytuje `modules/`.
