#!/usr/bin/env bash
# Smoke: bootstrap --clients cursor vs all tworzy oczekiwane ścieżki.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BOOT="$ROOT/scripts/bootstrap-project.sh"

"$BOOT" "$TMP/only-cursor" --clients cursor --from "$ROOT" --skip-agents >/dev/null
test -f "$TMP/only-cursor/.cursor/mcp.json"
test -f "$TMP/only-cursor/AGENTS.md"
test ! -e "$TMP/only-cursor/.mcp.json"
test ! -e "$TMP/only-cursor/.kiro"
grep -q '"--clients", "cursor"' "$TMP/only-cursor/.cursor/mcp.json"
echo "OK  --clients cursor"

"$BOOT" "$TMP/all" --clients all --from "$ROOT" --skip-agents >/dev/null
test -f "$TMP/all/.cursor/mcp.json"
test -f "$TMP/all/.mcp.json"
test -f "$TMP/all/.codex/config.toml"
test -f "$TMP/all/.vscode/mcp.json"
test -f "$TMP/all/.kiro/settings/mcp.json"
test -f "$TMP/all/.kilocode/mcp.json"
test -f "$TMP/all/.agents/mcp_config.json"
test -f "$TMP/all/opencode.json"
grep -q '"--clients", "all"' "$TMP/all/.cursor/mcp.json"
echo "OK  --clients all"

"$BOOT" "$TMP/opencode" --clients opencode --from "$ROOT" >/dev/null
test -f "$TMP/opencode/opencode.json"
test -f "$TMP/opencode/.opencode/command/cleanup.md"
grep -q '"--clients", "opencode"' "$TMP/opencode/opencode.json"
echo "OK  --clients opencode (+ rendered commands)"

"$BOOT" "$TMP/claude-kiro" --clients claude,kiro --from "$ROOT" >/dev/null
test -f "$TMP/claude-kiro/.mcp.json"
test -d "$TMP/claude-kiro/.claude/agents"
test -f "$TMP/claude-kiro/.claude/commands/cleanup.md"
test -d "$TMP/claude-kiro/.kiro/agents"
test ! -e "$TMP/claude-kiro/.cursor/mcp.json"
echo "OK  --clients claude,kiro (+ agents)"

echo "All bootstrap --clients checks passed."
