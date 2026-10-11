#!/usr/bin/env bash
# Regresja adaptera kontraktu (templates/shared/guards/invoke-hook.js).
#
# Guardy mowia dialektem Claude Code. Adapter jest jedynym miejscem, ktore wie,
# ze Cursor ma wlasny ksztalt wejscia i wyjscia — te testy pilnuja tlumaczenia
# w obie strony, dopisywania tool_name (--tool) oraz zachowania fail-closed,
# gdy sam adapter nie ma czego odpalic.
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
  out=$(printf '{"command":"%s"}' "$cmd" | node "$ADAPTER" git-guard.mjs --to cursor)
  perm=$(printf '%s' "$out" | field permission)
  [[ "$perm" == "$expect" ]] || fail "cursor: expected=$expect got=${perm:-empty} cmd=$cmd out=$out"
  echo "OK  [cursor/$expect] $cmd"
}

expect_claude() {
  local cmd="$1" expect="$2" out perm
  out=$(printf '{"tool_input":{"command":"%s"}}' "$cmd" | node "$ADAPTER" git-guard.mjs)
  perm=$(printf '%s' "$out" | field permissionDecision)
  [[ "$perm" == "$expect" ]] || fail "claude: expected=$expect got=${perm:-empty} cmd=$cmd out=$out"
  echo "OK  [claude/$expect] $cmd"
}

# --- ta sama polityka, dwa kontrakty ----------------------------------------
for pair in "git status:allow" "git reset --hard:deny" "git stash:allow" "git push origin feat/x:allow" "git push origin main:deny"; do
  cmd="${pair%:*}"
  want="${pair##*:}"
  expect_cursor "$cmd" "$want"
  expect_claude "$cmd" "$want"
done

# --- Cursor dostaje komunikaty dla uzytkownika i agenta ---------------------
out=$(printf '{"command":"git reset --hard"}' | node "$ADAPTER" git-guard.mjs --to cursor)
printf '%s' "$out" | grep -q '"user_message"' || fail "cursor deny bez user_message: $out"
printf '%s' "$out" | grep -q '"agent_message"' || fail "cursor deny bez agent_message: $out"
echo "OK  [cursor] deny niesie user_message + agent_message"

# allow ma zostac minimalne — bez zbednych pol
out=$(printf '{"command":"git status"}' | node "$ADAPTER" git-guard.mjs --to cursor)
printf '%s' "$out" | grep -q 'user_message' && fail "cursor allow nie powinien niesc user_message: $out"
echo "OK  [cursor] allow jest minimalne"

# --- domyslny format to Claude (bez --to) -----------------------------------
out=$(printf '{"tool_input":{"command":"git status"}}' | node "$ADAPTER" git-guard.mjs)
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

# --- --tool dopisuje tool_name dla Cursora ----------------------------------
# beforeReadFile daje file_path + content bez nazwy narzedzia; lockfile na odczyt
# przechodzi, ale ten sam plik z --tool Write ma byc deny.
out=$(printf '{"file_path":"uv.lock","content":""}' | node "$ADAPTER" sensitive-files-guard.mjs --to cursor --tool Read)
perm=$(printf '%s' "$out" | field permission)
[[ "$perm" == "allow" ]] || fail "cursor --tool Read uv.lock: expected=allow got=${perm:-empty} out=$out"
out=$(printf '{"file_path":"uv.lock"}' | node "$ADAPTER" sensitive-files-guard.mjs --to cursor --tool Write)
perm=$(printf '%s' "$out" | field permission)
[[ "$perm" == "deny" ]] || fail "cursor --tool Write uv.lock: expected=deny got=${perm:-empty} out=$out"
out=$(printf '{"file_path":".env","content":""}' | node "$ADAPTER" sensitive-files-guard.mjs --to cursor --tool Read)
perm=$(printf '%s' "$out" | field permission)
[[ "$perm" == "deny" ]] || fail "cursor --tool Read .env: expected=deny got=${perm:-empty} out=$out"
echo "OK  [cursor] --tool Read/Write rozroznia odczyt od zapisu"

# --- zero ask: adapter nigdy nie tlumaczy na "ask" -----------------------------
for cmd in "git stash" "git restore x" "rm -rf node_modules" "git commit --no-verify -m x"; do
  out=$(printf '{"command":"%s"}' "$cmd" | node "$ADAPTER" git-guard.mjs --to cursor)
  perm=$(printf '%s' "$out" | field permission)
  [[ "$perm" == "allow" ]] || fail "zero-ask: $cmd powinno byc allow, jest ${perm:-empty}"
done
echo "OK  [cursor] polityka bez ask (ADR 0006)"

# --- OpenCode: payload pluginu { tool, input } -> { decision, reason } ---------
# Plugin podaje nazwę narzędzia Claude w --tool; V2 (2.0.24) ma `path`, starsze `filePath`.
expect_opencode() {
  local payload="$1" guard="$2" tool="$3" expect="$4" out dec
  out=$(printf '%s' "$payload" | node "$ADAPTER" "$guard" --to opencode --tool "$tool")
  dec=$(printf '%s' "$out" | field decision)
  [[ "$dec" == "$expect" ]] || fail "opencode: expected=$expect got=${dec:-empty} payload=$payload out=$out"
  echo "OK  [opencode/$expect] $payload"
}
expect_opencode '{"tool":"shell","input":{"command":"git status"}}' git-guard.mjs Bash allow
expect_opencode '{"tool":"shell","input":{"command":"git reset --hard"}}' git-guard.mjs Bash deny
expect_opencode '{"tool":"shell","input":{"command":"git push origin master"}}' git-guard.mjs Bash deny
expect_opencode '{"tool":"read","input":{"path":".env"}}' sensitive-files-guard.mjs Read deny
expect_opencode '{"tool":"read","input":{"filePath":".env"}}' sensitive-files-guard.mjs Read deny
expect_opencode '{"tool":"read","input":{"path":"uv.lock"}}' sensitive-files-guard.mjs Read allow
expect_opencode '{"tool":"write","input":{"path":"uv.lock","content":""}}' sensitive-files-guard.mjs Write deny
expect_opencode '{"tool":"edit","input":{"path":"src/.env.local"}}' sensitive-files-guard.mjs Edit deny
# Pole, którego adapter nie zna, nie może przepuścić narzędzia (fail-closed).
expect_opencode '{"tool":"shell","input":{}}' git-guard.mjs Bash deny
expect_opencode '{"tool":"read","input":{"file":".env"}}' sensitive-files-guard.mjs Read deny
out=$(printf '{"tool":"shell","input":{"command":"git reset --hard"}}' | node "$ADAPTER" git-guard.mjs --to opencode --tool Bash)
printf '%s' "$out" | field reason | grep -q . || fail "opencode deny bez reason: $out"
out=$(printf '{}' | node "$ADAPTER" nie-ma-takiego.sh --to opencode)
[[ "$(printf '%s' "$out" | field decision)" == "deny" ]] || fail "opencode fail-closed: $out"
echo "OK  [opencode] deny niesie reason, brak polityki = deny"

echo "All guard adapter checks passed."
