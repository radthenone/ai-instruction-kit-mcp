# Dodawanie modułu, stacku i agenta

Trzy najczęstsze zmiany w repo kita. Zanim zaczniesz, sprawdź `docs/adr/` i `CONTEXT.md`. Nazwy muszą pasować do słownika.

## Nowy moduł

1. Napisz plik Markdown w odpowiednim katalogu `modules/`, np. `modules/infra/queue/kafka.md`.
2. Zarejestruj go w `manifest.yaml` w sekcji `modules:`, z `path`, `title` i `tags`:

```yaml title="manifest.yaml"
  infra:queue:kafka:
    path: modules/infra/queue/kafka.md
    title: Kafka (broker kolejki)
    tags: [infra, queue]
```

3. Jeśli moduł ma wchodzić po wyborze z Profilu, dopisz mapowanie w `mappings`. Dla slotu: `mappings.slots.queue.kafka`. Dla Tieru: w `mappings.tiers.<tier>.<stack>`.

Tagi decydują, do których bundli moduł trafi. Bez właściwego tagu moduł nie pojawi się w żadnym bundlu.

## Nowy stack w Tierze

1. Moduły stacku w `modules/stacks/<nazwa>/`: przegląd, struktura, instrukcje agenta, testy.
2. Wpis w `mappings.tiers.<tier>.<nazwa>` z listą modułów.
3. Jeśli stack ma podpowiedź układu katalogów, wpis w `layouts:`.
4. Jeśli stack da się wykryć w repo, pytanie w sekcji `questions:` manifestu.

Stack bez wpisu w `mappings` nie wywraca serwera. Trafi do nierozpoznanych decyzji. Zob. [Sloty i decyzje](../konfiguracja/sloty-i-decyzje.md).

## Nowy agent

Szablon agenta leży w `templates/shared/agents/<nazwa>.md`. Frontmatter ma trzy wymagane pola:

```yaml title="templates/shared/agents/<nazwa>.md"
---
name: <nazwa>
description: Co robi, kiedy odpalić. Use when …. Wywołuj jako @KIT_CMD_PREFIX@<nazwa>.
model-tier: light          # light | standard | heavy
classification: procedure  # procedure | code
---
```

- **`classification`** jest wymagana. `procedure` dla stałych przepływów kita, np. `git-*` i `review-*`. `code` dla agentów piszących kod aplikacji. Brak albo nieznana wartość przerywa bootstrap ([ADR-0013](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0013-agent-classification-and-ponytail-matcher.md)).
- **`model-tier`** wybiera klasę modelu. Konkretny model ustawiasz w `targets` w Profilu.
- Agent per Tier dostaje pole `tier:` z wartością `backend` albo `client`. Pojawia się wtedy tylko u klientów wybranych Tierów.
- **`@KIT_CMD_PREFIX@`** w treści zamieniany jest na przedrostek klienta: `kit-ai:` w Claude, `kit-ai/` w opencode.

Po dodaniu agenta uruchom testy i sprawdź wynik renderowania dla każdego klienta.

## Nowa komenda

Komenda nie jest osobnym plikiem. To agent, który dostaje natywną formę każdego klienta ([ADR-0019](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0019-commands-take-the-native-form-per-client.md)). Dodajesz tylko szablon w `templates/shared/agents/`.

## Nowy guard

Polityka jest w `templates/shared/guards/<nazwa>.mjs` i zwraca `allow` albo `deny`. Nigdy `ask` ([ADR-0006](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0006-guards-never-ask.md)). Potem dopisz go do hooków każdego klienta, w którym ma działać. Dla klientów innych niż Claude potrzebny jest też wpis w adapterze `invoke-hook.js`. Dodaj testy tabeli allow i deny.

## Zasady nazewnictwa

- Identyfikatory i nazwy testów po angielsku.
- Treść modułów i docstringi po polsku, zgodnie z językiem kitu.
- Tytuły issue i PR po angielsku, body po polsku.
