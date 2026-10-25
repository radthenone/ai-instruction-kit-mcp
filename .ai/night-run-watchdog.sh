#!/usr/bin/env bash
# Watchdog nocy night-run (#249). Śpi w tle i kończy się tylko wtedy, gdy trzeba obudzić
# orkiestratora: exit 1 — anomalia (brak postępu dłużej niż próg); exit 0 — minęło życie
# (orkiestrator odnawia watchdoga), `krok: koniec` w ## Stan, albo wznowienie po pauzie limitu.
# Użycie: watchdog.sh <CTX> [próg_anomalii_min=60] [życie_min=110]
# Testy: WATCHDOG_TICK_SEC (krok pętli, domyślnie 60), WATCHDOG_RECHECK_SEC (pauza bez
# godziny resetu, domyślnie 1800). Ceiling: pauza bez godziny wybudza po jednym okresie
# RECHECK bez sprawdzenia, czy limit minął — orkiestrator to zweryfikuje.
set -u

CTX="${1:?użycie: watchdog.sh <CTX> [próg_min] [życie_min]}"
ANOM_SEC=$(( ${2:-60} * 60 ))
LIFE_SEC=$(( ${3:-110} * 60 ))
TICK="${WATCHDOG_TICK_SEC:-60}"
RECHECK="${WATCHDOG_RECHECK_SEC:-1800}"
DIR="$(dirname "$CTX")"
START=$(date +%s)

stan() { sed -n "s/^$1//p" "$CTX" | tail -n1; }

ts() { date -d "@$1" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date -r "$1" '+%Y-%m-%dT%H:%M:%S'; }

mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

# Najnowszy znak życia: pliki w katalogu nocy i transkrypt subagenta z linii `subagent: <id>`.
last_activity() {
  local f t m=0 id
  for f in "$DIR"/*; do
    [[ -f $f ]] || continue
    t=$(mtime "$f"); (( t > m )) && m=$t
  done
  id=$(stan "subagent: ")
  if [[ -n $id ]]; then
    for f in "$HOME"/.claude/projects/*/*/subagents/agent-"$id".jsonl; do
      [[ -f $f ]] || continue
      t=$(mtime "$f"); (( t > m )) && m=$t
    done
  fi
  echo "$m"
}

# Ostatnie linie logów i transkryptu z komunikatem limitu (pusta linia = brak limitu).
limit_line() {
  local id f
  id=$(stan "subagent: ")
  for f in "$DIR"/*.log "$HOME"/.claude/projects/*/*/subagents/agent-"$id".jsonl; do
    [[ -f $f ]] && tail -n 5 "$f"
  done | grep -i -E 'rate.limit|session limit|usage limit|limit reached|429' | tail -n1
}

# „resets 3pm” / „resets 15:30” → epoch najbliższej takiej godziny w przyszłości (GNU date).
reset_epoch() {
  local t e
  t=$(printf '%s\n' "$1" | grep -o -i -E 'resets? (at )?[0-9]{1,2}(:[0-9]{2})? ?(am|pm)?' | head -n1 \
    | sed -E 's/^resets? (at )?//I')
  [[ -n $t ]] || return 0
  e=$(date -d "$t" +%s 2>/dev/null) || return 0
  (( e <= $(date +%s) )) && e=$(( e + 86400 ))
  echo "$e"
}

wait_until() {
  local until=$1 now
  while :; do
    now=$(date +%s)
    (( now >= until )) && return 0
    sleep $(( until - now < TICK ? until - now : TICK ))
  done
}

# Zapisuje otwartą pauzę do ## Stan (bez „do” — zamyka ją orkiestrator) i śpi do wznowienia.
pause() {
  local now until
  now=$(date +%s)
  until=$(reset_epoch "$1")
  if [[ -n $until ]]; then until=$(( until + 300 )); else until=$(( now + RECHECK )); fi
  printf 'pauza limitu od %s; wznowienie %s (epoch %s)\n' "$(ts "$now")" "$(ts "$until")" "$until" >> "$CTX"
  echo "pauza limitu do $(ts "$until") — śpię, potem wznowienie"
  wait_until "$until"
  echo "wznowienie po pauzie limitu"
  exit 0
}

# Otwarta pauza z poprzedniego watchdoga: czekaj do jej epoch i zakończ się.
open=$(grep '^pauza limitu od ' "$CTX" 2>/dev/null | tail -n1)
if [[ -n $open && $open != *" do "* ]]; then
  until=$(printf '%s\n' "$open" | sed -n 's/.*(epoch \([0-9]*\)).*/\1/p')
  if [[ -n $until ]]; then
    wait_until "$until"
    echo "wznowienie po pauzie limitu"
    exit 0
  fi
fi

seen=$(last_activity)
last_ok=$START
ignored=$(limit_line)

while :; do
  sleep "$TICK"
  if grep -q '^krok: koniec' "$CTX"; then echo "koniec nocy — watchdog kończy"; exit 0; fi
  line=$(limit_line)
  if [[ -n $line && $line != "$ignored" ]]; then pause "$line"; fi
  cur=$(last_activity)
  if (( cur > seen )); then seen=$cur; last_ok=$(date +%s); fi
  now=$(date +%s)
  if (( now - START >= LIFE_SEC )); then
    echo "życie: $(( (now - START) / 60 )) min — odnów watchdoga"
    exit 0
  fi
  if (( now - last_ok >= ANOM_SEC )); then
    echo "anomalia: brak postępu $(( (now - last_ok) / 60 )) min (próg $(( ANOM_SEC / 60 )))"
    exit 1
  fi
done
