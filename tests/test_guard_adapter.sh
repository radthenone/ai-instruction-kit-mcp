#!/usr/bin/env bash
# Regresja adaptera kontraktu (templates/shared/guards/invoke-hook.js).
#
# Skrypty polityki mowia dialektem Claude Code. Adapter jest jedynym miejscem,
# ktore wie, ze Cursor ma wlasny ksztalt wyjscia — te testy pilnuja tlumaczenia
# w obie strony oraz zachowania fail-closed, gdy sam adapter nie ma czego odpalic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARDS="$ROOT/templates/shared/guards"
ADAPTER="$GUARDS/invoke-hook.js"

if ! command -v node >/dev/null 2>&1; then
  if [[ -n "${CI:-}" ]]; then
    echo "FAIL brak node w CI — adapter jest wymagany" >&2
    exit 1
  fi
  echo "SKIP brak node — pomijam testy adaptera" >&2
  exit 0
fi

fail() {
  echo "FAIL $1" >&2
  exit 1
}

# Wytnij wartosc pola JSON. Wystarczy na te fixtury (bez zagniezdzen i escapes).
field() {
  sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p"
}

expect_cursor() {
  local cmd="$1" expect="$2" out perm
  out=$(printf '{"command":"%s"}' "$cmd" | node "$ADAPTER" gate-destructive.sh --to cursor)
  perm=$(printf '%s' "$out" | field permission)
  [[ "$perm" == "$expect" ]] || fail "cursor: expected=$expect got=${perm:-empty} cmd=$cmd out=$out"
  echo "OK  [cursor/$expect] $cmd"
}

expect_claude() {
  local cmd="$1" expect="$2" out perm
  out=$(printf '{"tool_input":{"command":"%s"}}' "$cmd" | node "$ADAPTER" gate-destructive.sh)
  perm=$(printf '%s' "$out" | field permissionDecision)
  [[ "$perm" == "$expect" ]] || fail "claude: expected=$expect got=${perm:-empty} cmd=$cmd out=$out"
  echo "OK  [claude/$expect] $cmd"
}

# --- ta sama polityka, dwa kontrakty ----------------------------------------
for pair in "git status:allow" "git reset --hard:deny" "git stash:ask" "git push origin feat/x:allow"; do
  cmd="${pair%:*}"
  want="${pair##*:}"
  expect_cursor "$cmd" "$want"
  expect_claude "$cmd" "$want"
done

# --- Cursor dostaje komunikaty dla uzytkownika i agenta ---------------------
out=$(printf '{"command":"git reset --hard"}' | node "$ADAPTER" gate-destructive.sh --to cursor)
printf '%s' "$out" | grep -q '"user_message"' || fail "cursor deny bez user_message: $out"
printf '%s' "$out" | grep -q '"agent_message"' || fail "cursor deny bez agent_message: $out"
echo "OK  [cursor] deny niesie user_message + agent_message"

# allow ma zostac minimalne — bez zbednych pol
out=$(printf '{"command":"git status"}' | node "$ADAPTER" gate-destructive.sh --to cursor)
printf '%s' "$out" | grep -q 'user_message' && fail "cursor allow nie powinien niesc user_message: $out"
echo "OK  [cursor] allow jest minimalne"

# --- domyslny format to Claude (bez --to) -----------------------------------
out=$(printf '{"tool_input":{"command":"git status"}}' | node "$ADAPTER" gate-destructive.sh)
printf '%s' "$out" | grep -q 'hookSpecificOutput' || fail "domyslny format nie jest kontraktem Claude: $out"
echo "OK  [claude] domyslny format bez --to"

# --- fail-closed przy awarii adaptera ---------------------------------------
# Brak pliku polityki nie moze skonczyc sie cichym przepuszczeniem komendy.
out=$(printf '{}' | node "$ADAPTER" nie-ma-takiego.sh --to cursor)
perm=$(printf '%s' "$out" | field permission)
[[ "$perm" == "deny" ]] || fail "cursor fail-closed: expected=deny got=${perm:-empty} out=$out"
echo "OK  [cursor/deny] brak pliku polityki → fail-closed"

out=$(printf '{}' | node "$ADAPTER" nie-ma-takiego.sh)
perm=$(printf '%s' "$out" | field permissionDecision)
[[ "$perm" == "deny" ]] || fail "claude fail-closed: expected=deny got=${perm:-empty} out=$out"
echo "OK  [claude/deny] brak pliku polityki → fail-closed"

# Adapter zawsze konczy zerem — niezerowy kod ukrywa payload przy failClosed.
set +e
printf '{}' | node "$ADAPTER" nie-ma-takiego.sh --to cursor >/dev/null
code=$?
set -e
[[ "$code" -eq 0 ]] || fail "adapter powinien konczyc exit 0, byl $code"
echo "OK  [exit0] adapter konczy zerem takze przy fail-closed"

# --- argumenty leca do polityki, --to zostaje w adapterze -------------------
# gate-push.sh poza repo git nie ma czego pilnowac → allow w obu formatach.
out=$(cd "${TMPDIR:-/tmp}" 2>/dev/null || cd /; printf '{"command":"git push origin main"}' | node "$ADAPTER" gate-push.sh --to cursor)
printf '%s' "$out" | grep -q '"permission"' || fail "gate-push przez adapter nie zwrocil kontraktu Cursora: $out"
echo "OK  [cursor] gate-push przechodzi przez ten sam adapter"

echo "All guard adapter checks passed."
