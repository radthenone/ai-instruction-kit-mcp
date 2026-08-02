#!/usr/bin/env bash
# Cursor hook: blokuj agresywne / destrukcyjne komendy gita i shella.
# Zawsze wypisz JSON (failClosed w hooks.json).

set -u

emit() {
  # $1 = permission, $2 = short reason (opcjonalnie)
  local perm="$1"
  local reason="${2:-}"
  reason=${reason//\\/\\\\}
  reason=${reason//\"/\\\"}
  if [[ "$perm" == "allow" ]]; then
    printf '%s\n' '{ "permission": "allow" }'
  elif [[ "$perm" == "deny" ]]; then
    printf '%s\n' "{ \"permission\": \"deny\", \"user_message\": \"Zablokowano: ${reason}\", \"agent_message\": \"Hook gate-destructive: DENY — ${reason}\" }"
  else
    printf '%s\n' "{ \"permission\": \"ask\", \"user_message\": \"Potwierdź: ${reason}\", \"agent_message\": \"Hook gate-destructive: ASK — ${reason}\" }"
  fi
}

# Przy każdym wyjściu bez wcześniejszego emit — allow (nie wywołuj exit w trapie).
_emitted=0
finish_allow() {
  if [[ "${_emitted}" -eq 0 ]]; then
    emit allow
    _emitted=1
  fi
}
trap finish_allow EXIT

input=$(cat 2>/dev/null || true)

command=""
if command -v jq >/dev/null 2>&1; then
  command=$(printf '%s' "$input" | jq -r '.command // empty' 2>/dev/null || true)
elif command -v python >/dev/null 2>&1; then
  command=$(COMMAND_JSON="$input" python -c 'import json,os; print(json.loads(os.environ.get("COMMAND_JSON") or "{}").get("command") or "")' 2>/dev/null || true)
elif command -v python3 >/dev/null 2>&1; then
  command=$(COMMAND_JSON="$input" python3 -c 'import json,os; print(json.loads(os.environ.get("COMMAND_JSON") or "{}").get("command") or "")' 2>/dev/null || true)
fi

if [[ -z "${command}" ]]; then
  _emitted=1
  emit allow
  exit 0
fi

normalized=$(printf '%s' "$command" | tr '\n\r\t' '   ')
# shellcheck disable=SC2001
normalized=$(printf '%s' "$normalized" | sed 's/  */ /g')

has() {
  printf '%s' "$normalized" | grep -Eqi "$1" && return 0
  return 1
}

decide() {
  local perm="$1"
  local reason="$2"
  _emitted=1
  trap - EXIT
  emit "$perm" "$reason"
  exit 0
}

if has '(^|[ ])git[ ]+push[ ].*(--force([ =]|-with-lease)|[[:space:]]-f([[:space:]]|$))'; then
  if has '(^|[ ])(main|master)([ ]|$|:)' || has 'origin[ ]+(main|master)([ ]|$)'; then
    decide deny "git force-push na main/master"
  fi
  decide ask "git force-push na feature branch"
fi

if has '(^|[ ])git[ ]+reset[ ]+--hard'; then
  decide deny "git reset --hard"
fi

if has '(^|[ ])git[ ]+clean[ ].*-[a-zA-Z]*f'; then
  decide deny "git clean -f"
fi

if has '(^|[ ])git[ ]+commit[ ].*--no-verify'; then
  decide ask "git commit --no-verify"
fi

if has '(^|[ ])git[ ]+push[ ].*(main|master)([ ]|$)' && ! has '(--force|-f|--force-with-lease)'; then
  decide ask "git push na main/master (preferuj PR)"
fi

if has '(^|[ ])rm[ ]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)'; then
  if has '(\.\.|/home|/Users|C:\\\\|\$HOME|~/)'; then
    decide deny "rm -rf na szerokiej sciezce"
  fi
  decide ask "rm -rf"
fi

_emitted=1
trap - EXIT
emit allow
exit 0
