# `/teacher-frontend` — React / RN / Expo Router

> Prywatne notatki z użycia. Źródło: `.claude/commands/teacher-frontend.md`.
> Wspólna mechanika nauczycieli i format odpowiedzi: [teacher-agent](teacher-agent.md).

**Kolejność, w której patrzy senior:**

1. **Skąd pochodzi ten stan** — server state (TanStack Query) vs client state
   (`useState`) vs globalny (Zustand, tylko gdy naprawdę współdzielony) vs stan
   URL. **Najczęstszy błąd juniora: kopiowanie danych serwera do `useState`.**
2. **Kto jest właścicielem danych** — jeden właściciel, reszta dostaje propsy.
   Duplikat stanu = dwa źródła prawdy.
3. **Granica komponentu** — po odpowiedzialności i po tym, co zmienia się razem,
   **nie po liczbie linii**.
4. **Kontrakt z backendem** — przy `codegen: orval` typy i hooki są generowane;
   ręczne dopisywanie typów obok generatora to dług.
5. **Re-rendery** — najpierw zrozum **co** powoduje render, dopiero potem `memo`.
   Memoizacja bez pomiaru to szum.
6. **Efekty** — `useEffect` to synchronizacja z systemem zewnętrznym, nie
   miejsce na logikę biznesową. Większość efektów juniora da się usunąć.
7. **Web vs native** — kod „prawie działający na obu" jest **gorszy** niż dwa
   jawne pliki.
8. **Routing** — struktura plików = struktura nawigacji; URL to część UX.
9. **Formularze** — jeden schemat walidacji współdzielony z typami; błąd
   z serwera musi mieć gdzie wylądować.
10. **Stany UI** — loading / empty / error / offline to normalne stany, nie
    „potem dorobimy".

Sekcja o typowaniu ma tu **odwrotną pułapkę niż w Pythonie**: typy są wszędzie,
więc łatwo uwierzyć, że skoro się kompiluje, to działa.

**vs [review-frontend](review-frontend.md):** ten uczy patrzeć zanim się
napisze kod; tamten łapie, co już wyszło źle w diffie.
