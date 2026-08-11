# Multi-client templates — design

**Status:** approved (user 2026-08-05)  
**Approach:** thin adapters + `templates/shared/` canon; MCP `--clients` = metadata (option A).

## Goals

- Canonical agent/rule prose lives in `templates/shared/` (not under `claude/`).
- Adapters: `cursor`, `claude`, `codex`, `vscode` (alias `copilot`), `kiro`, `kilo`, `antigravity`.
- Bootstrap `--clients` default `all`; single/list installs only those packs.
- Each generated MCP config includes `"--clients", "<value>"`.
- `guides-mcp` accepts `--clients` / `GUIDES_CLIENTS` and exposes `get_clients`; bundles unchanged.
- Cursor keeps `gate-*` hooks; others get shared git `pre-push` reminder; `/compact` Cursor-only.

## Non-goals

- Runtime adaptation of bundle text per client.
- Anthropic as separate client id (Claude Code = `claude`).
- 1:1 Cursor hook JSON on every IDE.
