# Kanon inżynierski — skąd biorą się „dobre nawyki”

Moduł dla agentów uczących (`/teacher-*`). `core:external-knowledge` mówi **w jakiej kolejności** sięgać po źródła. Ten moduł mówi **po które konkretnie** i **jak ocenić, czy dane źródło jest coś warte**.

Zasada nadrzędna: rekomendacja bez uzasadnienia mechanizmem to opinia. „Bo tak jest czyściej” nie jest argumentem — user ma wyjść z rozmowy umiejąc sam ocenić następny taki wybór.

## Jak ważyć źródło

Od najmocniejszego:

1. **Kod i lockfile projektu** — jedyne źródło o tym, co jest naprawdę.
2. **Oficjalna dokumentacja w wersji z lockfile** (Context7) — nie „najnowsza”, tylko *ta*.
3. **Maintainer biblioteki** — blog, RFC, release notes, dyskusja w issue. Kto to utrzymuje, ten wie, czemu API wygląda tak, a nie inaczej.
4. **Repozytoria referencyjne o realnej adopcji** — styleguide’y i przykładowe projekty używane produkcyjnie.
5. **Kanon branżowy** — Fowler, Nygard, 12-factor. Stare, ale o rzeczach, które się nie zestarzały (granice, sprzężenie, koszt zmiany).
6. **Stack Overflow z tagiem wersji** — trop do zweryfikowania.
7. **Medium / dev.to / blogi** — trop, **nigdy** autorytet sam w sobie.

## Sygnały jakości źródła (ucz tego wprost)

- **Data i wersja.** Odpowiedź o Django 1.7 albo React sprzed hooków to archeologia, nie porada. Na SO sprawdź, czy pod zaakceptowaną odpowiedzią nie ma nowszej, wyżej ocenionej.
- **Czy autor utrzymuje to, o czym pisze.** Maintainer > konsultant > osoba, która wczoraj przeczytała docs.
- **Czy tekst pokazuje koszt, nie tylko zysk.** Artykuł bez sekcji „kiedy tego nie robić” sprzedaje, nie uczy. To najszybszy filtr na treści z Medium.
- **Czy da się to potwierdzić w oficjalnych docs.** Jeśli nie da się — to wzorzec autorski, nie standard. Wolno go używać, ale trzeba go tak nazwać.
- **Popularność ≠ trafność.** Post bywa popularny, bo jest prosty, a nie dlatego, że ma rację. Gwiazdki na GitHubie mierzą marketing i wiek repo równie mocno jak jakość.
- **Uwaga na treści generowane masowo.** Sporo dzisiejszych tutoriali to przepisane docs bez zrozumienia — poznasz po braku kompromisów, braku wersji i przykładach, które nie kompilują się w całości.

## Kanon: backend (Python / Django / DRF)

| Źródło | Czego uczy | Zastrzeżenie |
|--------|------------|--------------|
| Django docs, DRF docs | Zachowanie frameworka, ORM, transakcje, migracje | Zawsze w wersji z lockfile |
| [HackSoftware/Django-Styleguide](https://github.com/HackSoftware/Django-Styleguide) | Warstwa services/selectors, gdzie kończy się model, a zaczyna logika | Opinia jednej firmy, nie standard Django — nie wprowadzaj `services/` na siłę w małym projekcie |
| [typeddjango/django-stubs](https://github.com/typeddjango/django-stubs) | Realny stan typowania Django, konfiguracja pluginu mypy | Pokazuje też granice — czego otypować się nie da |
| [12factor.net](https://12factor.net) | Konfiguracja, sekrety, parzystość środowisk | Powstało przed konteneryzacją, część punktów czytaj przez Docker |
| Celery docs | at-least-once, retry, idempotencja | Sekcja o gwarancjach ważniejsza niż tutorial |
| Dokumentacja PostgreSQL | Izolacja, blokady, indeksy | Tu leży prawda o wyścigach, nie w warstwie ORM |

## Kanon: frontend (React / React Native)

| Źródło | Czego uczy | Zastrzeżenie |
|--------|------------|--------------|
| [react.dev](https://react.dev) — zwłaszcza [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect) | Efekt to synchronizacja z systemem zewnętrznym, nie miejsce na logikę; struktura stanu | Obowiązkowa lektura, zanim user zacznie „naprawiać” re-rendery |
| [TkDodo](https://tkdodo.eu/blog) (maintainer TanStack Query, linkowany z oficjalnych docs) | Server state vs client state, query keys, cache, testowanie | Najmocniejsze źródło o danych z API w React |
| Kent C. Dodds | Kolokacja stanu, testing trophy, „state management to nie zawsze store” | Część tekstów starsza — sprawdź, czy dotyczy hooków |
| [Testing Library — Guiding Principles](https://testing-library.com/docs/guiding-principles) | Test zachowania zamiast implementacji | Bezpośrednio uzasadnia, czemu nie testujemy stanu wewnętrznego |
| Expo docs, React Native docs | Nawigacja, platformy, uprawnienia, buildy | Zmiany co SDK — zawsze wersja z lockfile |
| TypeScript Handbook | Zawężanie typów, unie, generyki | Wzorce typowania, nie składnia dla początkujących |

## Kanon: architektura

| Źródło | Czego uczy |
|--------|------------|
| [Microservice Premium](https://martinfowler.com/bliki/MicroservicePremium.html), [Monolith First](https://martinfowler.com/bliki/MonolithFirst.html) | Dlaczego podział ma cenę i czemu prawie zawsze zaczyna się od monolitu |
| [Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html) | Jak przepisywać stopniowo, bez wielkiego resetu |
| [adr.github.io](https://adr.github.io) + „Documenting Architecture Decisions” (Nygard, 2011) | Format ADR: kontekst → decyzja → konsekwencje |
| DORA / *Accelerate* | Co naprawdę mierzy zdrowie dostarczania: lead time, częstość wdrożeń, MTTR, odsetek nieudanych zmian |
| [Conventional Commits](https://www.conventionalcommits.org), [SemVer](https://semver.org) | Konwencje, na których stoją narzędzia w tym kicie |

## Jak używać kanonu w nauczaniu

- Przy nietrywialnej rekomendacji **podaj jedno źródło** do doczytania. Jedno, nie bibliografię.
- **Nie argumentuj autorytetem.** „Fowler tak mówi” nie jest uzasadnieniem — wytłumacz mechanizm, a źródło daj jako dalszy ciąg.
- **Repo wygrywa z kanonem.** Gdy projekt robi inaczej niż styleguide, nazwij różnicę i jej koszt; nie każ przepisywać repo pod artykuł.
- **Rozdziel standard od wzorca autorskiego.** „Tak działa Django” i „tak robi HackSoft” to dwie różne siły argumentu.
- **Nie znasz wersji — sprawdź lockfile.** Rekomendacja niezgodna z zainstalowaną wersją jest gorsza niż jej brak.
