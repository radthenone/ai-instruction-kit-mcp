# Decyzje architektoniczne (ADR)

Decyzje architektoniczne kita leżą w `docs/adr/` w repo kita. Każda ma kontekst i uzasadnienie. Zanim zaproponujesz zmianę architektury, sprawdź, czy część rzeczy już rozstrzygnięto.

| ADR | Decyzja |
|---|---|
| [0001](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0001-mappings-live-in-the-manifest.md) | Mapowania żyją w manifeście, nie w kodzie resolvera |
| [0002](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0002-alias-normalisation-runs-first.md) | Normalizacja aliasów działa jako pierwsza |
| [0003](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0003-aliases-are-deprecated-not-deleted.md) | Aliasy są wycofywane, nie usuwane |
| [0004](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0004-unknown-decisions-are-reported-not-fatal.md) | Nieznane decyzje są raportowane, nie wywracają serwera |
| [0005](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0005-shell-suites-enter-ci-through-unittest-discover.md) | Suity powłoki wchodzą do CI przez `unittest discover` |
| [0006](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0006-guards-never-ask.md) | Guardy nigdy nie pytają, odpowiadają tylko `allow` albo `deny` |
| [0007](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0007-the-workspace-profile-is-the-only-configuration.md) | Profil projektu jest jedyną konfiguracją |
| [0008](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0008-a-bare-stack-name-means-the-current-approach.md) | Goła nazwa stacku oznacza bieżące podejście |
| [0009](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0009-server-guard-denies-heavy-commands-on-vps.md) | Server guard blokuje ciężkie komendy na VPS |
| [0010](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0010-brief-as-artifact.md) | Brief jako artefakt, renderowany do nośników |
| [0011](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0011-host-detection-in-a-shared-module.md) | Wykrywanie hosta we wspólnym module |
| [0012](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0012-codegraph-module-delivery.md) | Dostarczanie modułu CodeGraph |
| [0013](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0013-agent-classification-and-ponytail-matcher.md) | Klasyfikacja agentów i matcher ponytaila |
| [0014](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0014-the-kit-owns-the-worktree-method-not-the-decision-to-isolate.md) | Kit posiada metodę worktree, nie decyzję o izolacji |
| [0015](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0015-retro-dedup-via-issue-marker.md) | Deduplikacja retro przez marker w issue |
| [0016](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0016-retro-scan-is-the-single-cost-source.md) | Skan retro jest jedynym źródłem kosztu |
| [0017](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0017-retro-dedup-counts-issues-in-every-state.md) | Deduplikacja retro liczy issues we wszystkich stanach |
| [0018](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0018-model-choice-comes-from-one-targets-block.md) | Wybór modelu pochodzi z jednego bloku `targets` |
| [0019](https://github.com/radthenone/ai-instruction-kit-mcp/blob/master/docs/adr/0019-commands-take-the-native-form-per-client.md) | Komendy przyjmują natywną formę każdego klienta |

Inne katalogi `docs/`: `agents/` (kontrakt issue trackera i etykiety triage), `specs/` (projekty przed implementacją), `plans/` (plany implementacyjne).
