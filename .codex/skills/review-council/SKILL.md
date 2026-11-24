---
name: review-council
description: Rada trzech delegatów dyskutujących w rundach o zmianie lub architekturze. Use when /review-council, council, rada modeli. Wywołuj jako /review-council.
---

Język odpowiedzi, hand-backu i opisu PR: z MCP `get_language` (Profil), niezależnie od języka wejścia.

## Reguły wspólne (obowiązkowe)

Przestrzegaj `AGENTS.md` oraz reguł git i review. Standardy projektu czytasz z `CODING_STANDARDS.md`. Rada nie zastępuje `/review-bugbot` przed pushem.

## Przed radą

1. Doprowadź implementację do stanu, który chcesz recenzować: odpowiedz na otwarte uwagi PR, napraw znane błędy, uruchom sprawdzenia. Nie odkładaj znanych poprawek na czas po recenzjach.
2. Gdy użytkownik chce odrzucić implementację i szukać nowych pomysłów, nie poprawiaj kodu, który zostanie zastąpiony.

## Skład rady

1. Wywołaj MCP `get_council`. Zwraca liczbę rund oraz listę delegatów w kształcie `target` dla `delegate_task` wraz z `supp-target`.
2. Poprawny skład: trzej członkowie podani przez użytkownika w Profilu (`council.members`). Użyj tych członków bez zmian.
3. Brak składu w Profilu lub uwagi o błędzie: nie zgaduj domyślnych flagowców. Zgłoś to użytkownikowi w hand-backu z informacją o skonfigurowaniu bloku `council:` przez `/kit-project-edit`.
4. Członkowie nazwani przez użytkownika w tej rozmowie mają pierwszeństwo przed Profilem.
5. Gdy członek jest niedostępny lub `target` zawiedzie: użyj wpisu `supp-target`. Jeśli brak `supp-target` lub on także zawiedzie — członek odpada z uwagą w podsumowaniu.

## Uruchomienie (T3 Code)

1. Przed pierwszym `delegate_task` wywołaj `orchestrator_capabilities`.
2. Liczba rund: z `get_council` (`council.rounds`, domyślnie 2).
3. Runda N (od 1 do N):
   - Dla każdego aktywnego członka wyślij jedno `delegate_task`, wszystkie równolegle:
     - `target`: `providerInstanceId`, `model` i `options` z wpisu członka (w razie niepowodzenia startu: `supp-target`);
     - `role: review`, `mode: async`, `isolation: shared`;
     - `clientRequestId`: `council-r<runda>-<nazwa_członka>`, żeby ponowienie nie tworzyło drugiego delegata;
     - `task`:
       - Runda 1: zadanie, recenzowany diff/kod, pytania projektowe, wymóg pracy read-only, format odpowiedzi (ustalenia, niezgodności, rekomendowane kroki).
       - Runda 2+: zadanie oraz odpowiedzi pozostałych członków z rundy N-1. Członek odnosi się do argumentów innych modeli, wskazuje punkty sporne i rewiduje swoje stanowisko.
   - Każda kolejna runda to nowe `delegate_task`, nigdy `t3_thread_send`.
4. Poza T3 Code: użyj narzędzi subagentów harnessu. Przekaż parametry członka, jeśli harness je wspiera; w przeciwnym razie odnotuj to w hand-backu.
5. Nie edytuj plików w trakcie trwania rundy delegatów.

## Podsumowanie i wynik

- Rada dyskutuje, nie punktuje (brak ocen 0–10).
- Po zakończeniu wszystkich rund zbierz i podsumuj:
  - **Zgodności:** w czym wszyscy członkowie rady byli zgodni.
  - **Różnice zdań:** kwestie sporne, różne perspektywy lub trade-offy zgłoszone przez modele.
  - **Rekomendowane kroki:** konkretne, uporządkowane działania wynikające z dyskusji.
  - **Uwagi o składzie:** ewentualne użycie `supp-target` lub odpadnięcie członka.
- Gdy praca kończy się PR i PR jest otwarty: edytuj opis PR i dopisz sekcję `## Council debate` przed stopką. Bez PR: przedstaw podsumowanie w odpowiedzi końcowej.
