#!/usr/bin/env bash
# Regression: gate-destructive must deny force via +ref on protected branches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/templates/cursor/hooks/gate-destructive.sh"

json_cmd() {
  # Minimal JSON string escape for test commands (no quotes/backslashes in fixtures).
  printf '{"command":"%s"}' "$1"
}

run_hook() {
  local cmd="$1"
  local expect="$2"
  local out perm
  out=$(json_cmd "$cmd" | bash "$HOOK")
  perm=$(printf '%s' "$out" | sed -n 's/.*"permission": "\([^"]*\)".*/\1/p')
  if [[ "$perm" != "$expect" ]]; then
    echo "FAIL expected=$expect got=${perm:-empty} cmd=$cmd out=$out" >&2
    return 1
  fi
  echo "OK  [$expect] $cmd"
}

run_hook "git push origin +main" deny
run_hook "git push origin +master" deny
run_hook "git push origin +dev" deny
run_hook "git push origin +main:main" deny
run_hook "git push --force origin main" deny
run_hook "git push -f origin master" deny
run_hook "git push origin +feat/foo" ask
run_hook "git push --force origin feat/x" ask
run_hook "git push origin main" ask
run_hook "git push origin feat/x" allow
run_hook "git status" allow

echo "All gate-destructive +ref checks passed."
