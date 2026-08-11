# Multi-client templates Implementation Plan

> **For agentic workers:** implement task-by-task; checkboxes for tracking.

**Goal:** Shared canonical templates + per-client adapters + bootstrap/MCP `--clients`.

**Architecture:** `templates/shared/{agents,rules}` is source of truth; client folders hold MCP/format only; bootstrap copies shared→native paths; MCP stores clients metadata via `get_clients`.

**Tech Stack:** bash bootstrap, Python FastMCP, markdown/TOML/JSON templates.

## Global Constraints

- Default `--clients all`
- Alias `copilot` → `vscode`
- Client ids: cursor, claude, codex, vscode, kiro, kilo, antigravity
- Docstrings PL; code identifiers EN
- Do not invent Anthropic client id

## Tasks

- [x] Move agents → `templates/shared/agents`; rules bodies → `templates/shared/rules`
- [x] Add adapter MCP configs (kiro, kilo, antigravity); trim claude to mcp-only; expand vscode
- [x] Rewrite bootstrap `--clients` + install functions
- [x] MCP `--clients` + `get_clients` + tests
- [x] README + AGENTS notes
