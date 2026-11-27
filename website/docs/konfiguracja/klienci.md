# Klienci AI

**Client** to narzędzie AI, które korzysta z kita. Klient decyduje tylko o tym, **gdzie** bootstrap zapisuje pliki i w jakim formacie. Treść instrukcji jest identyczna dla każdego klienta.

## Lista klientów

| Klient | Id w `--clients` | Plik MCP w projekcie | Klucz | Szablon |
|---|---|---|---|---|
| Cursor | `cursor` | `.cursor/mcp.json` | `mcpServers` | `templates/cursor/mcp.json` |
| Claude Code | `claude` | `.mcp.json` (root) | `mcpServers` | `templates/claude/mcp.json` |
| Codex CLI | `codex` | `.codex/config.toml` | `[mcp_servers.x]` (TOML) | `templates/codex/config.toml` |
| GitHub Copilot (VS Code) | `vscode` (alias `copilot`) | `.vscode/mcp.json` | `servers` | `templates/vscode/mcp.json` |
| Kiro | `kiro` | `.kiro/settings/mcp.json` | `mcpServers` | `templates/kiro/settings/mcp.json` |
| Kilo Code | `kilo` | `.kilocode/mcp.json` | `mcpServers` | `templates/kilo/mcp.json` |
| Antigravity | `antigravity` | `.agents/mcp_config.json` | `mcpServers` | `templates/antigravity/mcp_config.json` |
| opencode | `opencode` | `opencode.json` (root) | `mcp` (`type: "local"`) | `templates/opencode/opencode.json` |

Wiele klientów naraz: `--clients cursor,claude` albo `--clients all`.

## Zmienna `--workspace` per klient

| Klient | Zmienna |
|---|---|
| Cursor, VS Code, Kiro, Kilo, Antigravity | `${workspaceFolder}` |
| Claude Code | `${CLAUDE_PROJECT_DIR:-.}` |
| Codex CLI, opencode | ścieżka absolutna, bo nie ma stabilnej zmiennej |

## Co zapisuje każdy klient

- **Claude Code**: plugin `kit-ai` w `.claude/skills/kit-ai/` z komendami `/kit-ai:<nazwa>`, subagenty w `.claude/agents/*.md`, hooki guardów.
- **Codex**: skille w `.codex/skills/<nazwa>/`, hooki w `.codex/hooks/`, `.codex/hooks.json`.
- **Cursor**: agenty w `.cursor/agents/`, reguły w `.cursor/rules/`, `.cursor/BUGBOT.md`, skill `/compact`, hooki.
- **VS Code (Copilot)**: prompty `.github/prompts/*.prompt.md` (wywołanie `/nazwa`), `.github/copilot-instructions.md`, hooki w `.github/hooks/`.
- **Kiro**: `.kiro/steering/instruction-kit.md`, agenty w `.kiro/agents/`.
- **Kilo**: workflow w `.kilocode/workflows/*.md` (wywołanie `/nazwa`).
- **Antigravity**: skille w `.agents/skills/<nazwa>/SKILL.md`, hooki w `.agents/hooks.json`.
- **opencode**: komendy w `.opencode/commands/kit-ai/*.md` (wywołanie `/kit-ai/nazwa`), w tym `/kit-ai/goal` i `/kit-ai/loop`, plugin `.opencode/plugins/kit-guards.js`.

!!! note "Weryfikacja formatów"
    Formaty VS Code, Kilo, Antigravity i opencode oparte są na dokumentacji z sierpnia 2026. Nie były testowane na żywych instalacjach. Kiro, format agentów kopiowany 1:1, również nie jest zweryfikowany. Jeśli `/nazwa` nie działa, zgłoś różnicę i popraw `scripts/render_agent_commands.py`.

## Po zmianie klientów

- Declarative sync: bootstrap **usuwa** kitowe pliki klientów spoza `--clients`. Przełączenie z `all` na `claude` posprząta `.cursor/`, `.codex/` i resztę. Flaga `--keep-unselected-clients` wyłącza to sprzątanie.
- Sprzątanie kasuje tylko pliki kita po nazwie. Własne agenty i hooki zostają.
- Po każdym bootstrapie **zrestartuj IDE albo CLI**. MCP i komendy ładują się przy starcie.

## Różnica między klientami w praktyce

Komendy działają tak samo w każdym kliencie, różni się prefiks wywołania. Pełna tabela: [Przegląd komend](../komendy/przeglad.md).
