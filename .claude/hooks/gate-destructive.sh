#!/usr/bin/env bash
# Wspolny guardrail: blokuj agresywne / destrukcyjne komendy gita i shella.
# Jedno zrodlo polityki dla wszystkich klientow (templates/shared/guards/).
#
# Skrypt mowi JEDNYM dialektem — kontraktem hooka Claude Code:
#   wejscie : .tool_input.command (akceptuje tez .command)
#   wyjscie : { "hookSpecificOutput": { "permissionDecision": ... } }
#
# Klienci o innym kontrakcie (Cursor: .command / "permission") dostaja tlumaczenie
# w invoke-hook.js — wiedza o kliencie zyje w adapterze, nie w polityce.
#
#   Cursor: node .cursor/hooks/invoke-hook.js gate-destructive.sh --to cursor
#   Claude: node .claude/hooks/invoke-hook.js gate-destructive.sh
#
# Windows: NIE podawaj samej sciezki .sh w konfiguracji hooka — klient odpala
# wtedy `bash --login -i` i zostawia otwarte okna konsoli. Zawsze przez invoke-hook.js.
set -u


emit() {
  # $1 = decyzja (allow|ask|deny), $2 = krotki powod (opcjonalnie)
  local perm="$1"
  local reason="${2:-brak wzorca destrukcyjnego}"
  reason=${reason//\/\\}
  reason=${reason//\"/\\\"}
  printf '%s\n' "{ \"hookSpecificOutput\": { \"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"${perm}\", \"permissionDecisionReason\": \"${reason}\" } }"
}

# Przy wyjściu bez wcześniejszego emit: allow przy sukcesie, ask przy błędzie.
# Po emit JSON zawsze kończymy z exit 0 — invoke-hook przekazuje status bash do Cursor
# (failClosed: true inaczej zignoruje permission i zablokuje komendę).
_emitted=0
finish_allow() {
  local code=$?
  if [[ "${_emitted}" -eq 0 ]]; then
    if [[ "$code" -ne 0 ]]; then
      emit ask "hook error (exit ${code}) — potwierdź ręcznie"
      _emitted=1
      exit 0
    else
      emit allow
    fi
    _emitted=1
  fi
}
trap finish_allow EXIT

input=$(cat 2>/dev/null || true)

# Adapter (invoke-hook.js) juz sparsowal payload i podaje komende w GUARD_COMMAND.
# To jedyna sciezka w praktyce — omija start interpretera przy kazdym wywolaniu.
# Fallback (bezposrednie odpalenie skryptu, np. w testach) parsuje JSON sam.
# Cursor podaje `.command`, Claude Code `.tool_input.command` — akceptuj oba.
command=""
# Pusty wynik znaczy "payload nie niesie komendy" (inne narzedzie) — to allow.
# Nieczytelny payload to co innego: nie wiemy, co bysmy przepuscili, wiec ask.
# Ekstraktor sygnalizuje to sentinelem, zeby oba przypadki dalo sie rozroznic.
PARSE_ERROR="__GUARD_PARSE_ERROR__"

if [[ -n "${GUARD_COMMAND+set}" ]]; then
  command="$GUARD_COMMAND"
elif command -v jq >/dev/null 2>&1; then
  command=$(printf '%s' "$input" | jq -r '.command // .tool_input.command // empty' 2>/dev/null || printf '%s' "$PARSE_ERROR")
elif command -v node >/dev/null 2>&1; then
  # Zly JSON = wyjatek = niezerowy kod, wiec sentinel wystarczy podpiac pod `||`.
  command=$(COMMAND_JSON="$input" node -e 'const d=JSON.parse(process.env.COMMAND_JSON||"{}");process.stdout.write(d.command||(d.tool_input||{}).command||"")' 2>/dev/null || printf '%s' "$PARSE_ERROR")
else
  for py in python python3; do
    if command -v "$py" >/dev/null 2>&1; then
      # Jedna linia: shim `python` z pyenv-win rozbija wieloliniowy argument -c.
      command=$(COMMAND_JSON="$input" "$py" -c 'import json,os,sys; d=json.loads(os.environ.get("COMMAND_JSON") or "{}"); sys.stdout.write(d.get("command") or (d.get("tool_input") or {}).get("command") or "")' 2>/dev/null || printf '%s' "$PARSE_ERROR")
      [[ -n "$command" ]] && break
    fi
  done
fi

if [[ "${command}" == "$PARSE_ERROR" ]]; then
  _emitted=1
  trap - EXIT
  emit ask "nieczytelny payload hooka — potwierdz recznie"
  exit 0
fi

if [[ -z "${command}" ]]; then
  _emitted=1
  emit allow
  exit 0
fi

# Normalizacja bialych znakow bez `tr`/`sed` — te dwa potoki to cztery procesy
# na kazde wywolanie bramki, czyli ~0,17 s na Windows. Podstawienia parametrow
# robia to samo bez tworzenia procesu.
normalized=${command//[$'\n\r\t']/ }
while [[ "$normalized" == *"  "* ]]; do
  normalized=${normalized//  / }
done

# Dopasowanie robi wbudowane [[ =~ ]], nie `printf | grep`.
#
# Kazde sprawdzenie wzorca kosztowalo dwa procesy, a polityka robi ich 33 —
# na Windows tworzenie procesu to ~0,12 s, wiec jedno wywolanie bramki zajmowalo
# ~2,5 s i suita regresji chodzila 158 s zamiast kilku. Wbudowane dopasowanie
# nie tworzy procesu wcale.
#
# Wzorce to ERE po obu stronach (grep -E i regcomp), wiec skladnia zostaje bez
# zmian. `nocasematch` zastepuje flage -i i jest wlaczany TYLKO na czas
# dopasowania — globalnie zmienialby tez `case` nizej (m.in. */tmp/claude/*),
# czyli poszerzalby polityke przy okazji optymalizacji.
#
# Wzorzec MUSI byc nieocytowany: w cudzyslowie [[ =~ ]] traktuje go jak zwykly
# tekst i bramka przestaje lapac cokolwiek — po cichu, bez bledu.
has() {
  local rc
  shopt -s nocasematch
  [[ "$normalized" =~ $1 ]] && rc=0 || rc=1
  shopt -u nocasematch
  return "$rc"
}

# True if push targets protected branch ref (main|master|dev), not remote named "dev".
# Handles force refspecs with leading "+" (e.g. origin +main, +main:main, +refs/heads/main).
targets_protected_ref() {
  if has 'origin[ ]+\+?(main|master|dev)([ ]|$|:)' \
    || has 'origin/\+?(main|master|dev)([ ]|$|:)' \
    || has 'upstream[ ]+\+?(main|master|dev)([ ]|$|:)' \
    || has '(^|[ ])\+(main|master|dev)([ ]|$|:)' \
    || has '(^|[ ])\+refs/heads/(main|master|dev)([ ]|$|:)' \
    || has 'HEAD:\+?(main|master|dev)([ ]|$)' \
    || has '\+[^ ]+:(main|master|dev)([ ]|$)' \
    || has 'refs/heads/\+?(main|master|dev)([ ]|$|:)' \
    || has '[^/+]:(main|master|dev)([ ]|$)' ; then
    return 0
  fi
  # Shorthand / URL: last refspec is main|master (never treat bare `dev` here).
  # `git push main` — only options between push and branch.
  # `git push <remote-or-url> main` — at least one non-option token before branch.
  if has 'git[ ]+push([ ]+-[^ ]+)*[ ]+\+?(main|master)[ ]*$' \
    || has 'git[ ]+push([ ]+-[^ ]+)*[ ]+[^ ]+[ ]+\+?(main|master)[ ]*$'; then
    return 0
  fi
  # Last refspec `dev` only when previous token is origin/upstream or URL/path (has / or :).
  # Bare `git push dev` = remote name → not protected.
  if has 'git[ ]+push([ ]+-[^ ]+)*[ ]+(origin|upstream)[ ]+\+?dev[ ]*$' \
    || has 'git[ ]+push([ ]+-[^ ]+)*[ ]+[^ ]+[/:][^ ]*[ ]+\+?dev[ ]*$'; then
    return 0
  fi
  return 1
}

# Force push: --force / -f / --force-with-lease OR plus-refspec (+branch).
# Plus must be its own token (space-bounded) — do NOT match URLs like git+https://…
is_force_push() {
  if ! has '(^|[ ])git[ ]+push[ ]'; then
    return 1
  fi
  has '--force([ =]|$)|--force-with-lease' \
    || has '(^|[ ])-f([ ]|$)' \
    || has '(^|[ ])\+[A-Za-z0-9_./:@-]+'
}

decide() {
  local perm="$1"
  local reason="$2"
  _emitted=1
  trap - EXIT
  emit "$perm" "$reason"
  exit 0
}

if is_force_push; then
  if targets_protected_ref; then
    decide deny "git force-push na main/master/dev"
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

if has '(^|[ ])git[ ]+push[ ]' && ! is_force_push; then
  if targets_protected_ref; then
    decide ask "git push na main/master/dev (preferuj PR)"
  fi
fi

# --- kasowanie niezacommitowanej pracy -------------------------------------
# Git odzyska wszystko, co zacommitowane. Te komendy niszcza to, czego nie odzyska,
# wiec sa jedyna kategoria naprawde nieodwracalna wewnatrz repo.
if has '(^|[ ])git[ ]+checkout[ ]+--([ ]|$)'; then
  decide ask "git checkout -- <sciezka> — kasuje niezacommitowane zmiany"
fi

if has '(^|[ ])git[ ]+restore[ ]' && ! has 'git[ ]+restore[ ]+--staged[ ]'; then
  decide ask "git restore — kasuje niezacommitowane zmiany"
fi

if has '(^|[ ])git[ ]+stash([ ]|$)' && ! has '(^|[ ])git[ ]+stash[ ]+(list|show|pop|apply|branch|drop)'; then
  decide ask "git stash — chowa niezacommitowana prace"
fi

# --- kasowanie plikow -------------------------------------------------------
# Szeroka sciezka: nadrzedny katalog, katalogi domowe (POSIX i Windows), $HOME,
# tylda, goly dysk. Windows notacja ma pojedyncze backslashe — stary wzorzec
# wymagal dwoch i nigdy nie trafial.
broad_path() {
  has '(\.\.|/home/|/Users/|[$]HOME|~/)' && return 0
  has '[A-Za-z]:[\\/]+(Users|Windows|Program)' && return 0
  has '[ ][A-Za-z]:[\\/]*[ ]*$' && return 0
  has '[ ]/[ ]*$' && return 0
  return 1
}

if has '(^|[ ])rm[ ]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)'; then
  if broad_path; then
    decide deny "rekursywne kasowanie z -f na szerokiej sciezce"
  fi
  decide ask "rekursywne kasowanie z -f"
fi

# Rekursywne kasowanie bez -f nadal usuwa cale drzewo.
if has '(^|[ ])rm[ ]+-[a-zA-Z]*r'; then
  if broad_path; then
    decide deny "rekursywne kasowanie na szerokiej sciezce"
  fi
  decide ask "rekursywne kasowanie katalogu"
fi

if has '(^|[ ])find[ ].*(-delete([ ]|$)|-exec[ ]+rm[ ])'; then
  decide ask "find kasujacy pliki"
fi

# --- zmiany poza projektem --------------------------------------------------
# W repo cofa git, wiec tam przepuszczamy. Poza repo nie cofa nic: inne
# repozytorium, katalog domowy, konfiguracja systemowa. Czytanie i szukanie
# zostaje wolne — pytamy dopiero, gdy komenda ma cos tam zmienic albo skasowac.
#
# GRANICA, ktora trzeba znac: to heurystyka na TEKSCIE komendy, nie analiza jej
# wykonania. Wylapuje jawna sciezke przy typowej komendzie mutujacej. NIE wylapie
# sciezki schowanej w zmiennej ($TARGET), zapisu z wnetrza python/node, ani
# `cd /gdzies && rm plik`. Prog zwalniajacy na pomylki, nie mur na zlosliwosc.
MUTATING='(^|[ ;&|(])(rm|mv|cp|install|ln|dd|shred|truncate|touch|mkdir|rmdir|chmod|chown|chgrp|tee|unlink)([ ]|$)'

norm_path() {
  # Porownanie ma dzialac tak samo na POSIX i na Windows: backslash -> slash,
  # male litery, "C:/x" -> "/c/x", bez koncowego slasha.
  local p="${1//\\//}"
  p=${p,,}   # wbudowane male litery zamiast `printf | tr` — bez procesu
  if [[ "$p" =~ ^([a-z]):/(.*)$ ]]; then
    p="/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  fi
  [[ "$p" == "/" ]] || p="${p%/}"
  printf '%s' "$p"
}

project_root() {
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || root=""
  [[ -n "$root" ]] || root="${CLAUDE_PROJECT_DIR:-$PWD}"
  printf '%s' "$root"
}

# Zwraca pierwszy argument-sciezke, ktory wychodzi poza projekt (albo nic).
outside_target() {
  local root_n home_n tok tok_n prev="" cur=""
  root_n=$(norm_path "$(project_root)")
  home_n=$(norm_path "${HOME:-}")
  set -f  # bez tego glob rozwinalby "*" z komendy na pliki z cwd
  for tok in $command; do
    # Poprzedni token — potrzebny, zeby odroznic cel przekierowania od zwyklego
    # argumentu. Przypisanie na gorze petli, bo ponizsze `continue` je omijaja.
    prev="$cur"
    cur="$tok"
    case "$tok" in
      -*) continue ;;
      /*|~*|[A-Za-z]:[\\/]*) ;;
      *..*) ;;
      *) continue ;;
    esac
    tok="${tok#[\"\']}"
    tok="${tok%[\"\']}"
    [[ "$tok" == '~'* ]] && tok="${home_n}${tok#\~}"
    tok_n=$(norm_path "$tok")
    case "$tok_n" in
      # Katalog tymczasowy agenta jest z zalozenia jednorazowy — nie warty promptu.
      */tmp/claude/*|*/temp/claude/*) continue ;;
      # Urzadzenia puste nie przechowuja nic, wiec przekierowanie tam nie jest
      # zmiana, ktora git mialby odzyskiwac. Lista jest zamknieta, nie prefiksem
      # `/dev/*`: /dev/sda czy /dev/tty to juz zapis, ktory chcemy widziec.
      #
      # Wyjatek obowiazuje TYLKO dla celu przekierowania (`>`, `>>`, `2>`).
      # W roli zwyklego argumentu ten sam token niszczy dane — `mv plik /dev/null`
      # kasuje plik bezpowrotnie — wiec tam pytamy dalej.
      /dev/null|/dev/stdout|/dev/stderr)
        case "$prev" in
          *'>') continue ;;
        esac
        ;;
    esac
    [[ "$tok_n" == "$root_n" || "$tok_n" == "$root_n"/* ]] && continue
    set +f
    printf '%s' "$tok"
    return 0
  done
  set +f
  return 1
}

if has "$MUTATING" \
  || has '(^|[ ])sed[ ]+(-[a-zA-Z]*i|--in-place)' \
  || has '>[ ]*[~/A-Za-z]'; then
  if outside=$(outside_target); then
    decide ask "zmiana poza projektem: ${outside} — git tego nie odzyska"
  fi
fi

_emitted=1
trap - EXIT
emit allow
exit 0
