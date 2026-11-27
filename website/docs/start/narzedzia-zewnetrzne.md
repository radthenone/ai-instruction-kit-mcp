# Narzędzia zewnętrzne

Kit nie bundluje cudzych pluginów. Każdy instalujesz osobno, w swoim kliencie. Źródła ułożone są w cztery warstwy (kolejność priorytetów jest w `AGENTS.md`):

| Warstwa | Przykłady | Rola |
|---|---|---|
| Fundament | `kit-ai-mcp`, `/kit-ai:review-*`, `/kit-ai:git-*` | stack, git, review. Instaluje bootstrap |
| Proces | mattpocock/skills (`/grill-me`, `/tdd`) | jak budować feature |
| Meta | Superpowers (worktree, finishing, debug) | sesja, izolacja, finisz |
| PR → green | Autopilot | dociąganie PR po CI |

Nie mieszaj warstw: kit jest prawdą o stacku i nazwach branchy, Matt o procesie feature, Superpowers o sesji i worktree, a Autopilot o dociąganiu PR.

## Superpowers

- **Claude Code**: `/plugin marketplace add obra/superpowers-marketplace`, potem `/plugin install superpowers@superpowers-marketplace`.
- **Codex**: w TUI wpisz `/plugins`, wybierz `superpowers` i *Install Plugin*.
- **Antigravity**: `agy plugin install https://github.com/obra/superpowers`.

## Skille Matta Pococka (`/grill-me`, `/tdd`)

- **Claude Code**: `/plugin install mattpocock-skills`.
- **Codex, OpenCode, VS Code**: `npx skills@latest add mattpocock/skills -a <id>`.
- **Antigravity per projekt**: `npx skills@latest add mattpocock/skills -a antigravity -s '*' -y`.

W repo z kitem setup Matta nie jest potrzebny. `kit-ai reload` tworzy jego brakujące pliki w `docs/agents/` i w `AGENTS.md`.

## Caveman i Ponytail

- **Caveman** (Claude Code): `claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman`.
- **Ponytail** (Claude Code): `/plugin marketplace add DietrichGebert/ponytail`, a potem osobną wiadomością `/plugin install ponytail@ponytail`.

!!! note "Ponytail a procedury kita"
    Ponytail, nastawiony na „najkrótszą drogę”, omijałby procedury kita (np. `grep` zamiast `get_bundle`). Dlatego `kit-ai reload` wpisuje do `.claude/settings.local.json` zmienną `PONYTAIL_SUBAGENT_MATCHER`. Wyłącza ona ponytaila dla agentów procedur: `git-*`, `review-*`, `night-run*`, `create-*`, `kit-project-*`, `teacher-*`, `headless`, `cleanup`. Działa tylko w Claude Code. Własną wartość wpisz w `env` tego pliku, a kit jej nie nadpisze.

## Context7 (dokumentacja bibliotek)

Najprościej: `npx ctx7 setup --claude` (albo `--opencode`). Ręcznie to zdalny serwer `https://mcp.context7.com/mcp` z nagłówkiem `Authorization: Bearer <KLUCZ>`.

## CodeGraph (graf kodu)

```bash title="Git Bash · bash"
npm i -g @colbymchenry/codegraph
codegraph install --target claude,codex,opencode,copilot-vscode,antigravity --location global
codegraph init -i        # w każdym repo: buduje indeks .codegraph/
```

W `--target` zostaw tylko swoich klientów.

## GitHub MCP (issues i PR z agenta)

Serwer zdalny `https://api.githubcopilot.com/mcp/`. Poza VS Code potrzebny jest PAT w zmiennej środowiskowej, nigdy w pliku w repo:

```bash title="Git Bash · bash"
export GITHUB_PAT_TOKEN=…        # PowerShell: $env:GITHUB_PAT_TOKEN = "…"
```

Klient musi wystartować z już ustawioną zmienną.

## `.agents/skills/`

Skille z `npx skills` dla Codexa, OpenCode, Copilota i Antigravity trafiają do `.agents/skills/`. Kit ignoruje ten katalog w `.gitignore`, więc na nowej maszynie instalację powtarzasz.

!!! warning "Antigravity CLI"
    `agy` czyta globalnie tylko `~/.gemini/config/skills/`, a `npx skills -g` kładzie skille w `~/.agents/skills/`. Po aktualizacji skopiuj skille ponownie.

## Rtk

Rtk przepisuje komendy na `rtk …` i oszczędza tokeny. Brak rtk niczego nie psuje.

- Instalacja: `winget install rtk-ai.rtk` (Windows) albo skrypt z GitHuba (Linux, macOS).
- Hook na klienta: `rtk init -g --auto-patch` (Claude Code), `rtk init -g --codex` (Codex), `rtk init -g --opencode` (OpenCode), `rtk init -g --agent antigravity` (Antigravity).
- Copilot dostaje hook z kita (`.github/hooks/rtk-rewrite.json`). Nie uruchamiaj `rtk init --copilot`, bo nadpisze `.github/copilot-instructions.md`.

!!! warning "Kolizja nazw"
    Jeśli `rtk --version` działa, a `rtk gain` nie, masz inne narzędzie o tej nazwie (`reachingforthejack/rtk`), a nie Rust Token Killer.
