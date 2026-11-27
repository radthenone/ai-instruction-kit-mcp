# Review

Review działa na **gotowym diffie** i zwraca tabelę findingów. Nie edytuje plików. Każdy finding ma format `Severity | Location | Finding | Fix`. Konwencje agenci czytają z MCP (`get_bundle`) i z `CODING_STANDARDS.md`.

## Który review kiedy

| Zmiana | Minimum |
|---|---|
| Drobna | `review-bugbot` |
| Backend albo frontend | `review-bugbot` i `review-backend` albo `review-frontend` |
| API i UI razem | `review-bugbot`, BE i FE, albo para `subagent-*` |
| Auth, płatności, sekrety | `review-security` |
| Dowód, że działa | `review-tests` |

Nie odpalaj całego wachlarza. Minimalny stack wystarcza i jest szybszy.

## Opisy

- **`review-bugbot`**: manualny odpowiednik Cursor BugBota. Stosuje reguły z `BUGBOT.md` do bieżącego diffa. Przydatny, gdy nie masz natywnego BugBota (Claude, Codex, inne klienty). Szuka problemów blokujących i bezpieczeństwa.
- **`review-backend`**: konwencje backendu z Tieru `backend`: endpointy, kontrakt API, ACL, zadania w tle, migracje.
- **`review-frontend`**: kod klienta web i mobile, generowany klient API, typy TypeScript.
- **`review-ui`**: ekrany, formularze, flow użytkownika, komponenty wspólne.
- **`review-architecture`**: kontrakt API, struktura monorepo, wzorzec capability-provider.
- **`review-security`**: uwierzytelnianie, sesje, ACL, webhooki, sekrety.
- **`review-tests`**: weryfikator dowodu. Sprawdza, czy komendy faktycznie przechodzą. Nie jest stylistą.
- **`review-edge`**: pedantyczny reviewer. Szuka regresji, przypadków brzegowych i brakującej walidacji. Do większych zmian.
- **`review-council`**: trzech delegatów dyskutuje w rundach o zmianie albo architekturze. Do decyzji, nie do drobnych zmian.

## Poziom modelu

Większość agentów review działa na klasie `heavy`. `review-council` działa na `standard`. Klasę zmienisz w bloku `targets:`. Zob. [Modele agentów](../konfiguracja/modele-agentow.md).

## Przykład

```text
/kit-ai:review-backend przejrzyj zmiany w backend/apps/products/
/kit-ai:review-bugbot
```

Wynik to tabela. Każdy wiersz ma lokalizację i konkretną poprawkę. Finding na osi Spec o wadze High, który zostaje po poprawkach, jest **blokujący** w nocnym runie: blokuje merge swojego ticketu.

## Gdzie review się odbywa

| Warstwa | Co |
|---|---|
| lokalnie | `review-*` przed pushem |
| przed pushem | `git-guard` blokuje push na chronione gałęzie |
| na PR | BugBot przez integrację GitHuba |
| reguły | `BUGBOT.md`, a Twoje reguły w bloku `project:rules` |
| repo kita | unittest, suity powłoki i smoke serwera FastMCP w CI |

Pełne zasady: [Przepływ zmiany](../koncepcja/przeplyw-zmiany.md).
