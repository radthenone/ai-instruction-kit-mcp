# Architektura repo kita

Ta strona jest dla osób, które zmieniają sam kit. Użytkownicy kita znajdą opis działania w [Jak działa kit](../koncepcja/jak-dziala-kit.md).

## Układ repo

```text
ai-instruction-kit-mcp/
├── src/guides/          serwer MCP i CLI kita (Python)
├── modules/             treść instrukcji, Markdown (Module ID → plik)
├── templates/           szablony klientów i wspólne źródło
│   ├── shared/          kanon: agents, skills, guards, rules
│   └── claude/, cursor/, codex/, vscode/, kiro/, kilo/, antigravity/, opencode/
├── manifest.yaml        rejestr modułów, Tierów, bundli i mapowań
├── scripts/             bootstrap i renderery
├── tests/               unittest i suity powłoki
├── docs/                adr/, agents/, specs/, plans/
├── CONTEXT.md           słownik (ubiquitous language)
├── AGENTS.md            brief kita
└── CODING_STANDARDS.md  indeks źródeł standardów
```

## Moduły w `src/guides/`

| Moduł | Rola |
|---|---|
| `server.py` | serwer MCP: definicje narzędzi (`@mcp.tool`) |
| `cli.py` | komendy `kit-ai`: install, reload, status, doctor, retro, issue, pr |
| `resolver.py` | składa Bundle i moduły z Profilu według `manifest.yaml` |
| `manifest.py` | wczytanie i walidacja manifestu |
| `bootstrap.py` | zapis plików kita do Workspace |
| `host_profile.py` | wykrywanie hosta `vps` i `local` |
| `server_guard.py` | render i dopasowanie server guarda |
| `brief_rules.py` | renderowanie Brief Rules w wariantach pl i en |
| `questions.py` | katalog pytań o projekt (`list_questions`) |
| `labels.py` | etykiety GitHuba (`ensure_labels`) |
| `worktree.py` | kontrola zgodności Managed Worktree |
| `retro.py`, `issue_stats.py`, `matt_contract.py`, `kit_status.py` | retro, statystyki issue, kontrakt Matta, status kita |

## Zasada: mapowania w manifeście

[ADR-0001](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0001-mappings-live-in-the-manifest.md): reguły włączania modułów żyją w `manifest.yaml`. Nowa technologia to plik Markdown i wpis w manifeście, bez zmian w `resolver.py`.

## Zasada: jedno źródło, wiele adapterów

- Treść agentów i skilli: `templates/shared/`. Adaptery klientów zmieniają format i ścieżkę, nie treść.
- Polityka guardów: `templates/shared/guards/`. Adapter `invoke-hook.js` tłumaczy kontrakt klienta.
- Brief Rules: jeden szablon `templates/shared/rules/brief-rules.md`, renderowany do trzech nośników.

Test `TestBriefRulesFreshness` w `tests/test_brief_rules.py` pilnuje, że wygenerowane pliki odpowiadają szablonowi.

## Dlaczego treść nie jest kopiowana

Serwer czyta `modules/` z klona przy każdym `get_bundle`. Kopia w projekcie gniłaby, a serwowanie na żywo nie. Wyjątkiem są Brief Rules ([ADR-0010](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0010-brief-as-artifact.md)).

## Słownik

Nazwy z `CONTEXT.md` obowiązują w kodzie, docstringach i review. Zanim zaproponujesz zmianę architektury, sprawdź `docs/adr/`. Część rzeczy już rozstrzygnięto.
