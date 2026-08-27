#!/usr/bin/env bash
# Regresja polityki gate-destructive: force-push przez +ref na chronionych galeziach,
# operacje kasujace niezacommitowana prace, rekursywne kasowanie plikow.
#
# Polityka mowi dialektem Claude Code (hookSpecificOutput.permissionDecision).
# Tlumaczenie na kontrakt Cursora sprawdza tests/test_guard_adapter.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/templates/shared/guards/gate-destructive.sh"

json_cmd() {
  # Backslash musi zostac zescapowany, inaczej fixtura ze sciezka Windows
  # (`C:\Users\...`) to niepoprawny JSON i test sprawdza cos innego, niz mysli.
  local escaped=${1//\\/\\\\}
  printf '{"tool_input":{"command":"%s"}}' "$escaped"
}

decision_of() {
  # Wyluskaj permissionDecision z wyjscia polityki.
  sed -n 's/.*"permissionDecision": "\([^"]*\)".*/\1/p'
}

run_hook() {
  local cmd="$1"
  local expect="$2"
  local out perm
  out=$(json_cmd "$cmd" | bash "$HOOK")
  perm=$(printf '%s' "$out" | decision_of)
  if [[ "$perm" != "$expect" ]]; then
    echo "FAIL expected=$expect got=${perm:-empty} cmd=$cmd out=$out" >&2
    return 1
  fi
  echo "OK  [$expect] $cmd"
}

# --- force push / chronione galezie -----------------------------------------
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

# --- kasowanie historii / stanu ---------------------------------------------
run_hook "git reset --hard" deny
run_hook "git clean -fd" deny
run_hook "git commit -m x --no-verify" ask

# --- kasowanie niezacommitowanej pracy --------------------------------------
# Git odzyska tylko to, co zacommitowane — ponizsze niszcza reszte.
run_hook "git checkout -- ." ask
run_hook "git checkout -- src/app.py" ask
run_hook "git restore ." ask
run_hook "git stash" ask
# ...ale odczyt i przywracanie stashu sa bezpieczne
run_hook "git stash list" allow
run_hook "git stash pop" allow
run_hook "git stash show" allow
run_hook "git restore --staged src/app.py" allow
# checkout galezi to nie kasowanie plikow
run_hook "git checkout -b feat/x" allow
run_hook "git checkout master" allow

# --- rekursywne kasowanie plikow --------------------------------------------
run_hook "rm build.log" allow
run_hook "rm -r build/" ask
run_hook "rm -rf node_modules" ask
run_hook "find . -name *.pyc -delete" ask
run_hook "find . -type f -exec rm {} ;" ask

# Szeroka sciezka: katalog domowy POSIX i Windows, katalog nadrzedny.
run_hook "rm -rf /home/user/projects" deny
run_hook "rm -r /Users/someone/work" deny
run_hook "rm -rf ../.." deny
# Regresja: notacja Windows ma pojedyncze backslashe — stary wzorzec `C:\\\\`
# wymagal dwoch i przepuszczal to jako zwykly ask.
run_hook 'rm -rf C:\Users\someone\work' deny
run_hook 'rm -r D:\Windows\System32' deny

# --- fail-closed -------------------------------------------------------------
# Nieoczekiwany exit != 0 bez wczesniejszego emit → ask + exit 0 (zeby failClosed
# w Cursor nie zablokowal mimo poprawnej decyzji).
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
  perm=$(printf '%s' "$out" | decision_of)
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

# Nieczytelny payload to nie to samo co payload bez komendy. Pierwszy znaczy
# "nie wiemy, co bysmy przepuscili" → ask. Drugi to zwykle inne narzedzie → allow.
test_unparseable_payload_is_fail_closed() {
  local out perm
  out=$(printf 'to nie jest json' | bash "$HOOK")
  perm=$(printf '%s' "$out" | decision_of)
  if [[ "$perm" != "ask" ]]; then
    echo "FAIL unparseable payload expected=ask got=${perm:-empty} out=$out" >&2
    return 1
  fi
  echo "OK  [ask] nieczytelny payload → fail-closed"

  out=$(printf '{"tool_input":{"file_path":"src/app.py"}}' | bash "$HOOK")
  perm=$(printf '%s' "$out" | decision_of)
  if [[ "$perm" != "allow" ]]; then
    echo "FAIL payload bez komendy expected=allow got=${perm:-empty} out=$out" >&2
    return 1
  fi
  echo "OK  [allow] payload bez komendy (inne narzedzie)"
}

# Polityka musi rozumiec oba ksztalty wejscia: `.command` (Cursor) i
# `.tool_input.command` (Claude Code).
test_accepts_cursor_shaped_input() {
  local out perm
  out=$(printf '{"command":"git reset --hard"}' | bash "$HOOK")
  perm=$(printf '%s' "$out" | decision_of)
  if [[ "$perm" != "deny" ]]; then
    echo "FAIL cursor-shaped input expected=deny got=${perm:-empty} out=$out" >&2
    return 1
  fi
  echo "OK  [deny] wejscie w ksztalcie Cursora (.command)"
}

test_fail_closed_on_unexpected_error
test_unparseable_payload_is_fail_closed
test_accepts_cursor_shaped_input

echo "All gate-destructive checks passed."
