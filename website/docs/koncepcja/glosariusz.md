# Glosariusz

Nazwy z tej strony są używane w kodzie, docstringach i review. Pogrubione terminy to nazwy kanoniczne. Definicje są streszczeniem `CONTEXT.md` z repo kita.

## Treść instrukcji

- **Instruction Module**: plik Markdown z instrukcjami, o stabilnym ID, np. `infra:queue:redis`.
- **Module ID**: adres modułu w formie `warstwa:kategoria:wariant`. Alias nie jest Module ID.
- **Bundle**: nazwany, uporządkowany zestaw modułów dla jednego rodzaju pracy: `backend`, `frontend`, `architecture`, `infra`, `devops`, `full`.
- **Manifest**: rejestr modułów i reguł, które zamieniają wybory z Profilu na Module ID.
- **Overlay**: instrukcje prawdziwe dla jednego repo (ścieżki, porty, nazwy zadań). Dołączany do Bundle, nigdy w nim nie scalany. Dostarczany przez `get_overlay`.
- **Brief**: krótka orientacja, którą agent czyta przed pracą w Workspace.
- **Brief Rules**: kilka reguł, które każdy agent musi znać przed pierwszą akcją. Jedyna treść modułów kita kopiowana do Workspace. Szablony agentów, komend i skilli bootstrap kopiuje osobno.
- **Host**: maszyna, na której działa agent. Klasyfikowana jako `vps` albo `local`.
- **Carrier**: miejsce, w którym Brief Rules docierają do agenta: hook języka (tylko Claude), instrukcje MCP, sekcja `AGENTS.md`.

## Konfiguracja

- **Profile**: pełny zestaw wyborów projektu: język, klienci, stacki w Tierach, Capabilities, Patterns, Decisions.
- **Tier**: warstwa produktu: `backend`, `web` albo `mobile`. Zawiera dokładnie jeden stack albo nic.
- **Decision**: wybór jednej technologii dla jednego Slotu, np. `queue: rabbitmq`.
- **Slot**: punkt zmienności technologicznej, który kit potrafi obsłużyć: `database`, `cache`, `queue`, `storage`, `tasks`, `search`, `auth`.
- **Capability**: funkcja produktu, która jest albo jej nie ma: autoryzacja, pliki, płatności.
- **Variant**: bardziej konkretny moduł, który dołącza się obok ogólnego, np. `capability:auth:jwt` obok `capability:auth`. Ogólny zostaje.
- **Substitution**: moduł, który zastępuje ogólny w całości, np. `arch:api-contract:graphql` zamiast `arch:api-contract`.
- **Stack**: nazwana podstawa technologiczna dla jednego Tieru, np. `django`, `react`, `expo`.
- **Pattern**: powtarzalne podejście projektowe, np. capability-provider albo webhooki.
- **Language**: język prozy w instrukcjach i komunikacji agenta. Tytuły issue, PR, branchy i identyfikatory zawsze po angielsku.
- **Alias**: wycofana pisownia Module ID albo nazwy Capability, nadal akceptowana.
- **Model tier**: klasa modelu dla agenta lub zadania: `light`, `standard`, `heavy`, `takeover`.
- **Target**: wpis `targets.<klient>.<model tier>` w Profilu, z `providerInstanceId`, `model` i `options`.
- **Provider option**: ustawienie przyjmowane przez dostawcę modelu, np. `effort` (Claude), `reasoningEffort` (Codex).

## Dystrybucja

- **Kit Root**: katalog z manifestem i modułami.
- **Workspace**: katalog repo aplikacji, gdzie leżą Overlay i stamp bootstrapu.
- **Project Block**: chroniona sekcja plików regułami projektu, np. `project:rules` w `BUGBOT.md`. Przechodzi przez każdy bootstrap bez zmian.
- **Uncertain Migration**: migracja pliku bez Project Block, której kit nie stosuje sam, tylko proponuje.
- **Bootstrap**: zapis plików kita do Workspace zgodnie z Profilem. Powtarzalny, nigdy nie rusza Overlay.
- **Client**: narzędzie AI, które korzysta z kita: Cursor, Claude Code, Codex, VS Code, Kiro, Kilo, Antigravity, OpenCode.
- **Guard**: skrypt hooka, który odmawia albo zgłasza akcję agenta. Zawsze `allow` albo `deny`.
- **Lock-only Form**: komenda menedżera paczek, która zmienia tylko lockfile i nic nie instaluje.
- **Bootstrap Stamp**: zapis, z którego commita kita powstały skopiowane pliki (`.ai/.kit-bootstrap.json`).
- **Managed Worktree**: worktree zsynchronizowany metodą kita. Zob. [Managed Worktree](managed-worktree.md).

## Komendy i agenci

- **Command**: forma slash-komendy szablonu agenta, napisana dla jednego klienta w jego natywnej formie.
- **Command prefix**: przedrostek w nazwie komendy: `kit-ai:` w pluginie Claude, katalog `kit-ai/` w OpenCode.
- **Procedure agent**: agent klasy `procedure`, czyli stały przepływ kita, np. `git-*`, `review-*`. Ponytail go nie przepisuje.
- **Code agent**: agent klasy `code`, który pisze kod aplikacji. Tylko na niego działa ponytail.
- **Subagent**: agent uruchomiony przez innego agenta do jednego zadania, we własnym kontekście. Nie rozmawia z człowiekiem. Wynik oddaje jako Hand-back.

## Praca nocna

- **Orchestrator**: główna sesja, która prowadzi `/night-run`. Wybiera tickety i uruchamia subagenta dla każdego.
- **Ticket**: jedno issue przeprowadzone przez `/night-run` od brancha do merge albo do Needs-human.
- **Hand-back**: końcowy raport subagenta dla agenta, który go uruchomił.
- **Needs-human**: wynik ticketu, którego nie da się dokończyć bez człowieka. To status, nie etykieta.
- **Finding blokujący**: finding o wadze High na osi Spec, nierozwiązany po poprawkach. Blokuje merge swojego ticketu.

## Retro

- **Sesja**: jeden zapis rozmowy agenta razem z jego subagentami, albo jeden przebieg headless.
- **Koszt**: liczba tokenów zużytych przez sesję. To nie jest kwota w pieniądzach.
- **Sygnał**: pojedyncze wykrycie w logu sesji, np. odrzucenie przez guard.
- **Znalezisko**: sygnały o tym samym znaczeniu, zgrupowane po fingerprincie.
- **Fingerprint**: klucz deduplikacji znaleziska, stały między sesjami i maszynami.
- **Propozycja**: zmiana kitu, projektu albo karta do założenia. Wymaga akceptacji człowieka, zanim cokolwiek trafi na GitHub.
