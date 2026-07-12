# Workflow pracy z AI w olivin-app

## Cel

Ten dokument opisuje praktyczny sposób pracy z agentami AI w projekcie `olivin-app`.
Łączy lokalne zasady repo z dobrymi praktykami podejścia podobnego do `obra/superpowers`, ale bez ślepego kopiowania zewnętrznego workflow.

## Zasada nadrzędna

AI ma pomagać w analizie, planowaniu i implementacji, ale nie może zastępować realnej analizy repozytorium.
Najpierw repo, potem diagnoza, potem plan, na końcu kod.

## Narzędzia AI

Instrukcje projektowe pisz neutralnie względem klienta AI. Ten sam workflow ma działać dla Codex, GitHub Copilot, Gemini w Antigravity, ACP clienta dla Hermesa, Continue z OpenRouter, OpenCode, Perplexity ze stackiem oraz Cursor.

Źródłem prawdy dla agentów jest repozytorium:

- `AGENTS.md` — nadrzędne zasady dla agentów i workflow repo-first,
- `stack:django-drf:backend-standard` — wspólny standard tworzenia kodu backendu (Django/DRF),
- `.github/copilot-instructions.md` — dodatkowe wskazówki dla Copilota i agentów IDE,
- `.github/instructions/*.instructions.md` — lokalne instrukcje dla backendu i frontendu,
- `Taskfile.yml` oraz `taskfiles/*.yml` — realne komendy projektu.

Nie zapisuj osobnych, sprzecznych reguł dla każdego narzędzia. Jeśli klient AI obsługuje własny plik konfiguracyjny, powinien odsyłać do powyższych dokumentów albo streszczać je bez zmiany znaczenia.

## Podstawowy przepływ pracy

### 1. Analiza kontekstu

Przed każdą odpowiedzią techniczną agent powinien:

- sprawdzić realne pliki i katalogi,
- wskazać ścieżki związane z problemem,
- oddzielić fakty od założeń,
- dopiero potem formułować rekomendacje.

### 2. Dobór trybu pracy

Dobierz tryb pracy do zadania i nazwij go wprost, jeśli zmiana nie jest trywialna.
Tryb ma pomagać dobrać głębokość analizy, a nie tworzyć ciężką procedurę przy każdej drobnej poprawce.

#### Bugfix

Użyj trybu bugfix, gdy trzeba:

- ustalić objaw,
- znaleźć przyczynę źródłową,
- zaproponować minimalną poprawkę,
- ocenić ryzyko regresji.

Typowy przebieg:

1. Odtwórz albo opisz objaw na podstawie repo i komunikatów błędu.
2. Znajdź najmniejszy obszar kodu odpowiedzialny za problem.
3. Napraw przyczynę, nie tylko efekt uboczny.
4. Dobierz test lub kontrolę potwierdzającą poprawkę.

#### Feature

Użyj trybu feature, gdy trzeba:

- wskazać miejsce funkcjonalności w architekturze,
- ocenić wpływ na frontend, backend i API,
- zaproponować etapowy plan wdrożenia.

Typowy przebieg:

1. Ustal, czy funkcja dotyczy frontendu, backendu, API czy kilku warstw naraz.
2. Wskaż konkretne katalogi i pliki, w których powinna powstać zmiana.
3. Zaprojektuj kontrakt danych, walidację, permissions, cache i stany UI, jeśli mają znaczenie.
4. Po zmianach API uwzględnij `task ovral:generate` i `task lints:frontend:typecheck`.

#### Refactor

Użyj trybu refactor, gdy trzeba:

- poprawić strukturę kodu bez zmiany zachowania biznesowego,
- zmniejszyć coupling,
- poprawić testowalność,
- uprościć przepływ danych.

Typowy przebieg:

1. Nazwij problem jakościowy, który refaktor rozwiązuje.
2. Ogranicz zakres do najmniejszej sensownej zmiany.
3. Zachowaj publiczny kontrakt, jeśli użytkownik nie prosi o zmianę zachowania.
4. Zweryfikuj, że zachowanie nie zmieniło się przypadkiem.

#### Documentation / Workflow

Użyj tego trybu, gdy zmieniasz instrukcje, README, Taskfile, CI albo konfigurację narzędzi.

Typowy przebieg:

1. Porównaj instrukcje z realnymi plikami i taskami.
2. Usuń sprzeczności i przestarzałe komendy.
3. Preferuj jedno źródło prawdy oraz krótkie odsyłacze zamiast kopiowania pełnych reguł do wielu plików.
4. Sprawdź, czy różni agenci AI dostaną wystarczający kontekst bez znajomości historii rozmowy.

## Jak korzystać z podejścia podobnego do superpowers

Z podejścia podobnego do `obra/superpowers` warto zachować:

- lepszą diagnozę problemu,
- planowanie większych zmian,
- systematyczne debugging i verification-before-completion,
- myślenie w trybie minimalnej, bezpiecznej zmiany.

Nie warto kopiować bezpośrednio:

- obcych założeń o strukturze projektu,
- zbyt ciężkiego procesu dla małych zmian,
- sztywnego workflow tam, gdzie lokalna poprawka jest wystarczająca.

## Reguły językowe

W projekcie obowiązuje:

- język odpowiedzi: polski,
- język docstringów: polski,
- język nazw technicznych: angielski.

## Reguły jakości

Każda odpowiedź techniczna powinna zawierać:

1. krótką diagnozę,
2. wskazanie plików,
3. listę ryzyk,
4. plan zmian,
5. informację, czego nie udało się potwierdzić.

## Testy, linty i typecheck

Przed zaproponowaniem albo uruchomieniem komendy zawsze sprawdź `Taskfile.yml` i właściwy plik w `taskfiles/`.

Najważniejsze taski kontrolne:

- `task test:backend-local -- <ścieżka>` — szybkie testy backendu bez integracyjnych,
- `task test:backend-local-unit -- <ścieżka>` — testy jednostkowe backendu,
- `task test:backend-integration -- <ścieżka lub marker>` — testy integracyjne backendu,
- `task test:backend-cmd -- <ścieżka>` — wybrane testy backendu w kontenerze,
- `task test:backend` — pełne testy backendu w środowisku testowym,
- `task lints:backend:ruff` — Ruff check i format backendu,
- `task lints:backend:ruff:check` — Ruff check i format check bez modyfikowania plików,
- `task lints:backend:typecheck` — MyPy backendu,
- `task lints:frontend:lint` — lint Expo / React Native z poprawkami,
- `task lints:frontend:lint:check` — lint Expo / React Native bez modyfikowania plików,
- `task lints:frontend:typecheck` — TypeScript typecheck frontendu,
- `task lints:frontend:format` — formatowanie frontendu Prettierem,
- `task lints:frontend:format:check` — sprawdzenie formatowania frontendu bez modyfikowania plików.

Dobierz kontrolę do zakresu zmiany. Dla drobnej poprawki lokalnej wystarczy celowany test lub typecheck; dla zmian kontraktu API uwzględnij `task ovral:generate` i `task lints:frontend:typecheck`.

## Kiedy nie komplikować procesu

Nie uruchamiaj rozbudowanego procesu planowania, jeśli:

- problem jest lokalny i dobrze rozpoznany,
- poprawka dotyczy jednego lub kilku blisko powiązanych plików,
- ryzyko regresji jest niskie,
- nie ma zmiany kontraktu API ani zmiany architektury.

## Kiedy rozszerzyć analizę

Rozszerz analizę, jeśli zmiana dotyka:

- przepływu danych frontend-backend,
- auth,
- płatności,
- kontraktu API,
- cache i invalidation,
- side effectów lub operacji asynchronicznych,
- wielu modułów naraz.
