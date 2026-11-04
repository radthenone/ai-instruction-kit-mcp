# ai-instruction-kit-mcp

Kit instalowany w repozytoriach projektów: dostarcza procedury, guardy i skille, a `retro` analizuje, jak agenci te procedury wykonują.

## Retro

**Sesja**:
Jeden zapis rozmowy agenta (plik JSONL wraz z jego subagentami) albo jeden przebieg headless lub nocny ticket, traktowany jako całość przy analizie.
_Avoid_: Transkrypt, run, rozmowa

**Sygnał**:
Pojedyncze wykrycie w logu sesji, na przykład odrzucenie przez guard albo błąd narzędzia.
_Avoid_: Błąd, event, alert

**Znalezisko**:
Sygnały o tym samym znaczeniu zgrupowane po fingerprincie, z liczbą wystąpień i dowodem po maskowaniu.
_Avoid_: Problem, issue, raport

**Fingerprint**:
Klucz deduplikacji znaleziska, stały między sesjami i maszynami dla tego samego problemu.
_Avoid_: ID, hash, sygnatura

**Propozycja**:
Sugerowana zmiana kitu, projektu albo karta do założenia, którą człowiek musi zaakceptować przed jakimkolwiek zapisem na GitHub.
_Avoid_: Zadanie, ticket, automatyczne issue
