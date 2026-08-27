#!/usr/bin/env bash
# Wspolny guardrail: przypomnienie o /review-bugbot przed git push.
# Jedno zrodlo polityki dla wszystkich klientow (templates/shared/guards/).
#
# Dialekt jak w gate-destructive.sh — kontrakt hooka Claude Code. Tlumaczenie na
# ksztalt Cursora robi invoke-hook.js --to cursor.
#
# Windows: NIE podawaj samej sciezki .sh w konfiguracji hooka — zawsze invoke-hook.js.
set -euo pipefail

input=$(cat)

extract_command() {
  # Patrz gate-destructive.sh: adapter podaje gotowa komende w GUARD_COMMAND.
  if [[ -n "${GUARD_COMMAND+set}" ]]; then
    printf '%s' "$GUARD_COMMAND"
    return
  fi
  if command -v jq >/dev/null 2>&1; then
    echo "$input" | jq -r '.command // .tool_input.command // empty'
    return
  fi
  if command -v node >/dev/null 2>&1; then
    COMMAND_JSON="$input" node -e 'const d=JSON.parse(process.env.COMMAND_JSON||"{}");process.stdout.write(d.command||(d.tool_input||{}).command||"")' 2>/dev/null && return
  fi
  local py
  for py in python python3; do
    if command -v "$py" >/dev/null 2>&1; then
      # Jedna linia: shim `python` z pyenv-win rozbija wieloliniowy argument -c.
      COMMAND_JSON="$input" "$py" -c 'import json,os; d=json.loads(os.environ.get("COMMAND_JSON") or "{}"); print(d.get("command") or (d.get("tool_input") or {}).get("command") or "")' 2>/dev/null && return
    fi
  done
  echo ""
}

command=$(extract_command)

emit() {
  # $1 = decyzja, $2 = powod dla agenta
  printf '%s\n' "{ \"hookSpecificOutput\": { \"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"$1\", \"permissionDecisionReason\": \"$2\" } }"
}

allow() {
  emit allow "brak niepushnietych zmian do review"
  exit 0
}

ask_review() {
  local reason="$1"
  emit ask "${reason}. Przed pushem uruchom /review-bugbot (lub /review-security przy auth/platnosciach). Bypass: SKIP_PUSH_REVIEW=1 git push"
  exit 0
}

if [[ -z "$command" ]] || [[ ! "$command" =~ (^|[[:space:]])git[[:space:]]+push ]]; then
  allow
fi

if [[ -n "${SKIP_PUSH_REVIEW:-}" ]]; then
  allow
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  allow
fi

if ! git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
  ask_review "pierwszy push brancha (brak upstream)"
fi

local_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
remote_sha=$(git rev-parse @{u} 2>/dev/null || echo "")

if [[ -n "$local_sha" && -n "$remote_sha" && "$local_sha" == "$remote_sha" ]]; then
  allow
fi

ask_review "niepushnięte commity na bieżącym branchu"
