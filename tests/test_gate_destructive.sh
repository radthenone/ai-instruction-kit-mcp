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
# git+https must NOT be treated as force-refspec "+"
run_hook "git push git+https://example.com/repo.git main" ask
run_hook "git push git+https://example.com/repo.git feat/x" allow
# Remote named "dev" is not a protected branch; origin/upstream + branch is.
run_hook "git push dev" allow
run_hook "git push origin feat/x" allow
run_hook "git push origin dev" ask
run_hook "git push upstream dev" ask
run_hook "git push main" ask
run_hook "git push master" ask

# Fail-closed: nieoczekiwany exit != 0 bez wcześniejszego emit → ask + exit 0
# (JSON ask musi wyjść z 0, żeby failClosed w Cursor nie blokował mimo permission).
test_fail_closed_on_unexpected_error() {
  local tmp out perm code
  tmp=$(mktemp)
  awk '
    { print }
    /^trap finish_allow EXIT$/ { print "exit 42" }
  ' "$HOOK" > "$tmp"
  set +e
  out=$(json_cmd "git status" | bash "$tmp")
  code=$?
  set -e
  rm -f "$tmp"
  perm=$(printf '%s' "$out" | sed -n 's/.*"permission": "\([^"]*\)".*/\1/p')
  if [[ "$perm" != "ask" ]]; then
    echo "FAIL fail-closed expected=ask got=${perm:-empty} out=$out" >&2
    return 1
  fi
  if [[ "$code" -ne 0 ]]; then
    echo "FAIL fail-closed expected exit 0 got=$code out=$out" >&2
    return 1
  fi
  echo "OK  [ask/exit0] unexpected hook exit → fail-closed"
}

test_fail_closed_on_unexpected_error

echo "All gate-destructive +ref checks passed."
