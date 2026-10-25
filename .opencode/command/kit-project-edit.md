---
description: "Jedna zmiana w konfiguracji projektu bez całego wywiadu — Stack per Tier, codegen, klienci, język albo sekcja .ai/project.md, z podglądem i reloadem; spór z treścią modułu kita zapisany jako odstępstwo w .ai/project.md; albo naprawa zgłoszeń doctora w overlayu i bloku project:rules w BUGBOT.md. Use when /kit-project-edit, 'zmień web na angular', 'nie zgadzam się z modułem X', 'napraw zgłoszenia doctora'. Wywołuj jako /kit-project-edit."
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne

Przestrzegaj `AGENTS.md`. Zapisujesz **wyłącznie** `.ai/project.profile.yaml`,
`.ai/project.md` i blok `project:rules` w `BUGBOT.md` w repo projektu. Nie edytujesz `modules/`,
`manifest.yaml` ani plików kita — także wtedy, gdy repo kita jest pod ręką.
Bez akceptacji podglądu nic nie zapisujesz.

# /kit-project-edit — jedna odpowiedź, odstępstwo albo naprawa doctora

Trzy tryby. Rozpoznaj go z polecenia; niejasne → zapytaj jednym zdaniem.

| Tryb | Sygnał | Wynik |
| --- | --- | --- |
| **A — jedna odpowiedź** | „zmień web na angular", „codegen none", „dodaj klienta codex", „ścieżka backendu to api/" | Jedna zmiana w Profilu albo `.ai/project.md` + reload |
| **B — odstępstwo** | „nie zgadzam się z X w module Y", „u nas robimy to inaczej" | Wpis w `## Odstępstwa od modułów` w `.ai/project.md` |
| **C — naprawa doctora** | „napraw zgłoszenia doctora", „doctor", „posprzątaj ścieżki w regułach" | Poprawki w `.ai/project.md` i bloku `project:rules` w `BUGBOT.md` + podgląd |

## `--help` / `help` / `-h`

```markdown
# /kit-project-edit — pomoc

/kit-project-edit "zmień web na angular"        Tryb A: jedna odpowiedź → podgląd → zapis → reload
/kit-project-edit "nie zgadzam się z …"         Tryb B: grillowanie → odstępstwo w .ai/project.md
/kit-project-edit "napraw zgłoszenia doctora"   Tryb C: doctor → podgląd poprawek → zapis
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
   | Model przejęcia ticketu nocnego (#257) | Profil: `models.claude.takeover` | `haiku` \| `sonnet` \| `opus` \| `fable` (tylko Claude; brak = model sesji) |
   | Pytanie tak/nie (docker, taskfile, ci-cd, …) | Profil `include:` / `patterns:` | Wpisy z linii `Zapis` pytania |
   | Ścieżka Tieru, inna sekcja | `.ai/project.md` | Tekst użytkownika |
   | `server:` (server-guard: `guard`, `deny`, `allow`) | Profil, sekcja `server` | `guard: auto` albo `off`; `deny`/`allow`: dosłowne wywołania (wyjątki `allow` wygrywają z deny) |

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
   w tym samym podglądzie jego linię `- <tier>:` z `## Ścieżki` w `.ai/project.md` oraz linie
   pytań, które przestają być aktywne (`routes-web` / `routes-mobile`, `design-tokens` gdy
   web i mobile są `none` — `list_questions` po zmianie). Tier `none` → Stack web/mobile:
   zaproponuj kolejne `/kit-project-edit` na `design-tokens` i `routes-*` z wykryciem
   z `detect:` katalogu.
3. **Zapis** jednej linii (komentarze i reszta pliku nietknięte) → MCP
   `reload_workspace(dry_run=True)`; błąd → przywróć oryginał, pokaż błąd. OK →
   `reload_workspace(dry_run=False)`. Zmiana tylko w `.ai/project.md` → bez reloadu
   (serwer czyta overlay na żywo).
4. **Etykiety** — gdy Tier zmienił się z `none` na Stack albo do `clients` doszedł `claude`
   (przy Tierze web/mobile — etykiety `design: *`): MCP `ensure_labels(dry_run=True)`, lista
   nowych etykiet, zgoda → `ensure_labels(dry_run=False)`. Brak zgody → pomiń i podaj
   `kit-ai labels --apply`. Usunięcie `claude` niczego nie kasuje — jedna linia, że etykiety
   `design: *` zostają bez użycia.

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

## Tryb C — napraw zgłoszenia doctora

Doctor nie blokuje reloadu: pokazuje `doctor: OSTRZEŻENIE <plik>:<linia> — …` i
`doctor: INFO …`. Ten tryb zamienia zgłoszenia w poprawki reguł — nie w kod.

1. **Raport.** `kit-ai doctor` z terminala albo MCP `check_kit_status` (ma sekcję
   `doctor:`). Brak zgłoszeń → jedna linia i koniec. Nie zgaduj treści raportu.
2. **Podział zgłoszeń:**

   | Zgłoszenie | Gdzie poprawka | Jak |
   | --- | --- | --- |
   | Ścieżka w `.ai/project.md` | overlay: właściwa sekcja albo `## Ścieżki` | Podmień na ścieżkę, która istnieje w drzewie; klucz Tieru bez katalogu → usuń linię albo popraw |
   | Ścieżka w bloku `project:rules` w `BUGBOT.md` | tylko ten blok | Podmień/usuń linię; blok przechodzi przez reload bez zmian |
   | Ścieżka w szablonowej części `BUGBOT.md` | **nie edytuj** — reload nadpisze | Jeśli reguła ma zostać, dopisz jej wersję z właściwą ścieżką do `project:rules` |
   | Ścieżka w `AGENTS.md` / `CODING_STANDARDS.md` | poza zakresem trybu | Pokaż propozycję i poproś o ręczną decyzję — tych plików ten tryb nie zapisuje |
   | Komenda bez agenta/komendy/skilla | overlay albo `project:rules` | Usuń odwołanie **albo** — gdy komenda ma istnieć w kicie — daj szkic `/create-task` (nie edytuj `templates/`) |
   | `INFO` o pakiecie workspace'u | overlay | Dopisz pakiet (albo jego katalog nadrzędny) do `## Ścieżki` / sekcji struktury |

   Nie wiesz, gdzie plik się przeniósł → zapytaj. Zgadywanie ścieżki zamieni jeden
   fałszywy alarm w drugi.
3. **Podgląd** — diff per plik, tylko zmieniane linie:

   ```text
   .ai/project.md
   - - backend: `backend/`
   + - backend: `api/`
   BUGBOT.md (blok project:rules)
   - Jeśli zmiana dotyka `backend/apps/auth/` …
   + Jeśli zmiana dotyka `api/apps/auth/` …
   Akceptujesz? [tak / anuluj]
   ```

4. **Zapis** po akceptacji — tylko wskazane linie w overlayu i/lub bloku
   `project:rules`. Overlay i `BUGBOT.md` czyta się na żywo, więc reload nie jest
   potrzebny; nie ruszaj Profilu. Po zapisie pokaż ponowny wynik `doctor` (może zostać
   zgłoszenie spoza zakresu, np. w `AGENTS.md`).
5. **Zakazy.** Nie edytuj szablonowych sekcji `BUGBOT.md` (poza blokiem), `AGENTS.md`,
   `CODING_STANDARDS.md`, `templates/`, `modules/`. Jedno wywołanie = jedna partia
   zgłoszeń; kolejna partia → kolejne `/kit-project-edit`.

## Raport

```markdown
## /kit-project-edit OK
- Tryb: A | B | C
- Zmiana: <plik> — <linia przed> → <linia po>
- Reload: tak (N/M/K) | nie (tylko overlay)
- Doctor: <ile zgłoszeń zostało i gdzie>
- Dalej: <zrestartuj okno | /create-task w repo kita | nic>
```

## Zakazy

- Zapis do `modules/`, `manifest.yaml`, plików kita albo poza repo projektu — nigdy.
- Więcej niż jedna zmiana na wywołanie (kolejna → kolejne `/kit-project-edit`); wyjątek:
  linia `## Ścieżki` usuwana razem z Tierem → `none`.
- Zapis bez podglądu i akceptacji.
