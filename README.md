# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają Stack **per Tier** (`backend`/`web`/`mobile` w `.ai/project.profile.yaml`) + overlay.

## Szybki start — instalacja i update

Jedna komenda robi oba. Bootstrap jest idempotentny: pliki generowane (agenci, komendy,
hooki, `mcp.json`) nadpisuje świeżą kopią, a pliki z Twoją treścią (`AGENTS.md`,
`.ai/project.md`, `BUGBOT.md`) zostawia w spokoju.

**Wymagania:** `uv` w `PATH`, `bash` (Windows: Git for Windows), `node` (dla hooków),
opcjonalnie `npx` (skille zewnętrzne).

### 1. Instalacja / update w projekcie — `kit-ai`

Z katalogu klona kita (ścieżki `M:/…`, `/m/…` i linuksowe działają tak samo):

```bash
cd /m/projects/ai-instruction-kit-mcp      # klon tego repo
APP=/m/projects/moja-appka                 # repo aplikacji

uv run kit-ai install "$APP"               # pyta o język i klientów, zakłada Profil, Bootstrap
uv run kit-ai reload "$APP"                # po zmianie Profilu / update kita — odświeża pliki kita
uv run kit-ai reload "$APP" --dry-run      # plan bez zapisu
uv run kit-ai status "$APP"                # czy kit zmienił się od ostatniego Bootstrapu
```

`install` pyta o dwie rzeczy (`Język [pl/en] (pl)`, `Klienci (…) (all)`) — flagi `--language`
i `--clients` pomijają pytania, bez TTY pytań nie ma wcale. Zakłada `.ai/project.profile.yaml`
(`backend/web/mobile: none` = sam core) i `.ai/project.md`, robi Bootstrap, a na końcu
wypisuje JSON serwera MCP i gdzie leży per klient. Repo z kitem `install` odrzuca — wtedy
`reload`.

Jedyna konfiguracja to Profil (ADR-0007): język, klienci, Stacki per Tier, `codegen:`.
Zmiana czegokolwiek = edycja `$APP/.ai/project.profile.yaml` + `kit-ai reload`. `reload` nie
rusza `.ai/project.md`; repo ze starą konfiguracją (stamp z `--preset`, brak Profilu) dostaje
Profil core + none i nowy `mcp.json`.

| Klucz Profilu | Kiedy zmienić |
| --- | --- |
| `clients:` | `claude` \| `codex` \| `vscode` (= GitHub Copilot) \| `cursor` \| `kiro` \| `kilo` \| `antigravity` \| `opencode` \| `all`. Pliki klientów **spoza** listy są sprzątane przy `reload` |
| `backend`/`web`/`mobile` | Stack per Tier (puste Tiery = sam core) |
| `language:` | `pl` \| `en` — język prozy. Tytuły issue/PR/branch zawsze EN |
| `codegen:` | `orval` (default) \| `none` \| `graphql` |

Niskopoziomowo to samo robi `scripts/bootstrap-project.sh "$APP" --from "$KIT" --clients … --language …`
(dodatkowo `--with-overlay`, `--with-plugins`, `--keep-unselected-clients`). `--preset`,
`--profile`, `--with-profile` i `--codegen` zostały usunięte — skrypt odmawia i odsyła do `kit-ai reload`.

### 2. Po instalacji (kroki, których skrypt nie zrobi za Ciebie)

```bash
# a) hook pre-push — skrypt kopiuje go do git-hooks/, ale nie do .git/
cp "$APP/git-hooks/pre-push" "$APP/.git/hooks/pre-push"
chmod +x "$APP/.git/hooks/pre-push"
```

```text
# b) Superpowers — plugin marketplace Claude Code, nie da się ze skryptu.
#    Wpisz w Claude Code:
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

**c) Zrestartuj IDE / CLI.** MCP i komendy ładują się przy starcie — bez restartu
zobaczysz stan sprzed bootstrapu.

### 3. Weryfikacja

```bash
# MCP odpowiada i widzi właściwy kit
#   w Claude Code: poproś o wywołanie narzędzia check_kit_status
#   oczekiwane: "Kit status: aktualny"

# hooki działają (powinno wypisać "deny")
printf '%s' '{"tool_input":{"command":"git reset --hard HEAD"}}' \
  | node "$APP/.claude/hooks/git-guard.mjs"

# konfiguracja AI wchodzi do repo, lokalny stan nie
git -C "$APP" status --short -uall .claude .codex .github/prompts
```

### 4. Kiedy aktualizować

Narzędzie MCP `check_kit_status` porównuje commit kita zapisany przy bootstrapie
(`.ai/.kit-bootstrap.json`) z aktualnym `HEAD` i mówi, co się zmieniło. Rozdziela dwie
rzeczy: pliki, które **re-bootstrap wciągnie sam**, i te wymagające **ręcznego
przeniesienia** (`AGENTS.md`, `BUGBOT.md`, `.ai/project.md`, `git-hooks/pre-push` — kopiowane
tylko gdy brak, żeby nie zdeptać Twojej treści). Gdy pokaże zmiany: `kit-ai reload "$APP"`
(z terminala to samo pokazuje `kit-ai status "$APP"`).

### 5. Zanim odpalisz update na repo z pracą w toku

Bootstrap nadpisuje `.claude/{agents,commands,hooks}/`, `.codex/`, `.github/prompts/`,
`copilot-instructions.md` i pliki MCP. Jeśli edytowałeś je ręcznie — `git diff` najpierw.
Nie chcesz oglądać planu na sucho? Z poziomu agenta:

```text
reload_workspace()                  # dry run — lista plików nowych/nadpisanych/usuniętych
reload_workspace(dry_run=False)     # odświeżenie z Profilu (= kit-ai reload)
```

**Gdzie żyje konfiguracja AI po instalacji:** wszystko poza `.claude/settings.local.json`
i `.agents/skills/` idzie do repo — bootstrap wstawia do `.gitignore` sekcję między
markerami `# >>> instruction-kit >>>`. Szczegóły: sekcja „`.gitignore`" niżej.

**Gdzie czytać / zmieniać konfigurację:**


| Co                                           | Gdzie pisać                                             |
| -------------------------------------------- | ------------------------------------------------------- |
| Argumenty MCP (`--language`, `--clients`, `--workspace`, …) | ten README (sekcja niżej) + szablony `templates/*/mcp*` |
| Stack per Tier i fork                       | [profil z Tierami](#profil-z-tierami-backendwebmobile)              |
| Kanon agentów / reguł (niezależny od IDE)    | [`templates/shared/`](templates/shared/README.md)       |
| Multi-client design                          | [design](docs/specs/2026-08-05-multi-client-templates-design.md) |
| Szczegóły jednego produktu                   | `.ai/project.md` w **repo aplikacji** (Taskfile, porty, Docker)  |
| Inny zestaw modułów niż Tiery              | `include:` w `.ai/project.profile.yaml` (routing wg tagów)         |
| Docelowy kontrakt `--overlays` | [design overlays](docs/specs/2026-08-05-mcp-profile-architecture-overlays-design.md) |
| Cursor `/compact` (alias Summarize)          | `templates/cursor/skills/compact/` → `.cursor/skills/` (nie Claude/Codex) |
| Skille kita (wszyscy klienci)                | `templates/shared/skills/` → sekcja „Skille kita” niżej |


## Struktura `docs/`

```text
docs/
├── adr/     — decyzje architektoniczne (format Nygarda)
├── agents/  — kontrakt issue trackera, etykiety triage, docs domenowe
├── specs/   — projekty przed implementacją
└── plans/   — plany implementacyjne
```

> `docs/specs/` i `docs/plans/` nazywały się wcześniej `docs/superpowers/{specs,plans}`. Zmiana jest celowa: Superpowers i `mattpocock/skills` to zewnętrzne biblioteki, z których kit **korzysta** — ich nazwa nie powinna strukturyzować drzewa docs tego repo.

## Konfiguracja projektu — argumenty `guides-mcp`

Wszystkie flagi serwera MCP wpisujesz w `args` klienta (Cursor: `.cursor/mcp.json`). Kolejność: najpierw `--from` / nazwa pakietu (`guides-mcp`), potem flagi poniżej.

### Warstwy (co gdzie należy)


| Warstwa                           | Mechanizm                                             | Przykład                 |
| --------------------------------- | ----------------------------------------------------- | ------------------------ |
| Stack backendu                    | Tier `backend` w profilu                              | `django`, `fastapi`, `flask`, `none` |
| Stack webu                        | Tier `web` w profilu                                  | `react`, `angular`, `expo`, `none` |
| Stack mobile                      | Tier `mobile` w profilu                               | `expo`, `react-native`, `none` |
| Powtarzalny wariant               | `--tag` / facety (**planowane**, niezaimplementowane) | `physical`, `digital`    |
| Fakty jednego repo                | `.ai/project.md` + `--workspace`                      | porty, Taskfile          |
| Inny zestaw modułów niż Tiery     | `include:` w profilu (routing wg tagów)               | `capability:payments`    |


Nie mieszaj: nazwa produktu ≠ Stack; porty ≠ tag.

### Flagi (aktualne)

```json
{
  "mcpServers": {
    "project-guides": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git",
        "guides-mcp",
        "--language", "pl",
        "--clients", "all",
        "--workspace", "${workspaceFolder}"
      ]
    }
  }
}
```


| Flaga              | Wymagana? | Rola                                                                                                                                               | Gdzie / jak zmieniać                                     |
| ------------------ | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `--from SOURCE`    | przy `uvx` | Źródło zdalne kita: `git+https://…@ref`. Dla lokalnego klonu bootstrap generuje zamiast tego `uv run --project <ścieżka>` — patrz „Lokalny klon" niżej | `.cursor/mcp.json` (i odpowiedniki innych klientów)      |
| `--language pl|en` | nie       | Język **prozy** (odpowiedzi, docstringi, body issue/PR, commity). **Tytuły** issue/PR/branch zawsze EN. Domyślnie: `language:` w profilu albo `pl` | `language:` w Profilu + `kit-ai reload`; env `GUIDES_LANGUAGE` |
| `--clients LIST`   | nie       | Metadane IDE: `all` \| `cursor` \| `claude` \| `codex` \| `vscode` \| `kiro` \| `kilo` \| `antigravity` \| `opencode` (lista; alias `copilot`→`vscode`). **Nie** zmienia treści bundle | mcp.json / bootstrap `--clients` (default `all`); env `GUIDES_CLIENTS`; tool `get_clients` |
| `--kit-root PATH`  | nie       | Klon kita, z którego serwer czyta `manifest.yaml` / `modules/`. Bez niej root jest wykrywany automatycznie — a przy `uvx --from <katalog>` wykrywa się kopia z cache `uv` zamiast klonu | mcp.json — bootstrap dodaje sam przy źródle lokalnym; env `GUIDES_KIT_ROOT` |
| `--workspace PATH` | zalecane  | Root aplikacji — stąd profil `.ai/project.profile.yaml` i overlay `.ai/project.md`                                                                                                        | mcp.json; Cursor/VS: `${workspaceFolder}`                |
| `--overlay PATH`   | nie       | Extra MD (można wielokrotnie)                                                                                                                      | mcp.json — rzadko; zwykle wystarczy workspace            |


Stare konfiguracje klienta z `--preset` / `--profile` / `--codegen` nadal startują serwer, ale
te flagi są ignorowane, a bundle i indeks niosą ostrzeżenie o migracji — `kit-ai reload`
przepisze `mcp.json`. Bootstrap zapisuje tylko `--language` i `--clients` (z Profilu).

**Język:** MCP tool `get_language`. Priorytet: `--language` / `GUIDES_LANGUAGE` → `language:` w YAML profilu → `pl`. Moduł w bundle: `core:language-pl` albo `core:language-en`.

**Klienci AI:** MCP tool `get_clients` — tylko metadane instalacji; treść `get_bundle` jest identyczna dla każdego klienta.

**Codegen (Orval):** wyłącznie `codegen:` w `.ai/project.profile.yaml` (`orval` \| `none` \| `graphql`, domyślnie `orval`; ADR-0007), odczyt przez MCP tool `get_codegen`. Bez pary backend + klient (web/mobile) efektywny codegen to zawsze `none`. Reviewery FE/BE to honorują (przy `orval` wymagają regeneracji klienta po zmianie API; `graphql` → moduł `arch:api-contract:graphql` zamiast REST).

## Profil z Tierami (backend/web/mobile)

```yaml
# .ai/project.profile.yaml w repo aplikacji
name: moja-appka
language: pl
clients: claude,codex

backend: django      # none | django | django-html | fastapi | flask
web: react            # none | react | react@legacy | angular | angular@rxjs | expo
mobile: none           # none | expo | react-native

codegen: orval        # orval | none | graphql (bez pary backend + klient: zawsze none)

capabilities:
  - auth
  - payments

decisions:
  database: postgres
  auth: jwt
```

Bundle liczone są z Tierów: `get_bundle backend` zawiera Stack z Tieru `backend`, pusty profil daje sam core. Nierozpoznana wartość Tieru nie wywraca serwera — ląduje w „Nierozpoznanych decyzjach" w `get_index` (ADR-0004). Stare klucze `stacks:` / `patterns:` czytane są nadal.

### Katalog pytań o projekt (`list_questions`)

`manifest.yaml` → `questions:` trzyma pytania o projekt (Tiery, warianty, `codegen`, Docker,
Taskfile, CI/CD, monorepo, capability-provider, webhooki, ścieżki per Tier) z opcjami,
domyślnymi (`defaults:` zależne od Profilu, np. `django-html` → web/mobile `none`),
warunkiem `when:` i sygnałami `detect:` (`glob` + opcjonalny regex `pattern` w treści pliku).
Narzędzie MCP `list_questions` zwraca katalog z warunkami ocenionymi na bieżącym Profilu —
sygnały sprawdza agent w plikach repo, Python niczego nie skanuje. Odpowiedź ląduje tam, gdzie
wskazuje `sets:` (klucz Profilu albo `paths.<tier>` → `## Ścieżki` w `.ai/project.md`), a pytania
tak/nie dopisują `include:` / `patterns:` z `on_yes:`.

Moduły układu katalogów (`stack:frontend:*`) nie wchodzą do Bundli — `layouts:` w manifeście
wybiera podpowiedź drzewka dla kombinacji web/mobile (np. `web: react` + `mobile: expo` →
`react-expo-split`), `web: expo` + `mobile: react-native` daje ostrzeżenie, brak drzewka →
domyślne ścieżki (`backend/`, `frontend/web/`, `frontend/mobile/`; Expo unified: `frontend/`).

### Tagi / facety (planowane — jeszcze nie w CLI)

Gdy wiele projektów dzieli **ten sam** powtarzalny wariant instrukcji (np. sklep fizyczny vs cyfrowy), zamiast mnożyć presety `shop-jewelry` / `shop-tokens`:

1. W `manifest.yaml` → `mappings.tiers.<tier>` dopisać dozwolone Stacki (np. `fulfillment` nie — Tiery to backend/web/mobile; nowy wymiar trafia do `decisions` albo `capabilities`).
2. W mcp.json dodać np. `"--tag", "physical"` albo `"--facet", "fulfillment=physical"` (docelowa składnia przy implementacji).
3. Resolver dołoży wtedy dodatkowe MD z `modules/` — bez lokalnego forka, jeśli zestawy capabilities są te same.

**Teraz:** różnice jubiler vs tokeny → `.ai/project.md`. Tagi włączaj dopiero gdy wariant wraca w ≥2–3 projektach.

Szkic (nie działa jeszcze):

```json
"args": [
  "--from", "…",
  "guides-mcp",
  "--tag", "physical",
  "--tag", "b2c",
  "--workspace", "${workspaceFolder}"
]
```



### Bootstrap

```bash
# Generyczny — profil z Tierami + --language pl
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp \
  --with-overlay

# Tylko Cursor
./scripts/bootstrap-project.sh /sciezka/do/projektu \
  --clients cursor \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp

# Proza EN, wszyscy klienci AI (Stacki potem w .ai/project.profile.yaml)
./scripts/bootstrap-project.sh /sciezka/do/moj-sklep \
  --language en \
  --clients all \
  --from /absolutna/sciezka/do/ai-instruction-kit-mcp
```

**Agenci per Tier:** agenci z `tier:` we frontmatterze (`templates/shared/agents/`) trafiają do klienta tylko przy wybranym Tierze — `tier: backend` (`review-backend`, `teacher-backend`, `subagent-backend`) gdy `backend ≠ none`, `tier: client` (`review-frontend`, `teacher-frontend`, `subagent-frontend`, `review-ui`) gdy `web` lub `mobile ≠ none`. Tier zmieniony na `none` + `kit-ai reload` = ich pliki znikają u wszystkich klientów. Agenci nie zakładają Stacka — biorą go z `get_bundle`. `BUGBOT.md` dostaje sekcje (`<!-- tier:backend -->`, `<!-- tier:client -->`) tylko wybranych Tierów.

Zapisuje m.in. MCP per klient (`--language`, `--clients`, `--workspace`), agents z `templates/shared/agents`, `BUGBOT.md` w root (wszyscy klienci) + `.cursor/BUGBOT.md` (natywny Cursor BugBot), skill Cursor `/compact`, hooki `gate-*` (Cursor), stamp `.ai/.kit-bootstrap.json` (patrz "Update kita w projekcie"). Wymaga **Python 3** (`python3` albo `python` z major==3).

**Declarative sync klientów:** domyślnie bootstrap **usuwa** kitowe pliki klientów spoza `--clients` (np. przełączenie z `--clients all` na `--clients claude` sprząta `.cursor/`, `.codex/` itd. wygenerowane przy poprzednim bootstrapie). Flaga `--keep-unselected-clients` wyłącza to sprzątanie — zostają pliki wszystkich klientów kiedykolwiek bootstrapowanych.

### `.gitignore` — co z tego wersjonować

Bootstrap wstawia do `.gitignore` repo aplikacji sekcję między markerami
`# >>> instruction-kit >>>` i `# <<< instruction-kit <<<`. Przy kolejnych przebiegach
podmienia ją w całości, więc wpisy się nie duplikują, a reguły spoza markerów zostają
nietknięte. Źródło: `templates/gitignore-kit.txt`.

Zasada: **konfiguracja AI jest częścią repo.** Hooki bezpieczeństwa, agenci i komendy mają
działać u każdego, kto sklonuje projekt — nie tylko na maszynie, gdzie odpalono bootstrap.
Poza gitem zostaje lokalny stan klienta, to, co i tak żyje globalnie, oraz pliki, które
bootstrap renderuje **ze ścieżką tej maszyny**:

| Wersjonowane | Ignorowane |
| --- | --- |
| `.claude/{agents,commands,hooks,skills}/`, `.claude/settings.json` | `.claude/settings.local.json` (uprawnienia per maszyna) |
| `.codex/skills/` | `.codex/config.toml` (MCP), reszta `.codex/` (stan sesji) |
| `.github/prompts/`, `.github/copilot-instructions.md`, `.github/hooks/rtk-rewrite.json` | `.vscode/mcp.json` (MCP) |
| `AGENTS.md`, `BUGBOT.md`, `.ai/project.md` | `.mcp.json`, `.cursor/mcp.json`, `.kiro/settings/mcp.json`, `.kilocode/mcp.json`, `.agents/mcp_config.json`, `opencode.json` (MCP), `.ai/.kit-bootstrap.json` (stamp) |
| — | `.agents/skills/`, `skills-lock.json` (skille z `npx skills add` — instalowane globalnie w `~/.agents/skills/`, kopia w repo zaraz rozjedzie się z globalną) |

**Konfigi MCP i stamp są per maszyna, nie per repo.** Przy `--from <lokalny klon>` bootstrap
wpisuje do nich absolutną ścieżkę klona (`uv run --project`, `--kit-root`), a dla Codex
i opencode absolutny `--workspace`. Zacommitowane z Windowsa (`M:/projects/…`) na Linuksie
dają `CONNECTION_CLOSED` bez czytelnego powodu. Każdy odbiornik — PC, laptop, serwer —
odpala `kit-ai reload` u siebie; język i klienci są w zacommitowanym Profilu, więc nic
więcej nie trzeba pamiętać.

Repo zbootstrapowane wcześniej mają te pliki w indeksie — sam wpis w `.gitignore` ich nie
odśledzi. Bootstrap wykrywa to i wypisuje gotową komendę (pliki zostają na dysku):

```bash
git -C "$APP" rm --cached .mcp.json .vscode/mcp.json .codex/config.toml .ai/.kit-bootstrap.json
```

Typowy `.gitignore` ma `.claude/` wpisane hurtem — wtedy hooki i komendy nigdy nie trafiają
do repo, a bootstrap trzeba powtarzać na każdej maszynie. Reguły kita są w formie „ignoruj
katalog, odwróć dla plików kita", bo git nie wchodzi do zignorowanego katalogu i sam wyjątek
na plik by nie wystarczył.

### Bootstrap bez klona kita — narzędzie MCP `bootstrap_workspace`

Jeśli projekt ma już podłączony serwer MCP `project-guides`, kita nie trzeba klonować ani ręcznie odpalać skryptu — serwer ma szablony pod ręką i uruchamia ten sam `bootstrap-project.sh` u siebie. Poproś agenta o wywołanie narzędzia:

```text
bootstrap_workspace()                          # dry run — tylko lista plików
bootstrap_workspace(dry_run=False)             # instalacja
bootstrap_workspace(clients="claude", with_overlay=True, dry_run=False)
```

Odświeżenie z Profilu (= `kit-ai reload`, łącznie z migracją starej konfiguracji) robi `reload_workspace()` / `reload_workspace(dry_run=False)`.

Argumenty `bootstrap_workspace` (`clients`, `language`, `with_overlay`, `keep_unselected_clients`) odpowiadają flagom skryptu; pominięte biorą wartość z parametrów startowych serwera MCP. Cel zapisu to `--workspace` / `GUIDES_WORKSPACE` — **bez niego narzędzie odmawia**, zamiast zapisywać do katalogu, z którego przypadkiem wystartował proces serwera.

`dry_run=True` jest domyślne i nic nie zapisuje: skrypt leci na kopii kitowej powierzchni repo w katalogu tymczasowym, a raport pokazuje pliki nowe, nadpisane i **usunięte** przez sprzątanie klientów spoza `--clients`. Plan pochodzi więc z faktycznego przebiegu skryptu, nie z drugiej listy ścieżek w Pythonie.

> **Uwaga na bramki.** Hooki kita (`PreToolUse`) łapią `Bash`, `PowerShell` i `Edit|Write|MultiEdit|NotebookEdit` — nie nazwy narzędzi MCP. To jedyne zapisujące narzędzie tego serwera i hooki go **nie zatrzymają**; `dry_run=True` jako domyślka plus wymóg jawnego `dry_run=False` są tu całą ochroną. Reszta narzędzi serwera pozostaje tylko do odczytu.

## MCP w innych klientach (multi-client)

Kanon treści: `templates/shared/{agents,rules}`. Adaptery IDE trzymają tylko format MCP / ścieżki natywne. Bootstrap `--clients` instaluje wybrane pakiety (default `all`).


| Klient                   | Id `--clients` | Plik MCP w aplikacji              | Klucz top-level                  | Szablon                          |
| ------------------------ | -------------- | --------------------------------- | -------------------------------- | -------------------------------- |
| Cursor                   | `cursor`       | `.cursor/mcp.json`                | `mcpServers`                     | `templates/cursor/mcp.json`      |
| Claude Code              | `claude`       | `.mcp.json` (root)                | `mcpServers`                     | `templates/claude/mcp.json`      |
| Codex CLI                | `codex`        | `.codex/config.toml`              | `[mcp_servers.x]` (TOML)         | `templates/codex/config.toml`    |
| GitHub Copilot (VS Code) | `vscode` (alias `copilot`) | `.vscode/mcp.json`     | `servers` (**nie** `mcpServers`) | `templates/vscode/mcp.json`      |
| Kiro                     | `kiro`         | `.kiro/settings/mcp.json`         | `mcpServers`                     | `templates/kiro/settings/mcp.json` |
| Kilo                     | `kilo`         | `.kilocode/mcp.json`              | `mcpServers`                     | `templates/kilo/mcp.json`        |
| Antigravity              | `antigravity`  | `.agents/mcp_config.json`         | `mcpServers`                     | `templates/antigravity/mcp_config.json` |
| opencode                 | `opencode`     | `opencode.json` (root)            | `mcp` (`type: "local"`)          | `templates/opencode/opencode.json` |


Zmienna dla `--workspace`:


| Klient          | Zmienna                                     |
| --------------- | ------------------------------------------- |
| Cursor, VS Code, Kiro, Kilo, Antigravity | `${workspaceFolder}`             |
| Claude Code     | `${CLAUDE_PROJECT_DIR:-.}`                  |
| Codex CLI, opencode | ścieżka absolutna (brak stabilnej zmiennej) |




## Instalacja per klient (krok po kroku)

Wspólne dla wszystkich: `git clone` / masz kita lokalnie → uruchom `bootstrap-project.sh` w **repo aplikacji** (nie w repo kita) z `--from` wskazującym na kita → zrestartuj IDE.

```bash
./scripts/bootstrap-project.sh /sciezka/do/mojej-appki \
  --from /m/projects/ai-instruction-kit-mcp \
  --clients cursor \
  --with-overlay
```

| Klient | `--clients` | Wymaga poza kitem | Extra config po bootstrapie |
| --- | --- | --- | --- |
| Cursor | `cursor` | Cursor IDE | Ustaw `--from` w `.cursor/mcp.json` jeśli nie `uvx`-owalny git remote. Hooki (`gate-*`) działają od razu — wymagają `bash` w PATH (Windows: Git Bash) |
| Claude Code | `claude` | `claude` CLI albo desktop app | `.mcp.json` w root — Claude Code czyta go automatycznie po `cd` do repo. `.claude/commands/*.md` = prawdziwe `/nazwa`, `.claude/agents/*.md` = subagenty (Task tool) |
| Codex CLI | `codex` | `codex` CLI | `.codex/config.toml` wymaga absolutnej ścieżki w `--workspace` (brak `${workspaceFolder}`) — bootstrap wypełnia sam z `TARGET` |
| GitHub Copilot (VS Code) | `vscode` (alias `copilot`) | VS Code + rozszerzenie GitHub Copilot Chat | `.vscode/mcp.json` (`servers`, nie `mcpServers`) + `.github/prompts/*.prompt.md` (Copilot Chat `/nazwa`) + `.github/copilot-instructions.md` + `.github/hooks/rtk-rewrite.json` (`rtk hook copilot` — jedyny klient bez trybu globalnego rtk, więc hook idzie z kita). Wymaga w VS Code ustawienia `chat.promptFiles: true` (część wersji ma to domyślnie) |
| Kiro | `kiro` | Kiro IDE | `.kiro/settings/mcp.json` + `.kiro/steering/instruction-kit.md` + `.kiro/agents/` — format agentów kopiowany 1:1, **niezweryfikowany na żywym Kiro** |
| Kilo Code | `kilo` | rozszerzenie Kilo Code | `.kilocode/mcp.json` + `.kilocode/workflows/*.md` (`/nazwa`, `$ARGUMENTS` wspierane) |
| Google Antigravity | `antigravity` | Antigravity IDE | `.agents/mcp_config.json` + `.agents/workflows/*.md` (`/nazwa`; limit 12 000 znaków/plik — kit przycina) |
| opencode | `opencode` | `opencode` CLI | `opencode.json` w root (klucz `mcp`, `type: "local"`, `command` jako tablica) + `.opencode/command/*.md` (`/nazwa`, `$ARGUMENTS`) |

Wiele klientów naraz: `--clients cursor,claude` albo `--clients all`. Każdy klient dostaje **ten sam** `--language`/`--workspace` — różni się tylko format pliku MCP i ścieżka komend.

Po bootstrapie zawsze: **zrestartuj IDE/CLI** (MCP i komendy ładują się przy starcie), potem sprawdź że MCP wstał (np. `get_bundle` / lista narzędzi w kliencie).

## Czego kit **nie robi** / brakujące komendy

Świadome braki — nie zgłaszaj jako bug, tylko sprawdź czy potrzebujesz obejścia niżej:

| Brak | Status | Obejście |
| --- | --- | --- |
| `--tag` / facety wariantów | Zaprojektowane, **nie w CLI** | Różnice trzymaj w `.ai/project.md` dopóki wariant nie powtórzy się w ≥2–3 projektach |
| `--profile` / `--preset` / `--codegen` | Usunięte (serwer je ignoruje, bootstrap odmawia) | Profil zawsze `.ai/project.profile.yaml` w `--workspace`; migracja przez `kit-ai reload` |
| `/review-security` jako plik kita | Nie istnieje w `templates/shared/agents/` | To skill user/global (Cursor) — dodaj we własnym środowisku, kit go nie dostarcza |
| `/compact` poza Cursorem | Nie istnieje dla Claude/Codex/inne | To alias Cursor UI Summarize; Claude Code ma **wbudowane** `/compact` — nie koliduj, nie kopiuj |
| Natywna weryfikacja formatu VS Code/Kilo/Antigravity/opencode | Oparta o dokumentację (sierpień 2026), **nie testowana na żywych klientach** | Jeśli `/nazwa` nie działa w Twoim kliencie, zgłoś i popraw `scripts/render_agent_commands.py` |
| Auto-instalacja Superpowers/Autopilot | Niemożliwa ze skryptu (marketplace pluginów Claude/Cursor, wymaga interaktywnego `/plugin install`) | `--with-plugins` wypisze dokładne komendy/kroki, patrz niżej |

## Pluginy zewnętrzne — schemat użycia (4 warstwy)

Kit **nie** bundluje tych pluginów w `guides-mcp` (różna dystrybucja: MCP vs Claude/Cursor plugin marketplace vs npx skill). Pełna tabela warstw i priorytet źródeł: `AGENTS.md`.

```text
1. Fundament   — ten kit (MCP + /git-* + /review-*)     → instaluje bootstrap
2. Proces      — mattpocock/skills (/grill-me, /tdd)     → npx skills@latest add mattpocock/skills
3. Meta/izolacja — Superpowers (worktree, finishing…)     → Claude Code: /plugin marketplace add obra/superpowers-marketplace
                                                              /plugin install superpowers@superpowers-marketplace
4. PR → green  — Autopilot (Cursor)                       → Cursor: Settings → Extensions/Skills → Autopilot
```

Nie mieszaj warstw: kit = prawda o stacku i nazwach branchy, Matt = proces feature, Superpowers = sesja/worktree/finisz, Autopilot = dociąganie PR.

**Auto-instalacja przy bootstrapie:** `--with-plugins` (best-effort, opt-in — nic nie instaluje się bez tej flagi):

```bash
./scripts/bootstrap-project.sh ../moj-projekt \
  --clients claude \
  --from /m/projects/ai-instruction-kit-mcp \
  --with-plugins
```

Co robi: odpala `npx skills@latest add mattpocock/skills` w `TARGET` (wymaga `npx`/Node.js w PATH; best-effort — błąd nie przerywa bootstrapu), i wypisuje gotowe komendy do Superpowers/Autopilot (te dwa wymagają interaktywnego kroku w kliencie, nie da się ich odpalić z bash). TDD: jeden path na feature — domyślnie Matt `/tdd`, nie mieszaj z Superpowers TDD.

## Katalog modułów

```text
modules/
  core/              repo-first, workflow, typing, code-review, language-*, tooling-rtk
  architecture/      platforms, CI/CD, API (REST/GraphQL), security, testing, i18n,
                     taskfile, docker-structure, …
  stacks/
    django-drf/      (+ django/, fastapi/, flask/ layouts)
    expo-router/
    frontend/        warianty Expo/React (macierz web/mobile — design)
  capabilities/      auth (+ allauth/jwt/custom warianty), files, payments (+ expo-stripe gdy Tier expo), …
  patterns/          capability-provider, providers-and-settings, gateway, webhooks, …
  infra/             database, cache, queue, storage, tasks, search
templates/
  shared/            kanon agents + rules (źródło prawdy)
  cursor|claude|…    adaptery MCP / format IDE
```



## Sloty infrastruktury (`decisions`)

```yaml
decisions:
  database: postgres      # → infra:database:postgres
  cache: redis            # → infra:cache:redis
  queue: redis            # → infra:queue:redis  (lub rabbitmq)
  storage: s3             # → infra:storage:s3
  tasks: celery           # → infra:tasks:celery
  search: postgres        # → infra:search:postgres (lub meilisearch)
```

Moduły infra trafiają automatycznie do bundle `infra` i `devops`.

**Dodanie nowej technologii nie wymaga Pythona** (ADR-0001). Trzy kroki:

1. Napisz `modules/infra/queue/kafka.md`.
2. Zarejestruj go w `manifest.yaml` → `modules:`.
3. Dopisz wartość w `manifest.yaml` → `mappings.slots.queue.kafka`.

Nierozpoznana Decyzja (literówka `postgress`, technologia bez modułu) **nie wywraca
serwera** — ląduje w sekcji „Nierozpoznane decyzje" w `get_index` (ADR-0004).

## Wariant auth (`decisions.auth`)

```yaml
decisions:
  auth: custom      # default — brak enforced pakietu, opisz w .ai/project.md
  # auth: allauth   # → capability:auth:allauth (django-allauth headless)
  # auth: jwt       # → capability:auth:jwt (djangorestframework-simplejwt)
```

Inny mechanizm niż infra: nie tworzy osobnego bundle'a — dokleja się zaraz po
`capability:auth` wszędzie tam, gdzie ten moduł już jest wypisany w bundle
(`capabilities: [auth]` albo `include:` z ID modułu — routing wg tagów).
W manifeście to `mappings.variants.auth` (Wariant = wstaw po module bazowym),
w odróżnieniu od `mappings.substitutions.codegen` (Substytucja = podmień moduł bazowy).

## Słownik i decyzje

| Plik                       | Rola                                                                      |
| -------------------------- | ------------------------------------------------------------------------- |
| [`CONTEXT.md`](CONTEXT.md) | Ubiquitous language kita — Bundle, Preset, Slot, Wariant, Alias, Overlay… |
| [`docs/adr/`](docs/adr/)   | Decyzje architektoniczne z uzasadnieniem (dlaczego tak, a nie inaczej)    |

Nazwy z `CONTEXT.md` obowiązują w kodzie, docstringach i review. Zanim zaproponujesz
zmianę architektury, sprawdź `docs/adr/` — część rzeczy już rozstrzygnięto.

## Bundle'e MCP


| Bundle         | Zastosowanie                                |
| -------------- | ------------------------------------------- |
| `backend`      | Stack z Tieru backend, capabilities BE      |
| `frontend`     | Stacki z Tierów web i mobile, UI/UX         |
| `payments`     | Stripe, webhooks                            |
| `architecture` | monorepo, kontrakt API, capability-provider |
| `infra`        | postgres, redis, queue, s3, celery          |
| `devops`       | CI/CD + infra                               |
| `full`         | wszystko + infra                            |




## Bootstrap w projekcie docelowym

W **repo aplikacji** uruchom `scripts/bootstrap-project.sh` albo skopiuj z `templates/`:


| Plik                                | Rola                                                                    | Wymagany?            |
| ----------------------------------- | ----------------------------------------------------------------------- | -------------------- |
| `.cursor/mcp.json`                  | uvx → `--language` + `--clients` + `--workspace`; **per maszyna, poza gitem** | tak (Cursor)        |
| `.mcp.json` / `.codex/` / `.vscode/` / … | MCP per klient z `--clients`; **per maszyna, poza gitem**  | wg wybranego klienta |
| `.ai/project.md`                    | Overlay — Taskfile, Docker, porty           | zalecany             |

| `.ai/project.profile.yaml`          | Tiery (backend/web/mobile) + `codegen:` — jedyna konfiguracja kita                                              | **tak** |
| `.cursor/rules/use-guides.mdc`      | Bootstrap MCP                                                           | tak                  |
| `.cursor/rules/code-review.mdc`     | Review przed pushem                                                     | tak                  |
| `.cursor/rules/git-branch-pr.mdc`   | `/git-start`+`/git-check`+`/git-commit`+`/git-end`, issue#, chronione main/master/dev | tak                  |
| `.cursor/BUGBOT.md`                 | Reguły Bugbota                                                          | tak                  |
| `.cursor/hooks.json` + `hooks/invoke-hook.js` + `hooks/*.mjs` | Guardy: git-guard + sensitive-files (adapter → node) | tak                  |
| `AGENTS.md`                         | Cienki — odsyła do MCP                                                  | tak                  |
| `.cursor/agents/*.md`               | Subagenty `/review-*`, `/subagent-*`, `/git-*`                          | zalecany             |
| `.cursor/skills/compact/`           | **Tylko Cursor:** `/compact` = alias UI Summarize (nie Claude/Codex)    | zalecany (Cursor)    |


W projekcie docelowym **nie** duplikuj `modules/` — wystarczy profil z Tierami + opcjonalny overlay.

## Update kita w projekcie

Bootstrap to **jednorazowy stempel**, nie sync. Trzy różne zachowania:

| Co | Przy ponownym `bootstrap-project.sh` |
| --- | --- |
| `.claude/agents/`, `.cursor/agents/`, `.claude/commands/`, `mcp.json`/`config.toml` | **Zawsze nadpisane** świeżą kopią z kita — traktuj jak wygenerowany kod, nie edytuj ręcznie. `mcp.json`/`config.toml` i stamp dodatkowo **nie są wersjonowane** (ścieżka maszyny) — patrz „`.gitignore` — co z tego wersjonować” |
| `AGENTS.md`, `BUGBOT.md`, `.ai/project.md`, `git-hooks/pre-push` | Kopiowane **tylko jeśli brak** — bootstrap nigdy więcej ich nie tyka, update ręczny. `check_kit_status` wypisuje je w osobnej sekcji „wymagają ręcznego przeniesienia", żeby nie obiecywać nadpisania, którego nie zrobi |
| `modules/*.md` (treść instrukcji) | **W ogóle nie kopiowane** — MCP czyta je z `--kit-root` przy każdym `get_bundle`/`get_overlay`. Aktualne bez re-bootstrapu **pod warunkiem**, że serwer wie, gdzie jest klon — patrz niżej |

### Lokalny klon: `uv run --project`, nie `uvx --from`

`uvx --from <katalog>` **nie** czyta kita z tego katalogu w czasie działania. uv buduje koło,
w którym `manifest.yaml` i `modules/` lądują jako `guides/_data`
(`force-include` w `pyproject.toml`), i cache'uje je pod **wersję pakietu**. Wersja nie rośnie
przy zwykłej edycji modułu ani kodu serwera, więc klient dostaje kopię sprzed builda.
Do tego `find_kit_root()` woli `_data` od repo, więc `check_kit_status` traci historię gita.

Objaw: poprawiasz `modules/…`, restartujesz klienta, a `get_bundle` wciąż zwraca starą treść.
Bez komunikatu błędu. To samo dotyczy poprawek w `src/guides/` — serwer nadal biegnie na
starym kodzie.

Dlatego przy źródle lokalnym bootstrap generuje:

```json
"command": "uv",
"args": ["run", "--project", "/sciezka/do/klona", "guides-mcp", …,
         "--kit-root", "/sciezka/do/klona", …]
```

Pakiet ma układ `src/`, więc `uv run` instaluje go jako editable — `_data` w ogóle nie
powstaje, a kod i moduły czytane są wprost z klonu. `--kit-root` nie jest wtedy konieczny,
ale zostaje: nazywa klon wprost, zamiast pozwalać serwerowi go wnioskować.

Przy źródle zdalnym (`git+https://…`) nic się nie zmienia — zostaje `uvx --from`, bo klonu
nie ma, a `_data` z koła jest jedyną i aktualną kopią.

Projekty zbootstrapowane przed tą zmianą mają w `mcp.json` stare `uvx --from` albo
`uv run --directory` — wystarczy `kit-ai reload`.

Skąd wiedzieć **kiedy** re-bootstrapować (bez ciągłego czytania plików kita — tanie, jedno porównanie commitów):

```text
MCP tool: check_kit_status
```

Bootstrap zapisuje `.ai/.kit-bootstrap.json` (commit kita w momencie bootstrapu). `check_kit_status`
porównuje go z aktualnym `HEAD` kita (`git rev-parse` + `git diff --name-only` tylko na ścieżkach
które bootstrap faktycznie kopiuje) i zwraca: aktualny / zmienił się (+ lista plików) / brak stampu
(stary bootstrap sprzed tej funkcji) / brak lokalnej historii git (gdy `--from` to zdalny URL, nie
lokalny klon). Zero kosztu tokenów na nawigację plików — jedno wywołanie tool, agent woła je kiedy
chce sprawdzić stan (np. na początku sesji), nie w pętli.

Gdy pokaże zmiany: `bootstrap-project.sh` ponownie z tymi samymi flagami co poprzednio.

## Slash commands — konwencja nazw


| Prefiks       | Rola                                                 | Przykłady                                                                                                                                          |
| ------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/compact`    | **Cursor only** — alias UI Summarize w tym projekcie | `/compact`                                                                                                                                         |
| `/git-*`      | Start / sync issue / commit / PR                   | `/git-start`, `/git-check`, `/git-commit`, `/git-end`                                                                                               |
| `/create-task` | Pomysł → ocena na tle repo → issue (bez brancha)   | `/create-task`, `/create-task "eksport CSV"`; flagi: `/create-task --help`                                                                          |
| `/create-skill` | Pomysł na skill → skill czy agent → issue (bez brancha) | `/create-skill`, `/create-skill "konwencje migracji"`; flagi: `/create-skill --help`                                                            |
| `/review-*`   | Review tylko do odczytu, raport                      | `/review-backend`, `/review-frontend`, `/review-architecture`, `/review-ui`, `/review-edge`, `/review-tests`, `/review-bugbot`, `/review-security` |
| `/subagent-*` | Praca w dwóch oknach (wymiana raportów)              | `/subagent-backend`, `/subagent-frontend`                                                                                                          |
| `/night-run`  | Nocna praca na liście issue pod `/goal`              | `/goal Wykonaj #150–#157 wg /night-run …`                                                                                                          |




### `/compact` (wyłącznie Cursor)

Skill: `templates/cursor/skills/compact/SKILL.md` → **tylko** `.cursor/skills/compact/`.

Bootstrap **nie** kopiuje tego do Claude / Codex. Nie nadpisuje ani nie „tłumaczy” ich wbudowanego `/compact`.

- **Po co:** w Cursorze jedna komenda `/compact` zamiast szukania UI **Summarize**.
- **Nie** jest wspólną konwencją kita cross-tool.
- **Nie** mylić z `/handoff` (plik + nowy chat).

```text
/compact
```



### `/git-start`, `/git-check`, `/git-commit`, `/git-end` + Superpowers + Autopilot

Wymaga `gh` + `git`. Konwencja: `feat/42-add-cart-coupon`. Pełne zasady: `.cursor/rules/git-branch-pr.mdc`.

#### Podział ról (czytelnie)


| Krok                     | Narzędzie                                                                  | Uwagi                                        |
| ------------------------ | -------------------------------------------------------------------------- | -------------------------------------------- |
| Scope / TDD              | Matt `/grill-me`, `/tdd`                                                   | `/grill-me` tylko przy niejasnym scope; nie mieszać z Superpowers TDD |
| Issue + branch           | `/git-start` (kit)                                                         | Numeracja issue, Conventional name           |
| Sync issue ↔ diff        | `/git-check` (kit)                                                         | Gdy tytuł/body rozjechały się z plikami      |
| Commit(y)                | `/git-commit` (kit)                                                        | Conventional; `--one` / `--split` / `--dry-run` |
| Izolacja (opc.)          | Superpowers `using-git-worktrees`                                          | Na branchu z `/git-start`, nie zamiast niego |
| Review przed pushem      | `/review-bugbot` + **minimalny** stack (`/review-backend` i/lub `/review-frontend`) | Nie wszystkie `/review-*` naraz; format: Severity\|Location\|Finding\|Fix |
| Push + PR                | `/git-end` **lub** Superpowers `finishing-a-development-branch` → opcja PR | Jedno z dwóch. `/git-end` = push + PR (`Closes #N`); **bez** merge; brudne tree → najpierw `/git-commit` |
| CI / komentarze aż green | **Autopilot**                                                              | Po istniejącym PR; bez auto-merge            |
| Merge                    | Ty / `gh pr merge`                                                         | Gdy green → GitHub zamyka issue (`Closes #N`) |


```text
Krótko:   /git-start → kod → [/git-check] → /git-commit → /review-bugbot → /git-end → [Autopilot]
Długo:    [/grill-me] → /git-start → worktree → kod → [/git-check] → /git-commit → finishing| /git-end → Autopilot → merge
```


| Komenda kit  | Co robi                                                                                 |
| ------------ | --------------------------------------------------------------------------------------- |
| `/create-task` | Ocena pomysłu na tle repo → karta issue → utworzenie po akceptacji; `--dry-run` / `--quick` / `--split` / `--no-assign` / `--parent #N`. **Nie** zakłada brancha |
| `/create-skill` | Rozstrzyga skill vs agent, potem karta issue z nazwą, `description` i kryterium odpalenia; `--dry-run` / `--quick` / `--no-assign` / `--parent #N`. **Nie** pisze `SKILL.md` |
| `/git-start` | `#N` / opis / **puste = auto-diff** / `--help` (ręcznie: `gh issue create` / `develop`) |
| `/git-check` | Dopasuj tytuł (EN) i body (język MCP) issue do realnego diffa; `--dry-run`              |
| `/git-commit` | Conventional Commit(s) z diffa; `--one` (jeden) / `--split` / `--dry-run`; odpala pre-commit |
| `/git-end`   | Push + PR z `Closes #N` w body; `--help`; alias `/git-pr`. **Nie** merguje i **nie** zamyka issue od razu — issue zamyka się **po merge** PR |
| `/compact`   | **Cursor only** — skrót czatu (alias UI Summarize); nie Claude/Codex                     |


```text
/git-start --help
/git-start feat add cart coupon
/git-start fix #108 login returns 500
/git-start                    # auto z lokalnego diffa
# … praca zmieniła scope …
/git-check
/git-commit                   # lub --one / --split / --dry-run
# … review …
/git-end --help
/git-end
```

Ręczny odpowiednik:

```bash
gh issue create --title "Add cart coupon" --body "…"
gh issue develop 42 --name feat/42-add-cart-coupon --base dev --checkout
# … praca …
git push -u origin HEAD
gh pr create --base dev --title "feat: add cart coupon" --body "Closes #42"
```

UI: GitHub Issue → Development → **Create a branch** (potem nazwij spójnie `typ/N-slug`).


| Slash                                | Plik szablonu                                    |
| ------------------------------------ | ------------------------------------------------ |
| `/create-task`                       | `templates/shared/agents/create-task.md`         |
| `/create-skill`                      | `templates/shared/agents/create-skill.md`        |
| `/git-start`                         | `templates/shared/agents/git-start.md`           |
| `/git-check`                         | `templates/shared/agents/git-check.md`           |
| `/git-commit`                        | `templates/shared/agents/git-commit.md`          |
| `/git-end`                           | `templates/shared/agents/git-end.md`             |
| `/compact` (Cursor)                  | `templates/cursor/skills/compact/SKILL.md`       |
| `/review-architecture`               | `templates/shared/agents/review-architecture.md` |
| `/review-backend`                    | `templates/shared/agents/review-backend.md`      |
| `/review-frontend`                   | `templates/shared/agents/review-frontend.md`     |
| `/review-ui`                         | `templates/shared/agents/review-ui.md`           |
| `/review-edge`                       | `templates/shared/agents/review-edge.md`         |
| `/review-tests`                      | `templates/shared/agents/review-tests.md`        |
| `/review-bugbot`                     | `templates/shared/agents/review-bugbot.md` (manualny odpowiednik natywnego Cursor BugBot — stosuje reguły z `BUGBOT.md` ręcznie, dla klientów bez tej usługi) |
| `/cleanup`                           | `templates/shared/agents/cleanup.md` (znajdź i usuń zbędne scratch/testowe pliki zostawione po weryfikacji — pyta o potwierdzenie) |
| `/subagent-backend`                  | `templates/shared/agents/subagent-backend.md`    |
| `/subagent-frontend`                 | `templates/shared/agents/subagent-frontend.md`   |
| `/teacher-backend`                   | `templates/shared/agents/teacher-backend.md`     |
| `/teacher-frontend`                  | `templates/shared/agents/teacher-frontend.md`    |
| `/teacher-architecture`              | `templates/shared/agents/teacher-architecture.md` |
| `/teacher-agent`                     | `templates/shared/agents/teacher-agent.md`       |
| `/review-security`                   | skille Cursor (user/global), nie ten kit         |

### `/teacher-*` — tryb nauki (przed kodem, nie po)

`/review-*` sprawdza **gotowy diff** i zwraca tabelę findingów. `/teacher-*` działa **zanim** napiszesz kod: bierze Twoją koncepcję (albo bieżący diff, gdy nie podasz argumentu), tłumaczy o co w problemie naprawdę chodzi, pokazuje max 3 opcje z kosztami, wskazuje **jedną** rekomendację i zostawia Ci zadanie do zrobienia samodzielnie.

| Komenda | Zakres |
| --- | --- |
| `/teacher-backend` | Django/DRF (opc. FastAPI, Flask+Pydantic): warstwy, modele, migracje, transakcje, Celery, ACL, pytest, uv/ruff |
| `/teacher-frontend` | React, React Native/Expo Router (opc. Angular): stan serwera vs klienta, granice komponentów, re-rendery, web/native, typy TS, RTL/Playwright |
| `/teacher-architecture` | granice FE/BE, kontrakt API, kiedy **nie** dzielić, infra (Postgres/Redis/Celery/S3), Docker+Taskfile, odwracalność decyzji, ADR |
| `/teacher-agent` | praca z samymi agentami: skille, worktree i izolacja zadań, delegacja do subagentów, autonomia (`/goal` vs `/loop`), pisanie promptów, jak spiąć `/git-*` i `/review-*` w jeden flow |

Kontrakt tych agentów: `readonly` — **nie edytują plików**, nie dają gotowca do wklejenia (szkic ≤ 20 linii), nazywają wzorce po imieniu i mówią wprost, gdy koncepcja jest zła. Czytają `get_bundle` + `get_overlay`, więc uczą na Twoim stacku i Twoim kodzie, nie na `Foo/Bar`.

```
/teacher-backend czy walidację ceny dać do serializera czy do serwisu
/teacher-frontend                 # bez argumentu → uczy o tym, co masz w git diff
/teacher-architecture czy dodać Redisa pod cache koszyka
```

### `/night-run` — lista issue przez noc

Za dnia grillujesz issue (kryteria akceptacji, relacje blocked-by). W nocy `/goal` pilnuje pętli, a `/night-run` daje procedurę: na każdy ticket `/git-start` → test-first → szybkie bramki → `/git-commit` → review na diffie → `/git-end` → CI → merge → jeden raport na PR i zamknięcie issue. Problem zamiast pytania kończy się komentarzem `needs-human` z pytaniami Q1/Q2 na issue i agent idzie dalej. Pełna procedura: `templates/shared/agents/night-run.md`.

Agent jest **orkiestratorem w głównej sesji** (w Claude przez Skill, nie jako subagent). Sam nie czyta kodu: na ticket odpala świeżego subagenta ticketu, a review robi osobny świeży subagent na samym `git diff`. Dzięki temu żaden kontekst nie puchnie do 200k, a każda tura nie czyta go od nowa. Niczego nie dopisujesz do overlay:

- **Gałąź bazowa:** `dev`, jeśli `origin/dev` istnieje i nie jest w tyle za gałęzią domyślną; inaczej gałąź domyślna repo. Porzucony `dev` nie przejmie nocy.
- **Plik kontekstu nocy** (`/tmp/night-run-<repo>-<data>/context.md`): mapa aplikacji, konwencje, pułapki toolchainu z pamięci projektu i overlay. Po każdym tickecie orkiestrator dopisuje, co doszło (modele, serwisy, endpointy). Subagent czyta ten plik zamiast AGENTS.md, BUGBOT.md i wszystkich ADR-ów.
- **Bramki jakości:** kroki `run:` z `.github/workflows/*.yml` + sekcja kontroli z `.ai/project.md` (i `codegen:`). Lokalnie tylko szybkie (lint, typecheck, `makemigrations --check`, testy dotknięte ticketem); pełny zestaw testów tylko w CI.
- **Model subagenta ticketu:** `model: <nazwa>` w tekście celu; brak → model sesji.
- **Koszt:** po każdym tickecie snippet `python3` liczy z transkryptów subagentów tury, tokeny (input / cache_creation / cache_read / output), maks. kontekst i czas. Wynik trafia do `NIGHT-RUN REPORT`.
- Wybrana baza, bramki, model i każde założenie trafiają do `NIGHT-RUN REPORT`.

Sędzia `/goal` widzi tylko transkrypt, więc warunek żąda dowodów w rozmowie:

```text
/goal Wykonaj issue #150–#157 wg /night-run, model: sonnet. Koniec, gdy w transkrypcie jest
NIGHT-RUN REPORT, w którym każdy ticket ma: MERGED (wynik gh pr view --json state)
albo needs-human (link do komentarza), albo jest wpis "night-run halted".
```

Uwagi dopisujesz za warunkiem („#155 bez PDF”, „bez merge, same PR-y”, „model: sonnet”) — polecenia z celu mają pierwszeństwo przed procedurą. W Claude `model:` przyjmuje tylko aliasy (`sonnet`, `opus`, `haiku`, `fable`); konkretną wersję modelu wybierasz dla całej sesji: `claude --model <id>`.

#### Pomiar kosztu ticketu na różnych modelach

Tańszy token nie znaczy tańszy ticket: mocniejszy model może zrobić mniej tur i mniej poprawek, a koszt nocy to głównie ponowne czytanie kontekstu (cache_read). Porównanie robisz tak:

1. Wybierz **jeden** ticket średniej wielkości (kilka kryteriów akceptacji, jedna aplikacja backendu), bez decyzji o pieniądzach i zgodach, żeby needs-human nie zepsuł porównania. Zapisz commit bazowy: `git rev-parse origin/<BASE>`.
2. Na każdy model osobny worktree z tego commitu i osobna sesja z dokładnym id modelu:
   ```bash
   git worktree add ../measure-<model> <commit>
   cd ../measure-<model> && claude -p --model <id> "/night-run #<N>, bez merge"
   ```
3. PR służy tylko do pomiaru: po zebraniu wyników `gh pr close <PR> --delete-branch` i `git worktree remove ../measure-<model>`.
4. Metryki: snippet z sekcji „Pomiar kosztu ticketu” w agencie, uruchomiony na transkryptach sesji i jej subagentów (`~/.claude/projects/<projekt>/<sesja>.jsonl` i `…/<sesja>/subagents/*.jsonl`). Koszt liczysz **osobno** dla input, cache_creation, cache_read i output według aktualnego cennika, nie jedną stawką.
5. Jakość: CI zielone za pierwszym razem (t/n), liczba rund poprawek, potwierdzone findingi review, needs-human (t/n).
6. Limit: ile ticketów mieści się w jednym oknie limitu sesji. Okno nie jest publiczne, więc szacujesz: zużycie na ticket w stosunku do zużycia skumulowanego w chwili HTTP 429 we wcześniejszym przebiegu.

Wynik (tabela + rekomendacja modelu domyślnego) trafia do issue pomiaru; zmiana domyślnego modelu to jedna linijka w agencie.


Bootstrap (`--clients`) kopiuje/renderuje shared agents do natywnych ścieżek każdego klienta. Format i mechanizm różnią się per klient:

- **Cursor**: `.cursor/agents/` — natywne slash commands, działa 1:1.
- **Claude Code**: `.claude/agents/` (subagenty, wywołanie przez Task/Agent tool) **oraz** `.claude/commands/` (prawdziwe slash commands `/git-start` itd. — `$ARGUMENTS` wstrzyknięty automatycznie przy kopiowaniu).
- **Codex**: agenty instalowane jako natywne skille w `.codex/skills/<nazwa>/` (renderowane z `templates/shared/agents/*.md` przez `scripts/install_shared_skills.py`). Custom prompts (`.codex/agents/*.toml`) zostały wycofane w Codex CLI — Codex sam ładuje SKILL.md, gdy `description` pasuje do sytuacji.
- **Kiro**: `.kiro/agents/` — kopiowane 1:1, format niezweryfikowany na żywym Kiro.
- **VS Code/Copilot**: `scripts/render_agent_commands.py vscode` → `.github/prompts/*.prompt.md` (wywołanie `/nazwa` w Copilot Chat).
- **Kilo**: `scripts/render_agent_commands.py kilo` → `.kilocode/workflows/*.md` (wywołanie `/nazwa`, `$ARGUMENTS` wspierane).
- **Antigravity**: `scripts/render_agent_commands.py antigravity` → `.agents/workflows/*.md` (wywołanie `/nazwa`; limit 12 000 znaków/plik, kit przycina jeśli trzeba).
- **opencode**: `scripts/render_agent_commands.py opencode` → `.opencode/command/*.md` (wywołanie `/nazwa`, `$ARGUMENTS` wspierane).
  Do tego `/goal` i `/loop` jak w Claude Code: `templates/opencode/command/{goal,loop}.md` + plugin `.opencode/plugins/kit-loop.js`, który po `session.execution.succeeded` wysyła kolejną turę. Stop: `<promise>DONE</promise>` w odpowiedzi, Esc, `/goal clear` / `/loop stop`, limit tur (goal 25, loop 10, `max=N`); `/loop 5m <zadanie>` powtarza co interwał.

Formaty VS Code/Kilo/Antigravity/opencode oparte o publiczną dokumentację tych klientów (sierpień 2026) — nie testowane na żywych instalacjach; jeśli coś nie zadziała, zgłoś różnicę i popraw `scripts/render_agent_commands.py`.

Po skopiowaniu/wyrenderowaniu **zrestartuj** okno IDE — agenty/komendy ładują się przy starcie.

### Wywołanie

```text
/git-start feat #42 cart coupon   # lub bez # — utworzy issue
/git-check                        # gdy diff rozjechał się z opisem issue
/git-commit                       # Conventional Commit(s)
/review-backend przejrzyj zmiany w backend/apps/products/
/git-end
```

```text
/subagent-backend przejrzyj zmiany…   # potem wklej raport do /subagent-frontend w drugim oknie
```



## Skille kita — wspólne źródło

Skill to wiedza, którą model ładuje **sam**, gdy `description` pasuje do sytuacji —
w odróżnieniu od agenta (`/nazwa`), którego ktoś musi wywołać. Jedno źródło:
**`templates/shared/skills/<nazwa>/SKILL.md`** (+ opcjonalne `references/`, `scripts/`,
`assets/`). Rozkłada je `scripts/install_shared_skills.py`.

| Klient | Gdzie ląduje | Jak działa |
|--------|--------------|------------|
| claude | `.claude/skills/` | natywnie, z zasobami |
| cursor | `.cursor/skills/` | natywnie, z zasobami (obok Cursor-only `/compact`) |
| antigravity | `.agents/skills/` | natywnie, z zasobami |
| codex | `.codex/skills/` | natywnie, z zasobami |
| vscode | `.github/prompts/` | degradacja: komenda `/nazwa` |
| kiro | `.kiro/agents/` | degradacja: komenda `/nazwa` |
| kilo | `.kilocode/workflows/` | degradacja: komenda `/nazwa` |
| opencode | `.opencode/command/` | degradacja: komenda `/nazwa` |

**Degradacja kosztuje dwie rzeczy:** skill przestaje odpalać się sam (trzeba wpisać
`/nazwa`) i gubi wszystko poza `SKILL.md`, bo komenda to jeden plik. Instalator mówi
o gubionych katalogach na stderr. Skill, którego sens leży w `scripts/`, będzie
w pięciu na osiem klientów wydmuszką — wtedy to prawdopodobnie powinien być agent.

`.claude/skills/` i `.agents/skills/` dzielisz ze skillami spoza kita (`npx skills add`),
więc odznaczenie klienta kasuje tam **tylko** katalogi o nazwach ze wspólnego źródła,
nigdy całego katalogu skilli.

Nowy skill zakładasz przez **`/create-skill`** (issue), a piszesz według skilla
`skill-authoring` — to on trzyma zasady frontmatter, sufity długości i kryteria odpalania.

## Guardrails — bezpieczeństwo

Jedno źródło polityki: **`templates/shared/guards/`**. Bootstrap kopiuje je do katalogu
hooków wybranego klienta (`--clients`), więc Cursor i Claude Code egzekwują dokładnie
te same reguły.

| Guard | Klient | Zachowanie |
|-------|--------|------------|
| `git-guard.mjs` | Claude, Cursor | **deny**: `git reset --hard`, `git clean -f`, force push i zwykły push na `main`/`master`/`dev` (`--force` / `-f` / `--force-with-lease` / plus-refspec), `git branch -D`, `git checkout .` / `checkout --`, rekursywne `rm` na szerokiej ścieżce (`~`, `/`, `..`, katalogi domowe), mutacja / `sed -i` / redirect do `~/.ssh`, `/etc`, `C:\Windows`, `Program Files`, `~/.claude/settings*.json`. Reszta **allow** — także `git stash`, `git restore`, `find -delete`, `rm -rf` w repo |
| `sensitive-files-guard.mjs` | Claude, Cursor | **deny** odczyt i zapis sekretów (`.env*` poza `.env.example|sample|template`, `*.pem|key|p12|pfx`, `id_rsa*`, `id_ed25519*`, `.netrc`, `credentials.json`, `.git/objects|refs|hooks`); **deny** ręczną edycję lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `uv.lock`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`) — odczyt lockfile wolny |
| `bash-guard.mjs` | Claude | Tylko Windows: **deny** `pwsh` / `powershell` / `cmd` uruchamiane z narzędzia Bash — agent używa Git Basha. Narzędzie PowerShell nie jest blokowane |
| `linters-guard.mjs` | Claude | PostToolUse po Edit/Write: format → lint edytowanego pliku (ruff, prettier, eslint, shellcheck, hadolint, yamllint), tylko gdy repo ma config danego narzędzia; wynik wraca do modelu jako `additionalContext`, nigdy nie blokuje |
| `rtk-check.mjs` | Claude | SessionStart: brak `rtk` w PATH lub hooka `rtk hook claude` w `~/.claude/settings.json` → instrukcja `rtk init -g --auto-patch` dla użytkownika; kit sam nic w `~/.claude` nie zmienia |
| `rtk-rewrite.json` | Copilot | `.github/hooks/`: PreToolUse → `rtk hook copilot` przepisuje komendy bash na `rtk <cmd>`. Copilot nie ma globalnego trybu rtk, stąd per-repo z kita. Pozostali klienci (Claude, Cursor, Codex, OpenCode) mają rtk globalnie per maszyna — instrukcja w `modules/core/tooling-rtk.md` |

**Zero `ask`** (ADR 0006): Guard odpowiada `allow` albo `deny`. W auto mode `ask` z hooka
blokuje tak samo jak prompt, więc bramka, która pyta, nie jest automatyczna. Model dostaje
`permissionDecisionReason` i sam dobiera bezpieczną alternatywę. Git odzyska wszystko
w repo; poza repo pilnujemy tylko katalogów systemowych i sekretów — resztę gate'uje
natywna permission klienta (`cwd` + `additionalDirectories`).

**Jeden dialekt, adapter na brzegu.** Skrypty polityki mówią wyłącznie kontraktem
Claude Code (`hookSpecificOutput.permissionDecision`). Cursor ma własny kształt
(`permission`), więc `invoke-hook.js` tłumaczy — i to jedyne miejsce w kicie, które
wie o różnicy między klientami.

| Klient | Wywołanie | Kontrakt |
|--------|-----------|----------|
| Claude Code | `node .claude/hooks/<guard>.mjs` | natywny, bez adaptera |
| Cursor | `node .cursor/hooks/invoke-hook.js <guard>.mjs --to cursor [--tool Read\|Write]` | tłumaczony przez adapter |

Cursor: `beforeShellExecution` → git-guard, `beforeReadFile` → sensitive-files-guard
(`--tool Read`), `preToolUse` z matcherem `Write` → sensitive-files-guard (`--tool Write`).
`--tool` dopisuje `tool_name`, którego payload Cursora nie niesie. Wszystkie wpisy mają
`failClosed: true` — padnięty Guard (brak JSON) blokuje akcję, a nieczytelny payload
daje **deny**. `invoke-hook.js` po wypisaniu JSON **zawsze kończy exit 0** (niezerowy
exit ukrywa payload przy failClosed).

Guardy są w `.mjs` i idą przez `node` — bez basha, więc bez wykrywania Git Basha na
Windows i bez otwartych okien konsoli.

Regresja: `uv run python -m unittest tests.test_guards` (tabela allow/deny każdego Guarda)
i `bash tests/test_guard_adapter.sh` (tłumaczenie kontraktu) — odpalane też przez CI
(`tests/test_shell_suites.py` wciąga suity powłoki do `unittest discover`).

## Code review (Bugbot + GitHub)

Moduł MCP: `core:code-review` (bundle `devops` lub `architecture`).

**Minimalny zestaw przed pushem** (nie odpalaj całego wachlarza):

| Zmiana | Minimum |
|--------|---------|
| Drobna | `/review-bugbot` |
| Backend / Frontend | Bugbot + `/review-backend` lub `/review-frontend` |
| API + UI | Bugbot + BE+FE **lub** para `/subagent-*` |
| Auth / płatności | `/review-security` |
| Dowód „działa” | `/review-tests` (komendy, nie styl) |

Bugbot = blocking/security. Stack `/review-*` = konwencje z MCP (`Severity | Location | Finding | Fix`).  
Przy `codegen: orval` w overlay — po zmianie API regeneruj klienta.


| Warstwa            | Plik / akcja                                                                |
| ------------------ | --------------------------------------------------------------------------- |
| Lokalnie           | `/review-bugbot`, `/review-security`, `/review-backend`…                    |
| Przed push         | `git-guard.mjs` (deny na main/master/dev) — review przypomina `/git-end`     |
| Na PR              | Bugbot (GitHub integration)                                                 |
| Reguły             | `.cursor/BUGBOT.md`                                                         |
| CI (ten kit)       | `.github/workflows/ci.yml` — unittest (w tym suity powłoki) + smoke FastMCP |
| Hook regresja      | `tests/test_gate_destructive.sh` (polityka) + `tests/test_guard_adapter.sh` |
| Suity powłoki w CI | `tests/test_shell_suites.py` — jedyny adapter `*.sh` → `unittest discover`  |



## Zależności Python (pin majora)

```toml
mcp>=1.0.0,<2      # FastMCP (1.x); mcp 2.0 usuwa mcp.server.fastmcp
pyyaml>=6.0,<7
```

`uvx` resolvuje zależności od zera (nie bierze lokalnego `uv.lock`) — upper bound chroni konsumentów przed breaking major.

## Skills / pluginy zewnętrzne (poza tym kitem)

Trzy warstwy — nie bundluj Matt/Superpowers w `guides-mcp`:


| Warstwa   | Przykłady                                                 | Gdzie                                     | Rola                         |
| --------- | --------------------------------------------------------- | ----------------------------------------- | ---------------------------- |
| Fundament | Context7, `project-guides`, `/review-*`, `/git-*`, Cursor `/compact` | MCP + agents/skills z bootstrap | stack, git, skrót czatu (Cursor) |
| Proces    | [mattpocock/skills](https://github.com/mattpocock/skills) | `npx skills@latest add mattpocock/skills` | `/grill-me`, `/tdd`          |
| Meta      | superpowers, caveman, Autopilot                                      | user / plugin Cursor                      | worktree, finishing, CI loop |


Priorytet w `AGENTS.md`: użytkownik → overlay+MCP → review kita → Matt → Superpowers.  
TDD: jeden path na feature (preferuj Matt). Setup Matt: po instalacji uruchom `/setup-matt-pocock-skills`.

Context7 (docs Django/Expo): globalnie `npx ctx7 setup --cursor`.

## Subagenty — szczegóły

Każdy plik agentów jest **cienkim wrapperem**: przy starcie woła `get_bundle` / `get_overlay` z MCP `project-guides`. Wiedza merytoryczna żyje w `modules/`.

Praca w dwóch oknach: `/subagent-backend` ↔ `/subagent-frontend` — sekcja „Raport do przekazania” na końcu odpowiedzi.