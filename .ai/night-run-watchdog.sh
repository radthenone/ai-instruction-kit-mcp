#!/usr/bin/env bash
# Watchdog nocy night-run (#249). Śpi w tle i kończy się tylko wtedy, gdy trzeba obudzić
# orkiestratora. Kod 1 — anomalia (brak postępu dłużej niż próg). Kod 0 — linia stdout mówi,
# co się stało: `koniec nocy`, `życie`, `pauza trwa`, `wznowienie po pauzie limitu`.
# Użycie: watchdog.sh <CTX> [próg_anomalii_min=60] [życie_min=110]
# Testy: WATCHDOG_TICK_SEC (krok pętli, domyślnie 60), WATCHDOG_RECHECK_SEC (przerwa
# sprawdzania pauzy bez godziny resetu, domyślnie 1800). Wymaga GNU date (godzina resetu).
# Ceiling: pauza bez godziny wybudza po przerwie RECHECK, gdy nie ma nowej linii limitu
# w transkrypcie — to przybliżenie „limit minął”, orkiestrator weryfikuje to po wybudzeniu.
set -u

CTX="${1:?użycie: watchdog.sh <CTX> [próg_min] [życie_min]}"
ANOMALY_SEC=$(( ${2:-60} * 60 ))
LIFE_SEC=$(( ${3:-110} * 60 ))
TICK="${WATCHDOG_TICK_SEC:-60}"
RECHECK="${WATCHDOG_RECHECK_SEC:-1800}"
PAUSE_MARGIN_SEC=300
MAX_RESET_AHEAD_SEC=$(( 6 * 3600 ))
DIR="$(dirname "$CTX")"
START=$(date +%s)

state_value() { sed -n "s/^$1//p" "$CTX" | tail -n1; }

timestamp() { date -d "@$1" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date -r "$1" '+%Y-%m-%dT%H:%M:%S'; }

file_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

# Transkrypt subagenta z linii `subagent: <id>` w ## Stan (pusty wynik, gdy brak id).
subagent_transcripts() {
  local id file
  id=$(state_value "subagent: ")
  [[ -n $id ]] || return 0
  for file in "$HOME"/.claude/projects/*/*/subagents/agent-"$id".jsonl; do
    [[ -f $file ]] && printf '%s\n' "$file"
  done
}

# Najnowszy znak życia: pliki w katalogu nocy i transkrypt subagenta.
latest_activity() {
  local file mtime newest=0
  while IFS= read -r file; do
    mtime=$(file_mtime "$file")
    (( mtime > newest )) && newest=$mtime
  done < <( { for file in "$DIR"/*; do [[ -f $file ]] && printf '%s\n' "$file"; done; subagent_transcripts; } )
  echo "$newest"
}

cat_transcripts() {
  local file
  while IFS= read -r file; do cat "$file"; done < <(subagent_transcripts)
}

transcript_line_count() { cat_transcripts | wc -l | tr -d ' '; }

# Nowa linia limitu w transkrypcie od ostatniego sprawdzenia (logów /headless nie czytamy —
# limit wykonawcy to osobne issue). Przesuwa `limit_offset` w bieżącej powłoce, więc wynik
# idzie do `LIMIT_LINE_FOUND`, a nie przez `$(...)` (podpowłoka nie zapisałaby offsetu).
new_limit_line() {
  local total
  total=$(transcript_line_count)
  (( total < limit_offset )) && limit_offset=0
  # Tylko wpisy błędu API (isApiErrorMessage + rate_limit): fraza w tool_result (czytany plik) to nie limit (#262).
  LIMIT_LINE_FOUND=$(cat_transcripts | tail -n +$(( limit_offset + 1 )) \
    | grep -E '"isApiErrorMessage"[[:space:]]*:[[:space:]]*true' \
    | grep -E '"error"[[:space:]]*:[[:space:]]*"rate_limit"' | tail -n1)
  limit_offset=$total
}

# „resets 3pm” / „resets 15:30” → epoch najbliższej takiej godziny w przyszłości (≤ 6 h).
# Bez am/pm i bez `:MM` nie zgadujemy — zwraca pusto (ścieżka bez godziny).
reset_epoch() {
  local clock epoch now
  clock=$(printf '%s\n' "$1" | grep -o -i -E 'resets? (at )?([0-9]{1,2}:[0-9]{2}( ?(am|pm))?|[0-9]{1,2} ?(am|pm))' \
    | head -n1 | sed -E 's/^resets? (at )?//I')
  [[ -n $clock ]] || return 0
  epoch=$(date -d "$clock" +%s 2>/dev/null) || return 0
  now=$(date +%s)
  (( epoch <= now )) && epoch=$(( epoch + 86400 ))
  (( epoch - now > MAX_RESET_AHEAD_SEC )) && return 0
  echo "$epoch"
}

# Śpi do $1 w krokach TICK. Zwraca 1, gdy minęło życie watchdoga przed tym czasem.
wait_until() {
  local until=$1 now
  while :; do
    now=$(date +%s)
    (( now >= until )) && return 0
    (( now - START >= LIFE_SEC )) && return 1
    sleep $(( until - now < TICK ? until - now : TICK ))
  done
}

close_pause() { printf 'pauza limitu od %s do %s\n' "$1" "$(timestamp "$(date +%s)")" >> "$CTX"; }

# Zapisuje otwartą pauzę do ## Stan i czeka. Z godziną resetu: jedno czekanie do resetu + 5 min.
# Bez godziny: co RECHECK sprawdza, czy przyszła nowa linia limitu — jeśli tak, czeka dalej.
# Zawsze kończy skrypt.
pause_and_wait() {
  local limit_line=$1 pause_started=$2 reset_at until
  while :; do
    reset_at=$(reset_epoch "$limit_line")
    if [[ -n $reset_at ]]; then until=$(( reset_at + PAUSE_MARGIN_SEC )); else until=$(( $(date +%s) + RECHECK )); fi
    printf 'pauza limitu od %s; wznowienie %s (epoch %s)\n' "$pause_started" "$(timestamp "$until")" "$until" >> "$CTX"
    echo "pauza limitu do $(timestamp "$until") — śpię do wznowienia"
    if ! wait_until "$until"; then echo "pauza trwa — odnów watchdoga"; exit 0; fi
    [[ -n $reset_at ]] && break
    new_limit_line
    [[ -n $LIMIT_LINE_FOUND ]] || break
    limit_line=$LIMIT_LINE_FOUND
  done
  close_pause "$pause_started"
  echo "wznowienie po pauzie limitu"
  exit 0
}

# Otwarta pauza z poprzedniego watchdoga: przyszła — czekamy do jej epoch; przeterminowana —
# zamykamy i wchodzimy w pętlę (nie kończymy się od razu, żeby nie zapętlić wznowień).
open_line=$(grep '^pauza limitu od ' "$CTX" 2>/dev/null | tail -n1)
if [[ -n $open_line && $open_line != *" do "* ]]; then
  pause_epoch=$(printf '%s\n' "$open_line" | sed -n 's/.*(epoch \([0-9]*\)).*/\1/p')
  pause_started=$(printf '%s\n' "$open_line" | sed -n 's/^pauza limitu od \([^;]*\);.*/\1/p')
  if [[ -n $pause_epoch ]] && (( pause_epoch > $(date +%s) )); then
    if ! wait_until "$pause_epoch"; then echo "pauza trwa — odnów watchdoga"; exit 0; fi
    close_pause "$pause_started"
    echo "wznowienie po pauzie limitu"
    exit 0
  fi
  [[ -n $pause_started ]] && close_pause "$pause_started"
fi

last_seen=$(latest_activity)
last_progress=$START
limit_offset=$(transcript_line_count)

while :; do
  sleep "$TICK"
  if grep -q '^krok: koniec' "$CTX"; then echo "koniec nocy — watchdog kończy"; exit 0; fi
  new_limit_line
  [[ -n $LIMIT_LINE_FOUND ]] && pause_and_wait "$LIMIT_LINE_FOUND" "$(timestamp "$(date +%s)")"
  current=$(latest_activity)
  if (( current > last_seen )); then last_seen=$current; last_progress=$(date +%s); fi
  now=$(date +%s)
  if (( now - START >= LIFE_SEC )); then
    echo "życie: $(( (now - START) / 60 )) min — odnów watchdoga"
    exit 0
  fi
  if (( now - last_progress >= ANOMALY_SEC )); then
    echo "anomalia: brak postępu $(( (now - last_progress) / 60 )) min (próg $(( ANOMALY_SEC / 60 )))"
    exit 1
  fi
done
