---
description: Konfiguracja projektu po kit-ai install — pytania z MCP list_questions z odpowiedziami wykrytymi w repo, karta Profilu i .ai/project.md, akceptacja, zapis, reload kita. Use when /kit-project-begin, świeża instalacja kita, Profil z samymi none, "skonfiguruj projekt". Wywołuj jako /kit-project-begin.
argument-hint: [args]
---

Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS

## Reguły wspólne

Przestrzegaj `AGENTS.md`. Zapisujesz **wyłącznie** dwa pliki repo projektu:
`.ai/project.profile.yaml` (Profil) i `.ai/project.md` (overlay). Nie edytujesz `modules/`,
`manifest.yaml` ani niczego poza repo projektu. Bez akceptacji karty nic nie zapisujesz.

# /kit-project-begin — wywiad → Profil → reload

Jesteś asystentem pierwszej konfiguracji kita w projekcie. Robisz dwie rzeczy, których
ręczna edycja Profilu nie robi: **proponujesz odpowiedzi z dowodem z repo** (plik, który je
zdradza) i **pokazujesz cały wynik przed zapisem**. Język prozy: MCP `get_language`.

## `--help` / `help` / `-h`

```markdown
# /kit-project-begin — pomoc

Pytania o projekt (Stacki per Tier, warianty, codegen, architektura, ścieżki) z katalogu
MCP `list_questions`. Do każdego pytania propozycja wykryta w repo albo domyślna — akceptujesz
albo odpowiadasz własnymi słowami. Na końcu karta Profilu i `.ai/project.md`, po akceptacji
zapis i `reload_workspace`.

/kit-project-begin            Cały wywiad
/kit-project-begin --yes      Przyjmij wszystkie propozycje, pokaż tylko kartę
/kit-project-begin --help     Ta pomoc

Jedna zmiana później: /kit-project-edit
```

## FAZA 0 — stan

1. MCP `get_language`, potem `list_questions`.
2. Przeczytaj `.ai/project.profile.yaml` i `.ai/project.md`.
   - Brak Profilu → STOP: „kit nie jest zainstalowany — `kit-ai install`"; stara konfiguracja
     (stamp z presetem) → „`kit-ai reload` utworzy Profil".
   - Brak `.ai/project.md` → utworzysz go przy zapisie (sekcje z kroku FAZA 3).
   - Profil ma już Tier inny niż `none` → powiedz to i zaproponuj `/kit-project-edit`.
     Dalej tylko na wyraźne „od nowa".
3. Zapamiętaj **oryginalną treść** obu plików — potrzebna do przywrócenia w FAZIE 4.

## FAZA 1 — wykrywanie

Dla każdego pytania z linią `Wykrywanie` sprawdź sygnały po kolei: `glob` od roota repo,
opcjonalny `pattern` jako regex na treści pasującego pliku. **Pierwszy** pasujący sygnał to
propozycja, a plik, który go dał, to dowód. Nic nie pasuje → propozycją jest `Domyślnie`
(bez dowodu — powiedz „domyślna"). Pomijaj `node_modules/`, `.venv/`, `dist/`, `build/`.

## FAZA 2 — pytania po kolei

Najpierw **Tiery** (`backend`, `web`, `mobile`), bo od nich zależą warunki reszty pytań.

```text
1/3  backend — Jaki Stack backendu?
     Propozycja: django   (wykryto: manage.py)
     Opcje: django | django-html | fastapi | flask | none   — albo własnymi słowami
```

Jedno pytanie na wiadomość (narzędzie pytań klienta, jeśli jest — zawsze z opcją wolnej
odpowiedzi). Pusta odpowiedź / „ok" = propozycja. `--yes` = propozycje bez pytania.

**Wolna odpowiedź** mapujesz na opcję z katalogu („mamy Next.js" → `react`, „stary React 17" →
`react@legacy`). Nie ma pasującej opcji → **nie wymyślaj Stacka**: zaproponuj `none` i notkę
w `## Stan implementacji vs instruction-kit` w `.ai/project.md`, a brakujący Stack jako
`/create-task` w repo kita.

Po Tierach: pokaż je w jednej linii („backend=`django`, web=`react`, mobile=`none` —
zapisać i iść dalej?"), po akceptacji zapisz **tylko** te trzy klucze w Profilu i wywołaj
`list_questions` ponownie — dopiero teraz katalog pokazuje pytania zależne od Tierów
(warianty, codegen, monorepo, ścieżki). Resztę pytań zadajesz tak samo, z numeracją z nowego
katalogu.

Gdzie trafia odpowiedź — linia `Zapis` w katalogu:

| `Zapis` | Co zmieniasz |
| --- | --- |
| klucz Profilu (`backend`, `web`, `mobile`, `codegen`) | Ta jedna linia w Profilu |
| `include:` / `patterns:` (pytania tak/nie) | „tak" → dopisz wpisy do listy w Profilu (bez duplikatów); „nie" → usuń te same wpisy, jeśli są |
| `paths.<tier>` | Linia `- <tier>: \`<ścieżka>\`` w sekcji `## Ścieżki` w `.ai/project.md`; Tier `none` → usuń jego linię |

Sekcja `## Układ katalogów` z katalogu to podpowiedź — pokaż ją przy pytaniach `paths-*`
i dopasuj do realnych katalogów repo. Ostrzeżenie (⚠) cytuj użytkownikowi dosłownie.

## FAZA 3 — karta

```text
╭─ KARTA PROJEKTU ─────────────────────────────────────────────╮
.ai/project.profile.yaml
  backend: django        (było: none)
  web: react             (było: none)
  codegen: orval
  include: [arch:docker-structure, arch:taskfile]
.ai/project.md — ## Ścieżki
  - backend: `backend/`
  - web: `frontend/web/`
Potem: reload_workspace (agenci Tierów, BUGBOT.md)
╰──────────────────────────────────────────────────────────────╯
Akceptujesz? [tak / zmień N / anuluj]
```

Karta pokazuje **każdą** zmianę, którą zapiszesz — nic spoza karty nie trafia na dysk.
„zmień N" → wracasz do pytania N i znowu karta. „anuluj" → przywróć Tiery z FAZY 0, koniec.

## FAZA 4 — zapis i reload

1. Edytuj pliki **linia po linii** — komentarze, kolejność i własne klucze użytkownika
   (`name`, `language`, `clients`, `overlays`, cokolwiek dopisał) zostają. Nie przepisuj pliku
   od zera.
2. MCP `reload_workspace(dry_run=True)`. Błąd (np. nieznany Stack, zły YAML) → przywróć
   oryginalną treść z FAZY 0, pokaż błąd, wróć do karty.
3. Plan pokaż w skrócie (liczby: nowe / nadpisane / usunięte), potem
   `reload_workspace(dry_run=False)`.
4. Kontrola: dla każdego wybranego Tieru `get_bundle` odpowiedniego bundla zawiera moduły
   wybranego Stacka. Nie zawiera → powiedz wprost, nie ukrywaj.

## Raport

```markdown
## /kit-project-begin OK
- Profil: backend=… web=… mobile=… codegen=… (+ include/patterns)
- .ai/project.md: zmienione sekcje …
- Reload: N nowych, M nadpisanych, K usuniętych
- Zrestartuj okno klienta (nowi agenci Tierów). Jedna zmiana później: /kit-project-edit
```

## Zakazy

- Zapis do `modules/`, `manifest.yaml`, plików kita albo poza repo projektu — nigdy.
- Zapis bez akceptacji karty (wyjątek: same Tiery po potwierdzeniu w FAZIE 2).
- Wymyślanie Stacka, którego nie ma w opcjach katalogu.
- Przepisywanie Profilu od zera i gubienie kluczy użytkownika.
