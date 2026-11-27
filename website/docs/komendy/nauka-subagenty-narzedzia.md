# Nauka, subagenty i narzędzia

## Teacher: uczy przed kodem

`review-*` sprawdza gotowy diff. `teacher-*` działa **zanim** napiszesz kod. Bierze twoją koncepcję (albo bieżący diff, gdy nie podasz argumentu), tłumaczy, o co naprawdę chodzi, pokazuje do trzech opcji z kosztami i wskazuje **jedną** rekomendację. Zadanie zostawia tobie.

| Komenda | Zakres |
|---|---|
| `teacher-backend` | Django i DRF (opcjonalnie FastAPI, Flask): warstwy, modele, migracje, transakcje, Celery, ACL, pytest |
| `teacher-frontend` | React, React Native, Expo Router (opcjonalnie Angular): stan serwera i klienta, granice komponentów, re-rendery, typy, testy |
| `teacher-architecture` | granice FE i BE, kontrakt API, kiedy **nie** dzielić, infra, Docker i Taskfile, odwracalność decyzji, ADR |
| `teacher-agent` | praca z agentami: skille, worktree, delegacja, `/goal` vs `/loop`, pisanie promptów, spinanie komend kita w jeden przepływ |

Kontrakt: agenci `teacher-*` **nie edytują plików** i nie dają gotowego kodu do wklejenia. Szkic ma najwyżej 20 linii. Nazywają wzorce po imieniu i mówią wprost, gdy koncepcja jest zła. Czytają `get_bundle` i `get_overlay`, więc uczą na twoim stacku.

```text
/kit-ai:teacher-backend czy walidację ceny dać do serializera czy do serwisu
/kit-ai:teacher-frontend                 # bez argumentu: o tym, co masz w git diff
/kit-ai:teacher-architecture czy dodać Redisa pod cache koszyka
```

## Subagenty: cross-review w dwóch oknach

`subagent-backend` i `subagent-frontend` pracują w dwóch oknach naraz. Każdy przegląda swoją część. Raport z jednego okna wklejasz do drugiego.

```text
/kit-ai:subagent-backend przejrzyj zmiany…
# potem wklej raport do /kit-ai:subagent-frontend w drugim oknie
```

## `cleanup`

Szuka zbędnych plików zostawionych po weryfikacji: skryptów scratch, testów ad hoc, zrzutów. Przed usunięciem **pyta o potwierdzenie**. Uruchom go przed `git-commit`, gdy podejrzewasz śmieci w drzewie.

## `issue-stats` i `pr-stats`

- `issue-stats` analizuje otwarte issues pod kątem gotowości do pracy autonomicznej. Daje raport statusu, roadmapę i segmentację.
- `pr-stats` sprawdza otwarte PR-y: stan CI, ryzyka, konflikty i blokery merge.

Te same raporty z terminala: `kit-ai issue stats` i `kit-ai pr stats`.

## `kit-retro`

Skill, który klasyfikuje znaleziska z analizy sesji: do kitu, projektu, agenta albo zewnętrzne. Nic nie zmienia i nie zakłada issue bez akceptacji. Szczegóły i komendy `kit-ai retro`: [Retro](../diagnostyka/retro.md).
