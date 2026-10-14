# Frontend — tokeny, sekcja / strona i spec layoutu

Wspólny dla każdego Stacka web i mobile. Cel: działający ekran (dane, stany, formularze,
nawigacja) w neutralnym wyglądzie, a późniejsza zmiana layoutu nie rusza logiki. Ścieżki
z `.ai/project.md ## Ścieżki`: `design-tokens` (źródło tokenów), `routes-web` /
`routes-mobile` (katalog plików route'ów) — ścieżki od roota repo (w monorepo np.
`frontend/web/app/`). Brak klucza — reguły działają, bez wskazania ścieżki.

## Tylko tokeny

Kolory, fonty, rozmiary, spacing, radiusy i cienie wyłącznie przez tokeny: CSS custom
properties, theme frameworka albo pakiet tokenów — źródło `design-tokens`. Żadnych literałów
w komponentach (`#333`, `16px`, `font-family: …`, `rgba(…)`). Brakuje tokenu → dodaj go
w źródle tokenów, nie wpisuj wartości w komponencie. Przy specu: token z sekcji „Nowe /
zmienione tokeny” dodajesz; tokenu spoza speca i źródła — hand-back.

## Sekcja / strona

- **Plik route'a** (`routes-web` / `routes-mobile`) = routing, kompozycja sekcji i layout
  strony. Nie wywołuje API i nie trzyma logiki.
- **Komponent sekcji** (`features/<feature>/`) = dane, hooki API, stany (ładowanie, pusto,
  błąd), formularze. Nie ustala swojego położenia na stronie: bez marginesów zewnętrznych,
  gridu rodzica i `position` względem strony.
- Zmiana layoutu = zmiana pliku route'a + CSS layoutu. Sekcje zostają.
- Angular: konfiguracja `Routes` (`app.routes.ts`) to routing, a „plik route'a” to komponent
  strony wskazany w `Routes` — on komponuje sekcje i niesie layout; serwisy i komponenty
  sekcji siedzą w `features/`.

## Layout domyślny

Brak speca dla bieżącego issue → jedna kolumna, mobile-first, maksymalna szerokość i odstępy
z tokenów. Bez wymyślania „ładnego” layoutu — wygląd przyjdzie ze speca.

## Spec layoutu — `docs/design/<N>.md`

Spec istnieje dla bieżącego issue (na bazie albo na już wypchniętym branchu issue) → layout
**wyłącznie** według speca. Rozbieżność (sekcji nie da się ułożyć jak w specu, token spoza
speca i źródła, sprzeczność z kodem) = hand-back needs-human, nie improwizacja.

Format (agent piszący spec bierze go stąd; w projekcie nie ma pliku szablonu):

```markdown
# Layout: <ekran> (#<N>)

- Źródło: <link do artefaktu / pliku źródłowego albo „opis ręczny”>
- Route: <ścieżka pliku route'a per Tier>
- Referencja: <docs/design/<N>.png albo .html — eksport, opcjonalnie>

## Breakpointy
| Szerokość | Układ |
|-----------|-------|
| < 640 | … |
| ≥ 1024 | … |

## Sekcje (kolejność i położenie)
| Sekcja (komponent) | Obszar | Uwagi |
|--------------------|--------|-------|

## Nowe / zmienione tokeny
<nazwa: wartość — albo „brak”>

## Poza zakresem
<co ze źródła świadomie pomijamy>
```

Spec opisuje układ słowami i tabelą — tyle przeczyta każdy wykonawca. Eksport HTML/PNG to
tylko dodatkowa referencja.

### Spec trafia do repo zwykłym PR-em

Gałąź bazowa jest chroniona, więc spec nie idzie commitem prosto na nią: `/git-start` →
commit `docs(design): layout spec for #<N>` → `/git-end` → merge. Po merge'u spec leży na
bazie i widzi go każdy wykonawca. Branch issue już istnieje i jest wypchnięty → spec może być
jego pierwszym commitem.
