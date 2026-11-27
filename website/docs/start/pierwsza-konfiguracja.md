# Pierwsza konfiguracja projektu

Po `kit-ai install` projekt ma już pliki, ale nie ma jeszcze Profilu z wyborami. Konfigurację robi agent w kliencie AI, krok po kroku, z pytaniami.

## `/kit-ai:kit-project-begin`

Komenda podana w formie Claude Code. W innych klientach inny przedrostek, zob. [Przegląd komend](../komendy/przeglad.md).

```text
/kit-ai:kit-project-begin          # wywiad: pytania o stack, tiery, codegen, ścieżki
/kit-ai:kit-project-begin --yes    # zaakceptuj propozycje wykryte w repo
```

Przebieg:

1. Agent pobiera katalog pytań przez MCP `list_questions` i sprawdza pliki repo (np. `manage.py`, `package.json`, `Taskfile.yml`, `.github/workflows/`). Na tej podstawie proponuje odpowiedzi.
2. Pyta tylko o to, czego nie wykrył. Każda propozycja ma też wolną odpowiedź.
3. Pokazuje kartę: zawartość `.ai/project.profile.yaml` i `.ai/project.md` (z sekcjami ścieżek i komend).
4. Po akceptacji zapisuje pliki i wywołuje `reload_workspace`.
5. Jeśli brakuje etykiet GitHuba, proponuje ich założenie (`kit-ai labels --apply`).

Przykład: w repo jest `manage.py` i `requirements.txt` z `django`. Agent wpisze `backend: django` sam. Nie musisz tego ręcznie.

## Minimalny Profil

Minimum to język, klienci i Tiery. Reszta jest opcjonalna:

```yaml title=".ai/project.profile.yaml"
name: moja-appka
language: pl
clients: claude,codex
backend: django        # none | django | django-html | fastapi | flask
web: react             # none | react | react@legacy | angular | angular@rxjs | expo
mobile: none           # none | expo | react-native
codegen: orval         # orval | none | graphql
```

Pełny opis kluczy: [Profil projektu](../konfiguracja/profil.md).

## Overlay: `.ai/project.md`

Overlay zawiera fakty tylko tego repo: ścieżki, porty, nazwy zadań Taskfile, komendy testów. Agent czyta go przez `get_overlay` przed pierwszą edycją. Po pierwszym zapisie kit nie nadpisuje tego pliku. Szczegóły: [Overlay](../konfiguracja/overlay.md).

## Zmiana jednej rzeczy

```text
/kit-ai:kit-project-edit "zmień web na angular"
/kit-ai:kit-project-edit "nie zgadzam się z modułem X"
/kit-ai:kit-project-edit "napraw zgłoszenia doctora"
```

Każda zmiana pokazuje podgląd przed zapisem. Ręczna edycja `.ai/project.profile.yaml` też działa, ale wtedy uruchom `kit-ai reload`.

## Po zapisie

1. Zrestartuj klienta.
2. Uruchom `kit-ai doctor`. Ostrzeżenie oznacza, że reguła wskazuje ścieżkę, której nie ma w repo. Zob. [Doctor](../diagnostyka/doctor.md).
