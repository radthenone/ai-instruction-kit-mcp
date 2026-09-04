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
# Ten przebieg leci z --skip-agents, więc jest zarazem dowodem, że flaga pomija skille.
test ! -e "$TMP/only-cursor/.cursor/skills/skill-authoring"
grep -q '"--clients", "cursor"' "$TMP/only-cursor/.cursor/mcp.json"
# Guardraile ida ze wspolnego zrodla (templates/shared/guards).
test -f "$TMP/only-cursor/.cursor/hooks/gate-destructive.sh"
test -f "$TMP/only-cursor/.cursor/hooks/gate-push.sh"
test -f "$TMP/only-cursor/.cursor/hooks/invoke-hook.js"
grep -q -- '--to cursor' "$TMP/only-cursor/.cursor/hooks.json"
# Cursor ma tylko afterFileEdit (po zapisie), wiec bramki na pliki nie dostaje.
test ! -e "$TMP/only-cursor/.cursor/hooks/gate-file-writes.mjs"
test ! -e "$TMP/only-cursor/.claude/hooks"
echo "OK  --clients cursor (+ guardraile)"

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

"$BOOT" "$TMP/codex" --clients codex --from "$ROOT" >/dev/null
test -f "$TMP/codex/.codex/config.toml"
# Codex nie ma custom prompts (.codex/agents) — agenty i skille lądują w .codex/skills.
test -f "$TMP/codex/.codex/skills/git-start/SKILL.md"
test -f "$TMP/codex/.codex/skills/create-task/SKILL.md"
test -f "$TMP/codex/.codex/skills/skill-authoring/SKILL.md"
test ! -e "$TMP/codex/.codex/agents"
echo "OK  --clients codex (+ agenty jako skille)"

"$BOOT" "$TMP/claude-kiro" --clients claude,kiro --from "$ROOT" >/dev/null
test -f "$TMP/claude-kiro/.mcp.json"
test -d "$TMP/claude-kiro/.claude/agents"
test -f "$TMP/claude-kiro/.claude/commands/cleanup.md"
test -d "$TMP/claude-kiro/.kiro/agents"
test ! -e "$TMP/claude-kiro/.cursor/mcp.json"
# Claude dostaje te same guardraile co Cursor plus bramke na zapisy plikow.
test -f "$TMP/claude-kiro/.claude/hooks/gate-destructive.sh"
test -f "$TMP/claude-kiro/.claude/hooks/gate-push.sh"
test -f "$TMP/claude-kiro/.claude/hooks/invoke-hook.js"
test -f "$TMP/claude-kiro/.claude/hooks/gate-file-writes.mjs"
grep -q 'PreToolUse' "$TMP/claude-kiro/.claude/settings.json"
grep -q 'gate-file-writes.mjs' "$TMP/claude-kiro/.claude/settings.json"
# Claude nie tlumaczy kontraktu — dialekt polityki jest jego wlasnym.
if grep -q -- '--to cursor' "$TMP/claude-kiro/.claude/settings.json"; then
  echo "FAIL .claude/settings.json nie powinien tlumaczyc na kontrakt Cursora" >&2
  exit 1
fi
echo "OK  --clients claude,kiro (+ agents, guardraile)"

# Ta sama polityka u obu klientow: pliki musza byc identyczne ze zrodlem.
"$BOOT" "$TMP/both" --clients cursor,claude --from "$ROOT" --skip-agents >/dev/null
cmp -s "$ROOT/templates/shared/guards/gate-destructive.sh" "$TMP/both/.cursor/hooks/gate-destructive.sh"
cmp -s "$ROOT/templates/shared/guards/gate-destructive.sh" "$TMP/both/.claude/hooks/gate-destructive.sh"
cmp -s "$TMP/both/.cursor/hooks/invoke-hook.js" "$TMP/both/.claude/hooks/invoke-hook.js"
echo "OK  --clients cursor,claude (jedno zrodlo polityki)"

# Odznaczenie klienta sprzata jego hooki i wpisy w settings.json.
"$BOOT" "$TMP/both" --clients cursor --from "$ROOT" --skip-agents >/dev/null
test ! -e "$TMP/both/.claude/hooks"
test ! -e "$TMP/both/.claude/settings.json"
test -f "$TMP/both/.cursor/hooks/gate-destructive.sh"
echo "OK  prune: claude odznaczony sprzata po sobie"

"$BOOT" "$TMP/skills" --clients all --from "$ROOT" >/dev/null
# Cztery klienty czytają skille natywnie — katalog skilla z zasobami, nie jeden plik.
test -f "$TMP/skills/.claude/skills/skill-authoring/SKILL.md"
test -f "$TMP/skills/.cursor/skills/skill-authoring/SKILL.md"
test -f "$TMP/skills/.agents/skills/skill-authoring/SKILL.md"
# Cursorowy skill spoza shared zostaje na miejscu obok kitowych.
test -f "$TMP/skills/.cursor/skills/compact/SKILL.md"
# Codex czyta skille natywnie jak claude/cursor — katalog z zasobami.
test -f "$TMP/skills/.codex/skills/skill-authoring/SKILL.md"
# Reszta dostaje ten sam skill jako komendę w swoim formacie.
test -f "$TMP/skills/.github/prompts/skill-authoring.prompt.md"
test -f "$TMP/skills/.kiro/agents/skill-authoring.md"
test -f "$TMP/skills/.kilocode/workflows/skill-authoring.md"
test -f "$TMP/skills/.opencode/command/skill-authoring.md"
echo "OK  shared skills u wszystkich klientów (4 natywnie, 4 przez degradację)"

# .agents/skills i .claude/skills dzielimy ze skillami spoza kita — prune musi
# kasować po nazwach ze źródła, nie całym katalogiem.
mkdir -p "$TMP/skills/.agents/skills/obcy-skill"
echo "nie moj" > "$TMP/skills/.agents/skills/obcy-skill/SKILL.md"
"$BOOT" "$TMP/skills" --clients claude --from "$ROOT" >/dev/null
test -f "$TMP/skills/.agents/skills/obcy-skill/SKILL.md"
test ! -e "$TMP/skills/.agents/skills/skill-authoring"
test -f "$TMP/skills/.claude/skills/skill-authoring/SKILL.md"
# Cursor odznaczony w tym samym przebiegu — jego skille znikają razem z resztą.
test ! -e "$TMP/skills/.cursor/skills"
echo "OK  prune kasuje kitowe skille, zostawia cudze"

echo "All bootstrap --clients checks passed."
