#!/usr/bin/env bash
# Cursor hook: przypomnienie o /review-bugbot przed git push.
# Wejście: JSON na stdin (beforeShellExecution).
# Wyjście: JSON z permission allow|ask|deny.

set -euo pipefail

input=$(cat)

extract_command() {
  if command -v jq >/dev/null 2>&1; then
    echo "$input" | jq -r '.command // empty'
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "$input" | python3 -c "import sys, json; print(json.load(sys.stdin).get('command', '') or '')"
    return
  fi
  echo ""
}

command=$(extract_command)

allow() {
  echo '{ "permission": "allow" }'
  exit 0
}

ask_review() {
  local reason="$1"
  cat <<EOF
{
  "permission": "ask",
  "user_message": "Przed pushem uruchom /review-bugbot w Cursor (lub /review-security przy auth/płatnościach). Bypass: SKIP_PUSH_REVIEW=1 git push",
  "agent_message": "Hook gate-push: ${reason}. Zaproponuj użytkownikowi /review-bugbot na branch changes przed git push."
}
EOF
  exit 0
}

# Nie dotyczy pusha — przepuść.
if [[ -z "$command" ]] || [[ ! "$command" =~ (^|[[:space:]])git[[:space:]]+push ]]; then
  allow
fi

# Jawny bypass (awaryjny push).
if [[ -n "${SKIP_PUSH_REVIEW:-}" ]]; then
  allow
fi

# Brak repo git — nie blokuj.
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  allow
fi

# Brak niepushniętych commitów — nic do review.
if ! git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
  # Brak upstream — pierwszy push; warto review.
  ask_review "pierwszy push brancha (brak upstream)"
fi

local_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
remote_sha=$(git rev-parse @{u} 2>/dev/null || echo "")

if [[ -n "$local_sha" && -n "$remote_sha" && "$local_sha" == "$remote_sha" ]]; then
  allow
fi

# Są commity do wypchnięcia.
ask_review "niepushnięte commity na bieżącym branchu"
allow
