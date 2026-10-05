---
mode: "agent"
description: "Jedna zmiana w konfiguracji projektu bez całego wywiadu — Stack per Tier, codegen, klienci, język albo sekcja .ai/project.md, z podglądem i reloadem; albo spór z treścią modułu kita zapisany jako odstępstwo w .ai/project.md. Use when /kit-project-edit, 'zmień web na angular', 'nie zgadzam się z modułem X'. Wywołuj jako /kit-project-edit."
---

## Reguły wspólne

Przestrzegaj `AGENTS.md`. Zapisujesz **wyłącznie** `.ai/project.profile.yaml` i
`.ai/project.md` w repo projektu. Nie edytujesz `modules/`, `manifest.yaml` ani plików kita —
także wtedy, gdy repo kita jest pod ręką. Bez akceptacji podglądu nic nie zapisujesz.

# /kit-project-edit — jedna odpowiedź albo odstępstwo od modułu

Dwa tryby. Rozpoznaj go z polecenia; niejasne → zapytaj jednym zdaniem.

| Tryb | Sygnał | Wynik |
| --- | --- | --- |
| **A — jedna odpowiedź** | „zmień web na angular", „codegen none", „dodaj klienta codex", „ścieżka backendu to api/" | Jedna zmiana w Profilu albo `.ai/project.md` + reload |
| **B — odstępstwo** | „nie zgadzam się z X w module Y", „u nas robimy to inaczej" | Wpis w `## Odstępstwa od modułów` w `.ai/project.md` |

## `--help` / `help` / `-h`

```markdown
# /kit-project-edit — pomoc

/kit-project-edit "zmień web na angular"        Tryb A: jedna odpowiedź → podgląd → zapis → reload
/kit-project-edit "nie zgadzam się z …"         Tryb B: grillowanie → odstępstwo w .ai/project.md
/kit-project-edit --help                         Ta pomoc

Cały wywiad od zera: /kit-project-begin
```

## Tryb A — jedna odpowiedź

1. **Cel.** MCP `get_language`, `list_questions`; przeczytaj Profil i `.ai/project.md`
   (zapamiętaj oryginał). Ustal jeden klucz:

   | Co | Gdzie | Dozwolone wartości |
   | --- | --- | --- |
   | Stack per Tier (`backend`/`web`/`mobile`), wariant | Profil | Opcje pytania z `list_questions` + `none` |
   | `codegen` | Profil | `orval` \| `none` \| `graphql` |
   | `clients` | Profil | `all` albo lista z MCP `get_clients` |
   | `language` | Profil | `pl` \| `en` |
   | Pytanie tak/nie (docker, taskfile, ci-cd, …) | Profil `include:` / `patterns:` | Wpisy z linii `Zapis` pytania |
   | Ścieżka Tieru, inna sekcja | `.ai/project.md` | Tekst użytkownika |

   Wartość spoza dozwolonych → pokaż listę, nie zgaduj. Brak Stacka w katalogu → `none` +
   podpowiedź `/create-task` w repo kita.
2. **Podgląd** — tylko zmieniane linie:

   ```text
   .ai/project.profile.yaml
   - web: react
   + web: angular
   Skutek reloadu: agenci Tierów bez zmian; get_bundle web → moduły angular
   Akceptujesz? [tak / anuluj]
   ```

   Skutki do nazwania wprost: zmiana Tieru na/z `none` dodaje lub usuwa agentów Tieru;
   zmiana `clients` **usuwa** pliki kita klientów spoza listy (własne pliki zostają);
   zmiana Tieru może włączyć pytania zależne (np. `codegen`, warianty) — wymień je i podaj
   gotowe kolejne `/kit-project-edit` (jedna zmiana na wywołanie); Tier → `none` usuwa
   w tym samym podglądzie jego linię `- <tier>:` z `## Ścieżki` w `.ai/project.md`.
3. **Zapis** jednej linii (komentarze i reszta pliku nietknięte) → MCP
   `reload_workspace(dry_run=True)`; błąd → przywróć oryginał, pokaż błąd. OK →
   `reload_workspace(dry_run=False)`. Zmiana tylko w `.ai/project.md` → bez reloadu
   (serwer czyta overlay na żywo).

## Tryb B — odstępstwo od modułu

1. **Źródło.** Znajdź moduł i dokładny fragment: MCP `get_bundle` / `get_module <id>`.
   Zacytuj zdanie, z którym jest spór, z Module ID. Nie znajdziesz → powiedz to, nie
   wymyślaj treści modułu.
2. **Grillowanie** — maks. trzy pytania, po jednym:
   - Co konkretnie robicie zamiast tego? (przykład z repo, plik)
   - Dlaczego — ograniczenie tego repo czy przekonanie, że moduł jest zły dla wszystkich?
   - Co się zepsuje, jeśli agent zrobi według modułu?
   Odpowiedź „bo tak wolę" bez skutku → powiedz wprost, że to preferencja, i zapisz ją
   jako taką.
3. **Decyzja:**
   - **Dotyczy tego repo** → wpis w `.ai/project.md` (podgląd → akceptacja → zapis):

     ```markdown
     ## Odstępstwa od modułów

     - `stack:django:views` — zamiast <X z modułu> robimy <Y>, bo <powód>. Przykład: `<plik>`.
     ```

     Sekcji nie ma → dodaj ją na końcu pliku. Overlay ma pierwszeństwo przed bundlem, więc
     wpis wygrywa z modułem od razu, bez reloadu.
   - **Dotyczy wszystkich projektów** → nie zapisujesz nic w module. Daj gotowy szkic do
     `/create-task` w repo kita (tytuł EN, cytat z modułu, propozycja zmiany, uzasadnienie).
     Na życzenie dodatkowo lokalne odstępstwo jak wyżej, do czasu zmiany w kicie.

## Raport

```markdown
## /kit-project-edit OK
- Tryb: A | B
- Zmiana: <plik> — <linia przed> → <linia po>
- Reload: tak (N/M/K) | nie (tylko overlay)
- Dalej: <zrestartuj okno | /create-task w repo kita | nic>
```

## Zakazy

- Zapis do `modules/`, `manifest.yaml`, plików kita albo poza repo projektu — nigdy.
- Więcej niż jedna zmiana na wywołanie (kolejna → kolejne `/kit-project-edit`); wyjątek:
  linia `## Ścieżki` usuwana razem z Tierem → `none`.
- Zapis bez podglądu i akceptacji.
