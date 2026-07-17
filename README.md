# Instruction Kit — MCP z instrukcjami projektów

Centralne repo MD + serwer MCP. Projekty wybierają moduły przez `.ai/project.profile.yaml`.

## Uruchomienie (uvx — bez lokalnego klona)

```json
{
  "mcpServers": {
    "project-guides": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git",
        "guides-mcp",
        "--profile", "${workspaceFolder}/.ai/project.profile.yaml"
      ]
    }
  }
}
```

**Wybór modułów** = `.ai/project.profile.yaml` w projekcie (extends `profiles/<nazwa-projektu>.yaml`).

Dev lokalny (przed pushem na GitHub):

```json
"--from", "/absolutna/sciezka/do/ai-instruction-kit-mcp"
```

## MCP w innych klientach (Claude Code, Codex CLI, GitHub Copilot)

Każdy klient ma **własny plik i własny format** rejestracji MCP — nie da się skopiować `.cursor/mcp.json` 1:1.

| Klient | Plik | Klucz top-level | Szablon w tym repo |
|--------|------|------------------|---------------------|
| Cursor | `.cursor/mcp.json` | `mcpServers` | `templates/cursor/mcp.json` |
| Claude Code | `.mcp.json` (root repo aplikacji) | `mcpServers` | `templates/claude/mcp.json` |
| Codex CLI | `.codex/config.toml` | `[mcp_servers.x]` (TOML) | `templates/codex/config.toml` |
| GitHub Copilot (VS Code) | `.vscode/mcp.json` | `servers` (**nie** `mcpServers`) | `templates/vscode/mcp.json` |

Zmienna dla ścieżki `--profile` różni się per klient:

| Klient | Zmienna |
|--------|---------|
| Cursor, VS Code | `${workspaceFolder}` |
| Claude Code | `${CLAUDE_PROJECT_DIR:-.}` |
| Codex CLI | brak stałej zmiennej — użyj ścieżki absolutnej lub `cwd` w `config.toml` (zmienne w `args` bywają niestabilne, zwłaszcza w Codex App) |

Skopiuj odpowiedni szablon do repo aplikacji, podstaw `--from` (git+https jak wyżej, albo lokalna ścieżka na czas developmentu) i właściwą zmienną profilu.

## Katalog modułów

```text
modules/
  core/              repo-first, workflow, typing (TS + Python)
  architecture/      platforms (BE/web/mobile), CI/CD, API contract, UI/UX
  stacks/
    django-drf/
    expo-router/     structure, mobile-native, web-target
  capabilities/      auth, files, payments, payments-expo-stripe
  domains/           shop
  patterns/          capability-provider, providers-and-settings, gateway…
  infra/             database, cache, queue, storage, tasks
profiles/
  _base.yaml         wspólny preset (extends w profilach projektów)
  *.yaml             presety projektów (np. e-commerce)
```

## Sloty infrastruktury (`decisions`)

```yaml
decisions:
  database: postgres      # → infra:database:postgres
  cache: redis            # → infra:cache:redis
  queue: redis            # → infra:queue:redis  (lub rabbitmq)
  storage: s3             # → infra:storage:s3
  tasks: celery           # → infra:tasks:celery
```

Moduły infra trafiają automatycznie do bundle `infra` i `devops`.

## Bundle'e MCP

| Bundle | Zastosowanie |
|--------|--------------|
| `backend` | Django, DRF, capabilities BE |
| `frontend` | Expo, UI/UX |
| `shop` | products, orders, cart |
| `payments` | Stripe, webhooks |
| `architecture` | monorepo, kontrakt API, capability-provider |
| `infra` | postgres, redis, queue, s3, celery |
| `devops` | CI/CD + infra |
| `full` | wszystko + infra |

## Bootstrap w projekcie docelowym

W **repo aplikacji** (nie w instruction-kit) skopiuj z `templates/`:

| Plik | Rola |
|------|------|
| `.ai/project.profile.yaml` | `extends: profiles/<preset>.yaml` z tego kita |
| `.ai/project.md` | Overlay — Taskfile, Docker, porty |
| `.cursor/mcp.json` | uvx → instruction-kit |
| `.cursor/rules/use-guides.mdc` | Bootstrap MCP |
| `.cursor/rules/code-review.mdc` | Przypomnienie o review przed pushem |
| `.cursor/BUGBOT.md` | Reguły Bugbota (z `templates/cursor/BUGBOT.md`, dostosuj) |
| `.cursor/hooks.json` + `.cursor/hooks/gate-push.sh` | Przypomnienie przy `git push` |
| `AGENTS.md` | Cienki — odsyła do MCP i overlay |
| `.cursor/agents/*.md` (+ opcjonalnie `.claude/agents/*.md`) | Opcjonalnie — subagenty review, patrz sekcja niżej |

Opcjonalnie: `.git/hooks/pre-push` z `templates/git-hooks/pre-push`.

W projekcie docelowym **nie** duplikuj modułów z `modules/` — wystarczy profil + overlay + `.cursor/`.

## Code review (Bugbot + GitHub)

Moduł MCP: `core:code-review` (bundle `devops` lub `architecture`).

| Warstwa | Plik / akcja |
|---------|----------------|
| Lokalnie | `/review-bugbot`, `/review-security` w Cursor |
| Przed push | `.cursor/hooks/gate-push.sh` |
| Na PR | Bugbot (GitHub integration) |
| Reguły | `.cursor/BUGBOT.md` |
| CI | `arch:ci-cd` — testy + typy + opcjonalnie check Bugbota |

Szablony: `templates/cursor/`, `templates/git-hooks/`.

## Subagenty review (Cursor / Claude Code / Codex)

### Co to jest

Subagent to wyspecjalizowana „rola" AI z własnym, izolowanym kontekstem — wywołujesz ją na żądanie (`/nazwa`), ona robi swoje zadanie (np. review diffu), i zwraca **jeden** raport do Twojej głównej rozmowy. Nie zaśmieca Twojego kontekstu swoim procesem myślenia — widzisz tylko wynik.

To nie jest kolejny system promptów wklejanych ręcznie do czatu — to pliki `.md` (Cursor/Claude Code) lub `.toml` (Codex), które narzędzie **automatycznie wykrywa** po umieszczeniu w odpowiednim katalogu projektu.

### Do czego to służy

Każdy plik = jedna wyspecjalizowana rola reviewera, dopasowana do warstwy stacku (Django/DRF, Expo/React), zamiast jednego ogólnego review wszystkiego naraz:

| Rola | Plik | Kiedy używać |
|------|------|--------------|
| Architektura, kontrakt API | `architecture-reviewer.md` | zmiana dotyka monorepo, API, capability-provider |
| Backend Django/DRF | `backend-reviewer.md` | zmiany w `backend/`, serializery, ACL, Celery |
| Frontend Expo/React | `frontend-reviewer.md` | zmiany w `frontend/`, klient Orval, TypeScript |
| UI/UX | `ui-ux-reviewer.md` | zmiany ekranów, formularzy, flow użytkownika |
| Weryfikacja „zrobione" | `test-verifier.md` | po oznaczeniu zadania jako ukończone — sceptycznie sprawdza dowody |
| Edge case'y, regresje | `edge-case-reviewer.md` | większe zmiany — szuka przypadków brzegowych |
| Backend, praca w 2 okienkach | `backend-sub.md` | jak `backend-reviewer`, ale wymienia raporty z `frontend-sub` w drugim oknie (patrz niżej) |
| Frontend, praca w 2 okienkach | `frontend-sub.md` | jak `frontend-reviewer`, ale wymienia raporty z `backend-sub` w drugim oknie (patrz niżej) |

Każdy plik jest **cienkim wrapperem**: nie zawiera na sztywno reguł Django/Expo, tylko przy starcie sam woła `get_bundle` / `get_overlay` z MCP `project-guides` (ten sam serwer, który już skonfigurowałeś w sekcji „Uruchomienie" wyżej) i lokalne pliki repo (`.cursor/BUGBOT.md`, `.ai/project.md`). Dzięki temu jeden plik działa identycznie w każdym projekcie korzystającym z tego kita — wiedza merytoryczna żyje w `modules/`, nie w pliku subagenta.

### Jak skopiować do swojego projektu

To są **szablony** — nie działają, dopóki nie znajdą się w repo aplikacji (nie w instruction-kit).

1. Skopiuj cały katalog `templates/claude/agents/` do `<twój-projekt>/.cursor/agents/` (Cursor czyta tę lokalizację jako główną; obsługuje też `.claude/agents/`, jeśli używasz też Claude Code — możesz skopiować do obu, treść jest identyczna).
2. Upewnij się, że w `<twój-projekt>/.cursor/mcp.json` masz zarejestrowany serwer `project-guides` (patrz „Uruchomienie" i „MCP w innych klientach" wyżej) — subagenty wywołują go wewnętrznie, więc musi tam być.
3. **Zrestartuj okno/workspace** narzędzia (Cursor/Claude Code) w tamtym projekcie — subagenty są wykrywane przy starcie, nie w locie.
4. Dla Codex CLI: skopiuj `templates/codex/agents/*.toml` do `<twój-projekt>/.codex/agents/` (na razie przykład dla `backend-reviewer` i `frontend-reviewer` — reszta ról wg tego samego wzorca, patrz plik TOML).

### Jak wywołać

W czacie wpisz `/` + nazwę subagenta, opcjonalnie z opisem zadania:

```text
/backend-reviewer przejrzyj zmiany w backend/apps/products/
```

```text
/frontend-reviewer sprawdź czy klient Orval jest aktualny po zmianie API
```

Po samym `/` Cursor podpowiada listę zamontowanych subagentów. Jeśli lista jest pusta lub brakuje na niej pliku, który właśnie skopiowałeś — zrestartuj okno (subagenty wczytują się przy starcie, nie w locie).

### Łączenie kilku subagentów w jednej rozmowie

Do jednego głównego czatu (jedno okno) możesz wywołać kilku reviewerów po sobie — główny agent w tym oknie widzi raporty obu i sam je łączy:

```text
1. Uruchom /backend-reviewer na diffie.
2. Na podstawie jego raportu uruchom /frontend-reviewer,
   przekazując mu istotne znaleziska backend-reviewera jako kontekst.
3. Zsyntetyzuj oba raporty w jedną tabelę.
```

Wpisujesz to jako jedną wiadomość do głównego agenta — on decyduje, co i kiedy przekazać dalej między subagentami.

### Subagenty do pracy w dwóch okienkach (`backend-sub` / `frontend-sub`)

To wariant dla innego stylu pracy: dwa **osobne** okna Cursor (np. jedno z kontekstem backendu, drugie frontendu), między którymi sam ręcznie przenosisz raport (kopiuj-wklej). Pliki: `backend-sub.md` i `frontend-sub.md` w `templates/claude/agents/` — montujesz je tak samo jak resztę (krok „Jak skopiować" wyżej, ten sam katalog `.cursor/agents/`).

Różnica względem `-reviewer`: `-sub` rozpoznaje wklejony raport z drugiego okienka i sprawdza względem niego kod w swojej warstwie, a swoją odpowiedź zawsze kończy sekcją „Raport do przekazania" gotową do skopiowania.

Użycie:

1. **Okno 1 (backend):** `/backend-sub przejrzyj zmiany w backend/apps/products/` → na końcu odpowiedzi dostajesz sekcję „Raport do przekazania dla frontend-sub".
2. Kopiujesz tę sekcję.
3. **Okno 2 (frontend):** `/frontend-sub` + wklejasz skopiowaną sekcję → frontend-sub sprawdza, czy frontend faktycznie konsumuje to, co zmienił backend, i na końcu zwraca własną sekcję „Raport do przekazania dla backend-sub".
4. W razie potrzeby wracasz do okna 1, wklejasz tę sekcję i backend-sub weryfikuje odpowiedź frontendu.

Na razie dostępne tylko dla Cursor/Claude Code (`.md`). Dla Codex CLI można dodać analogiczne pliki w `templates/codex/agents/*.toml` wg tego samego wzorca, jeśli będzie taka potrzeba.

## Context7

Docs Django/Expo/Stripe — globalnie `npx ctx7 setup --cursor`, osobno od instruction-kit.
