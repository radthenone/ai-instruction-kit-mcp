# Modele agentów

Każdy agent kita ma w szablonie klasę modelu (`model-tier`): `light`, `standard` albo `heavy`. To osobny klucz od `tier:` stacku. Wybór konkretnego modelu zapisujesz w jednym miejscu, bloku `targets:` w Profilu ([ADR-0018](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0018-model-choice-comes-from-one-targets-block.md)).

## Klasy modeli

| Klasa | Do czego |
|---|---|
| `light` | tanie, mechaniczne procedury: `git-*`, `pr-stats`, `cleanup` |
| `standard` | większość pracy: `create-task`, `kit-project-*`, `teacher-*`, `subagent-*` |
| `heavy` | mocne review: `review-backend`, `review-frontend`, `review-security`, `review-edge` |
| `takeover` | model przejęcia ticketu nocnego, gdy wykonawca zwróci limit |

## Blok `targets:`

```yaml title=".ai/project.profile.yaml"
targets:                  # ręczny; reload tego bloku nie rusza
  claude:
    light:
      providerInstanceId: claudeAgent
      model: claude-haiku-5-5
      options: [{ id: effort, value: low }]
    standard:
      providerInstanceId: claudeAgent
      model: claude-sonnet-5-5
      options: [{ id: effort, value: medium }]
    heavy:
      providerInstanceId: claudeAgent
      model: claude-opus-5-5
      options: [{ id: effort, value: high }]
```

Każdy wpis to `providerInstanceId`, `model` i `options`. Brak wpisu klienta albo klasy oznacza brak pól `model` i `effort`. Agent dziedziczy wtedy model sesji.

## Blok `agents:`

```yaml title=".ai/project.profile.yaml"
agents:                   # synchronizowany przez reload
  light: git-start,git-commit,git-end,git-check,cleanup
  standard: create-task,create-skill
  heavy: night-run,review-edge
```

Reload dopisuje brakujących agentów kita do klasy z szablonu i usuwa nazwy spoza kita. Przypisania, które już istnieją, zostają, bo Profil wygrywa.

## Gdzie model trafia

| Klient | Obsługa | Gdzie | Format nazwy |
|---|---|---|---|
| Claude Code | tak | frontmatter `.claude/agents/<agent>.md` | id modelu albo alias: `haiku`, `sonnet`, `opus`, `fable` |
| opencode | tak | `.opencode/commands/kit-ai/<agent>.md` | `provider/model`, a przy `variant` sufiks `#<variant>` |
| Cursor, Codex, VS Code, Kiro, Kilo, Antigravity | nie | pole pomijane | |

Claude przyjmuje alias wyprowadzany z id modelu. Nieznane id oznacza model sesji. Opcje dostawcy: `effort` (Claude), `variant` (opencode), `thought_level` (Antigravity), `reasoningEffort` (Codex).

## Błędy, które przerywają reload

Reload zatrzymuje się z opisem błędu, gdy:

- używasz starych kluczy `models:` albo `t3.targets`,
- klient albo klasa są nieznane,
- wpis nie ma `providerInstanceId` albo `model` jest pusty,
- blok `targets:` zapisano w jednej linii, np. `targets: {…}`,
- klient nie ma klasy `standard` ani `takeover`,
- ten sam agent jest w dwóch klasach.

Bloki pisz z wcięciami, jak w przykładzie. Reload przepisuje blok `agents:` i komentarze w nim giną.

## Takeover

`targets.<klient>.takeover` to model przejęcia ticketu nocnego. Brak wpisu oznacza kopię `standard` tego klienta. Zob. [Praca nocna i headless](../komendy/praca-nocna-i-headless.md).
