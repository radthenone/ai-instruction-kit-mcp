#!/usr/bin/env bash
# Bootstrap instruction-kit w repo aplikacji (multi-client).
#
# Użycie:
#   ./scripts/bootstrap-project.sh /sciezka/do/projektu [--from PATH|URL]
#   ./scripts/bootstrap-project.sh ../app --clients cursor
#   ./scripts/bootstrap-project.sh ../app --clients all
#
# Profil z Tierami (`.ai/project.profile.yaml`) zapisywany, gdy go brak — jedyne
# miejsce konfiguracji (ADR-0007). Na co dzień: `kit-ai install` / `kit-ai reload`.
# Domyślni klienci: all.
# Agenci: templates/shared/agents → natywne ścieżki klienta.
# Skille: templates/shared/skills → katalog skilli klienta (claude/cursor/antigravity)
#         albo komenda /nazwa u pozostałych (patrz scripts/install_shared_skills.py).

set -euo pipefail
# Windows: bez tego Pythony piszą stdout w cp1250 (reguły briefu mają znaki spoza niego).
export PYTHONUTF8=1

usage() {
  cat <<'EOF'
Użycie: bootstrap-project.sh TARGET_DIR [opcje]

Opcje:
  --language LANG     Język prozy instrukcji: pl|en (domyślnie: pl). Tytuły issue/PR zawsze EN
  --clients LIST      all | cursor | claude | codex | vscode | kiro | kilo | antigravity | opencode
                      (lista po przecinku; alias: copilot→vscode). Domyślnie: all
  --from SOURCE       Źródło uvx: ścieżka lokalna lub git+https://… (domyślnie: placeholder GitHub)
  --with-overlay      Skopiuj templates/project.md → .ai/project.md (jeśli brak)
  --skip-agents       Nie kopiuj agentów (/kit-ai:git-*, /kit-ai:review-*, /kit-ai:subagent-*) ani skilli
                      z templates/shared/skills/
  --with-plugins      Best-effort doinstaluj zewnętrzne pluginy (mattpocock skills przez npx;
                      Superpowers/Autopilot tylko instrukcja — to marketplace pluginów Claude/Cursor,
                      nie da się zainstalować z skryptu). Wymaga npx w PATH (Node.js)
  --keep-unselected-clients
                      Nie usuwaj plików klientów spoza --clients (domyślnie: sprzątane —
                      declarative sync, np. --clients claude usuwa .cursor/.codex/… kitowe pliki)
  --remove            Usuń z TARGET pliki kita wszystkich klientów, wpisy kita w .gitignore
                      i .claude/settings.json, Profil i stamp. Zostają .ai/project.md,
                      pliki użytkownika oraz AGENTS.md / BUGBOT.md / .gitattributes,
                      jeśli różnią się od szablonu kita
  -h, --help          Ta pomoc

Przykład (tylko Cursor):
  ./scripts/bootstrap-project.sh ../moj-projekt \
    --clients cursor \
    --from /m/projects/ai-instruction-kit-mcp \
    --with-overlay

Przykład (profil z Tierami, wszyscy klienci):
  ./scripts/bootstrap-project.sh ../moj-projekt \
    --clients all \
    --from /m/projects/ai-instruction-kit-mcp
  # potem w ../moj-projekt/.ai/project.profile.yaml wybierz Stacki (backend/web/mobile)
EOF
}

TARGET=""
LANGUAGE="pl"
CLIENTS_RAW="all"
FROM_SRC="git+https://github.com/radthenone/ai-instruction-kit-mcp.git"
WITH_OVERLAY=0
SKIP_AGENTS=0
WITH_PLUGINS=0
PRUNE_CLIENTS=1

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_AGENTS="$KIT_ROOT/templates/shared/agents"
# Komplet agentów (SHARED_AGENTS jest niżej podmieniane na zestaw po filtrze Tierów).
ALL_AGENTS="$SHARED_AGENTS"
# Kopie z dawnych instalacji zostają u użytkowników.
LEGACY_COMMAND_NAMES=(review-backend review-frontend review-ui subagent-backend subagent-frontend teacher-backend teacher-frontend)
PROFILE_TIERS=""
REMOVE=0
SHARED_GUARDS="$KIT_ROOT/templates/shared/guards"
SHARED_SKILLS="$KIT_ROOT/templates/shared/skills"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset|--profile|--with-profile|--codegen)
      echo "Opcja $1 została usunięta — Stacki i codegen są w .ai/project.profile.yaml." >&2
      echo "Odśwież istniejący projekt: kit-ai reload <ścieżka> (migruje starą konfigurację)." >&2
      exit 1
      ;;
    --language)
      LANGUAGE="$(echo "${2:?}" | tr '[:upper:]' '[:lower:]')"
      if [[ "$LANGUAGE" != "pl" && "$LANGUAGE" != "en" ]]; then
        echo "Nieprawidłowy --language: $LANGUAGE (dozwolone: pl, en)" >&2
        exit 1
      fi
      shift 2
      ;;
    --clients) CLIENTS_RAW="${2:?}"; shift 2 ;;
    --from) FROM_SRC="${2:?}"; shift 2 ;;
    --with-overlay) WITH_OVERLAY=1; shift ;;
    --skip-agents) SKIP_AGENTS=1; shift ;;
    --with-plugins) WITH_PLUGINS=1; shift ;;
    --keep-unselected-clients) PRUNE_CLIENTS=0; shift ;;
    --remove) REMOVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "Nieznana opcja: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "$TARGET" ]]; then
        TARGET="$1"
        shift
      else
        echo "Za dużo argumentów pozycyjnych" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  usage
  exit 1
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

# Ścieżka Workspace'u wpisywana do konfiguracji (Codex, opencode) i repo, z którego
# czytamy Taskfile / package.json. Dry-run (`plan_bootstrap`) leci na sandboxie
# i podaje tu prawdziwe repo przez KIT_WORKSPACE — wtedy plan widzi te same bajty,
# które zapisałby prawdziwy reload, w tej samej postaci ścieżki co `pwd` (#279).
WORKSPACE_PATH="$TARGET"
if [[ -n "${KIT_WORKSPACE:-}" ]]; then
  WORKSPACE_PATH="$(cd "$KIT_WORKSPACE" 2>/dev/null && pwd)" || {
    echo "KIT_WORKSPACE nie istnieje: $KIT_WORKSPACE" >&2
    exit 1
  }
fi

if [[ -d "$FROM_SRC" ]]; then
  FROM_SRC="$(cd "$FROM_SRC" && pwd)"
fi

# python3 (Linux/macOS) albo python (Windows / pyenv) — bez twardego `python`.
# `kit-ai` / serwer MCP podają własny interpreter (KIT_PYTHON): przy instalacji z koła
# (`uv tool install`) tylko on widzi pakiet `guides` — klonu z `src/` nie ma.
if [[ -n "${KIT_PYTHON:-}" ]]; then
  PYTHON_BIN="$KIT_PYTHON"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Brak interpretera Python (python3 lub python) w PATH" >&2
  exit 1
fi

# Shim (np. pyenv-win) psuje wielolinijkowe `-c` — od tej chwili prawdziwy interpreter (#420).
if [[ -z "${KIT_PYTHON:-}" ]]; then
  REAL_PYTHON="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
  if [[ -n "$REAL_PYTHON" ]]; then
    PYTHON_BIN="${REAL_PYTHON//\\//}"
  fi
fi

# Kopia szablonu do celu z podstawieniem @KIT_CMD_PREFIX@ / @KIT_NAME_PREFIX@ (#525).
# Wartości z manifest.yaml (command_prefixes); pliki bez placeholderów idą bajt w bajt jak cp.
copy_prefixed() {
  "$PYTHON_BIN" "$KIT_ROOT/scripts/command_prefix.py" copy "$KIT_ROOT/manifest.yaml" "$@"
}

# Bootstrap wymaga Pythona 3 (f-stringi / pathlib / type hints w guides.clients).
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
  echo "Wymagany Python 3 (znaleziono: $($PYTHON_BIN --version 2>&1))" >&2
  exit 1
fi

# --- Parse --clients (Python = jedno źródło prawdy z guides.clients) ---
CLIENTS_PARSE="$(
  CLIENTS_RAW="$CLIENTS_RAW" PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" - <<'PY'
import os
from guides.clients import expand_clients, format_clients_arg, parse_clients

try:
    parsed = parse_clients(os.environ.get("CLIENTS_RAW"))
except ValueError as exc:
    raise SystemExit(str(exc)) from exc
print(format_clients_arg(parsed))
for cid in expand_clients(parsed):
    print(cid)
PY
)" || {
  echo "Nieprawidłowy --clients: $CLIENTS_RAW" >&2
  echo "$CLIENTS_PARSE" >&2
  exit 1
}

CLIENTS_ARG="${CLIENTS_PARSE%%$'\n'*}"
CLIENTS_ARG="${CLIENTS_ARG//$'\r'/}"
CLIENTS_LIST=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line//$'\r'/}"
  [[ -z "$line" ]] && continue
  CLIENTS_LIST+=("$line")
done < <(echo "$CLIENTS_PARSE" | tail -n +2)

client_enabled() {
  local want="$1" c
  for c in "${CLIENTS_LIST[@]}"; do
    [[ "$c" == "$want" ]] && return 0
  done
  return 1
}

# Pliki kita jednego klienta = to, co install_<id> kładzie w pustym katalogu. Lista
# pochodzi z tych samych funkcji co instalacja (komplet agentów, bez filtra Tierów), więc
# prune i `--remove` nie trzymają drugiej, rozjeżdżającej się mapy ścieżek.
# `.claude/settings.json` pomijamy — należy do użytkownika, wpisy kita zdejmuje
# `claude_settings.py prune`. Tak samo `.agents/hooks.json` Antigravity: workspace'owy
# plik hooków użytkownika, klucz kita zdejmuje `antigravity_hooks.py prune`.
kit_files() {
  local id="$1" sandbox
  sandbox="$(mktemp -d)"
  if ! ( TARGET="$sandbox" SHARED_AGENTS="$ALL_AGENTS" SKIP_AGENTS=0; "install_$id" ) >/dev/null 2>&1; then
    rm -rf "$sandbox"
    echo "Nie udało się ustalić plików kita klienta $id" >&2
    return 1
  fi
  (cd "$sandbox" && find . -type f ! -path ./.claude/settings.json ! -path ./.agents/hooks.json | sed 's|^\./||' | sort)
  rm -rf "$sandbox"
}

# Czy katalog (ścieżka względem $TARGET) po rozwiązaniu dowiązań i junctionów leży
# w $TARGET (#566). `pwd -P` rozwiązuje też junction w Git Bash. Brak katalogu = nie.
dir_in_target() {
  local real root
  real="$(cd -P "$TARGET/$1" 2>/dev/null && pwd -P)" || return 1
  root="$(cd -P "$TARGET" && pwd -P)"
  [[ "$real" == "$root" || "$real" == "$root"/* ]]
}

# Usuń jeden plik kita (ścieżka względem $TARGET) i puste katalogi nad nim, aż do $TARGET.
# Cudzy plik w tym samym katalogu blokuje rmdir, więc katalog zostaje razem z nim.
# Katalog nadrzędny wskazujący poza workspace (dowiązanie, junction) — nic nie kasujemy.
kit_rm() {
  local rel="$1" dir
  [[ -e "$TARGET/$rel" || -L "$TARGET/$rel" ]] || return 0
  dir_in_target "$(dirname "$rel")" || return 0
  rm -f "$TARGET/$rel"
  echo "  - $rel"
  dir="$(dirname "$rel")"
  while [[ "$dir" != "." ]] && rmdir "$TARGET/$dir" 2>/dev/null; do
    dir="$(dirname "$dir")"
  done
}

# Ścieżki, po których poznać, że klient w ogóle jest w repo. Bez nich nie ma czego
# sprzątać — i nie płacimy za render listy przy każdym bootstrapie.
client_present() {
  local rel
  case "$1" in
    cursor) set -- .cursor ;;
    claude) set -- .claude .mcp.json ;;
    codex) set -- .codex ;;
    vscode) set -- .vscode .github ;;
    kiro) set -- .kiro ;;
    kilo) set -- .kilocode ;;
    antigravity) set -- .agents ;;
    opencode) set -- .opencode opencode.json ;;
  esac
  for rel in "$@"; do
    [[ -e "$TARGET/$rel" ]] && return 0
  done
  return 1
}

# Usuwa TYLKO pliki, które bootstrap sam kładzie dla danego klienta — po nazwie, nigdy
# całego katalogu. Własne agenty, komendy, hooki i skille użytkownika obok zostają.
# Plik użytkownika o nazwie identycznej z plikiem kita też zniknie (README).
prune_legacy_claude_commands() {
  local name
  for name in "$ALL_AGENTS"/*.md; do
    kit_rm ".claude/commands/$(basename "$name")"
  done
  for name in "${LEGACY_COMMAND_NAMES[@]}"; do
    kit_rm ".claude/commands/${name}.md"
  done
  rmdir "$TARGET/.claude/commands" 2>/dev/null || true
}

# Komendy kita spod starej ścieżki OpenCode (#527): przed #527 agentów, skille i
# /kit-ai:headless renderowaliśmy do `.opencode/command/<nazwa>.md` (wywołanie `/<nazwa>`).
# Teraz to `.opencode/commands/kit-ai/<nazwa>.md` (`/kit-ai/<nazwa>`). Od #567 także
# `/goal` i `/loop` (`/kit-ai/goal`, `/kit-ai/loop`), więc ich płaskie pliki też znikają.
prune_legacy_opencode_commands() {
  local name
  for name in goal loop; do
    kit_rm ".opencode/command/${name}.md"
  done
  for name in "$ALL_AGENTS"/*.md; do
    kit_rm ".opencode/command/$(basename "$name")"
  done
  for name in "${LEGACY_COMMAND_NAMES[@]}"; do
    kit_rm ".opencode/command/${name}.md"
  done
  if compgen -G "$SHARED_SKILLS/*/SKILL.md" >/dev/null; then
    for name in "$SHARED_SKILLS"/*/; do
      kit_rm ".opencode/command/$(basename "$name").md"
    done
  fi
  # Skill sprzed zmiany nazwy (`retro` → `kit-retro`, #422) znika tylko z markerem kita.
  if [[ -d "$TARGET/.opencode/command" ]]; then
    "$PYTHON_BIN" "$KIT_ROOT/scripts/install_shared_skills.py" prune-renamed opencode "$TARGET/.opencode/command" "$TARGET"
  fi
}

prune_client() {
  local id="$1" files rel name
  client_present "$id" || return 0
  files="$(kit_files "$id")"
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    # .cursor/BUGBOT.md bootstrap nadpisuje tylko nietknięty — dostosowany zostaje i tu.
    if [[ "$rel" == ".cursor/BUGBOT.md" ]] && ! bugbot_pristine "$TARGET/$rel"; then
      continue
    fi
    kit_rm "$rel"
  done <<< "$files"
  # Kitowe skille spod nazw sprzed zmiany (#422) — lista wyżej zna tylko nowe nazwy.
  # Mapa katalogów 1:1 z wywołaniami copy_shared_skills.
  local skills_dir=""
  case "$id" in
    cursor) skills_dir=".cursor/skills" ;;
    claude) skills_dir=".claude/skills" ;;
    codex) skills_dir=".codex/skills" ;;
    vscode) skills_dir=".github/prompts" ;;
    kiro) skills_dir=".kiro/agents" ;;
    kilo) skills_dir=".kilocode/workflows" ;;
    antigravity) skills_dir=".agents/skills" ;;
    opencode) skills_dir=".opencode/commands/kit-ai" ;;
  esac
  if [[ -d "$TARGET/$skills_dir" ]]; then
    "$PYTHON_BIN" "$KIT_ROOT/scripts/install_shared_skills.py" prune-renamed "$id" "$TARGET/$skills_dir" "$TARGET"
    rmdir "$TARGET/$skills_dir" 2>/dev/null && rmdir "$TARGET/$(dirname "$skills_dir")" 2>/dev/null || true
  fi
  # Pozostałości starszych wersji kita, których dzisiejsza instalacja już nie kładzie.
  case "$id" in
    cursor|claude)
      for name in gate-push.sh gate-destructive.sh gate-file-writes.mjs; do
        kit_rm ".$id/hooks/$name"
      done
      ;;
    codex)
      for name in "$ALL_AGENTS"/*.md backend-reviewer frontend-reviewer; do
        kit_rm ".codex/agents/$(basename "$name" .md).toml"
      done
      prune_shared_skills "$TARGET/.codex/agents"
      rmdir "$TARGET/.codex" 2>/dev/null || true
      ;;
    antigravity)
      for name in "$ALL_AGENTS"/*.md; do
        kit_rm ".agents/workflows/$(basename "$name")"
      done
      # `.agents/hooks.json` należy do użytkownika — zdejmujemy tylko klucz kita
      # (`kit-guards`); plik z cudzymi hookami zostaje, pusty znika.
      if [[ -f "$TARGET/.agents/hooks.json" ]]; then
        "$PYTHON_BIN" "$KIT_ROOT/scripts/antigravity_hooks.py" prune "$TARGET/.agents/hooks.json"
      fi
      rmdir "$TARGET/.agents" 2>/dev/null || true
      ;;
  esac
  # Płaskie komendy kita sprzątamy też dla odznaczonego klienta (#533), jak dla Claude.
  if [[ "$id" == "claude" ]]; then
    prune_legacy_claude_commands
  fi
  if [[ "$id" == "opencode" ]]; then
    prune_legacy_opencode_commands
  fi
  if [[ "$id" == "claude" && -f "$TARGET/.claude/settings.json" ]]; then
    "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" prune "$TARGET/.claude/settings.json"
  fi
  if [[ "$id" == "claude" ]]; then
    "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" prune-local "$TARGET/.claude/settings.local.json"
    rmdir "$TARGET/.claude" 2>/dev/null || true
  fi
}

prune_unselected_clients() {
  local id
  for id in cursor claude codex vscode kiro kilo antigravity opencode; do
    if ! client_enabled "$id"; then
      prune_client "$id"
    fi
  done
}

# Wypełnij szablon MCP (JSON/TOML): from, language, clients, opcjonalnie workspace.
# Tiery i codegen czyta serwer z `.ai/project.profile.yaml` w --workspace (ADR-0007),
# więc zmiana Stacka w profilu nie zmienia konfiguracji klienta.
fill_mcp() {
  local src="$1" dest="$2" workspace_repl="${3:-}"
  mkdir -p "$(dirname "$dest")"
  FROM_SRC="$FROM_SRC" LANGUAGE="$LANGUAGE" \
  CLIENTS_ARG="$CLIENTS_ARG" \
  WORKSPACE_REPL="$workspace_repl" SRC="$src" DEST="$dest" "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
import re
from pathlib import Path

src = Path(os.environ["SRC"])
dest = Path(os.environ["DEST"])
text = src.read_text(encoding="utf-8")
text = text.replace(
    "git+https://github.com/radthenone/ai-instruction-kit-mcp.git",
    os.environ["FROM_SRC"],
)
text = re.sub(
    r'("--language",\s*")[^"]*(")',
    rf'\g<1>{os.environ["LANGUAGE"]}\2',
    text,
)
text = re.sub(
    r'("--clients",\s*")[^"]*(")',
    rf'\g<1>{os.environ["CLIENTS_ARG"]}\2',
    text,
)
text = re.sub(
    r'("--workspace",\s*")[^"]*(")',
    lambda m: m.group(0)
    if not os.environ.get("WORKSPACE_REPL")
    else f'{m.group(1)}{os.environ["WORKSPACE_REPL"]}{m.group(2)}',
    text,
)
if os.environ.get("WORKSPACE_REPL"):
    # Codex placeholder path
    text = text.replace("/ABSOLUTNA/SCIEZKA/DO/PROJEKTU", os.environ["WORKSPACE_REPL"])

# Zrodlo lokalne: `uv run --project`, nie `uvx --from`.
#
# `uvx --from <katalog>` nie czyta kita z tego katalogu w czasie dzialania. uv buduje
# kolo, w ktorym `manifest.yaml` i `modules/` laduja jako `guides/_data`
# (force-include w pyproject.toml), i cache'uje je pod WERSJE pakietu. Wersja nie rosnie
# przy zwyklej edycji modulu ani kodu serwera, wiec klient dostaje kopie sprzed builda —
# poprawiasz modul, restartujesz IDE, a `get_bundle` zwraca stara tresc. Bez bledu.
# Do tego `find_kit_root` woli `_data` od repo, wiec `check_kit_status` traci historie
# gita i nie ma czego porownac ze stampem.
#
# `uv run --project <katalog>` instaluje pakiet z ukladem `src/` jako editable: `_data`
# w ogole nie powstaje, kod i moduly czytane sa wprost z klonu. Jedna zmiana naprawia
# jednoczesnie zamrozone moduly i zamrozony kod serwera. `--project` (w odroznieniu od
# `--directory`) nie zmienia katalogu roboczego procesu serwera.
#
# `--kit-root` dokladamy mimo to — nie jest juz konieczny, ale nazywa klon wprost, wiec
# konfiguracja mowi wprost, skad kit jest czytany, zamiast polegac na wnioskowaniu.
#
# Przy zrodle zdalnym (`git+https://…`) nic nie zmieniamy: klonu nie ma, `uvx` jest
# poprawnym wyborem, a `_data` z kola to jedyna i aktualna kopia.
from_src = os.environ["FROM_SRC"]
if Path(from_src).is_dir():
    # `uvx` występuje w szablonie raz — jako komenda (JSON `"command": "uvx"`,
    # TOML `command = "uvx"`, opencode jako pierwszy element tablicy `command`).
    text = text.replace('"uvx"', '"uv"', 1)
    # `--from X` i `run --project X` znaczą to samo dla obu poleceń: "weź pakiet stąd".
    text = re.sub(
        r'"--from",(\s*)"' + re.escape(from_src) + r'"',
        lambda m: f'"run", "--project",{m.group(1)}"{from_src}"',
        text,
        count=1,
    )
    if "--kit-root" not in text:
        # Wciecie i styl (JSON vs TOML, spacje po przecinku) biora sie z dopasowanej
        # linii, wiec wynik wyglada jak reszta pliku, ktorykolwiek klient go dostaje.
        text = re.sub(
            r'(^([ \t]*)"--clients",[^\n]*\n)',
            lambda m: f'{m.group(1)}{m.group(2)}"--kit-root", "{from_src}",\n',
            text,
            count=1,
            flags=re.MULTILINE,
        )

# Istniejący plik należy do użytkownika (własne serwery, modele, providerzy) i jest
# w .gitignore, więc nadpisanie go ginie bez śladu. Podmieniamy tylko wpis kita
# `kit-ai-mcp`, resztę zostawiamy. Pliku, którego nie umiemy sparsować (JSONC
# z komentarzami, uszkodzony JSON/TOML), nie scalamy: oryginał idzie do `.bak`.
KIT_SERVER = "kit-ai-mcp"
# Nazwa sprzed zmiany; przy scalaniu ją usuwamy, inaczej zostają dwa wpisy kita.
LEGACY_KIT_SERVERS = ("project-guides",)


def merge_json(old_text: str) -> str:
    old = json.loads(old_text)
    new = json.loads(text)
    key = next(k for k in ("mcpServers", "servers", "mcp") if k in new)
    if not isinstance(old, dict) or not isinstance(old.get(key, {}), dict):
        raise ValueError(f"`{key}` nie jest obiektem")
    merged = json.loads(json.dumps(old))
    for k, v in new.items():
        if k != key:
            merged.setdefault(k, v)
    servers = merged.setdefault(key, {})
    for legacy in LEGACY_KIT_SERVERS:
        servers.pop(legacy, None)
    servers[KIT_SERVER] = new[key][KIT_SERVER]
    if merged == old:
        return old_text
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


TOML_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")
TOML_KEY = re.compile(r'"(?:[^"\\]|\\.)*"|' + r"'[^']*'|[^.\s]+")


def toml_open_quote(line: str, quote: str | None) -> str | None:
    """Ogranicznik ciągu wielowierszowego otwartego po tej linii albo None.

    Skanuje linię jak lekser TOML: `#` poza ciągiem kończy linię (komentarz),
    zwykłe ciągi w cudzysłowach są pomijane, a ogranicznik poprzedzony backslashem
    w ciągu podstawowym nie zamyka go.
    """
    i = 0
    while i < len(line):
        if quote:
            j = line.find(quote, i)
            if j < 0:
                return quote
            slashes = len(line[i:j]) - len(line[i:j].rstrip("\\"))
            if quote == '"""' and slashes % 2 == 1:  # nieparzyste \ przed """ = escape
                i = j + 1
                continue
            i, quote = j + 3, None
            continue
        c = line[i]
        if c == "#":
            return None
        if line.startswith('"""', i) or line.startswith("'''", i):
            quote, i = line[i:i + 3], i + 3
            continue
        if c in "\"'":
            j = i + 1
            while j < len(line) and line[j] != c:
                j += 2 if c == '"' and line[j] == "\\" else 1
            i = j + 1
            continue
        i += 1
    return quote


def toml_kit_span(lines: list[str], server: str = KIT_SERVER) -> tuple[int, int] | None:
    """Zakres linii tabeli `[mcp_servers.<server>]` (z podtabelami) albo None."""
    start = None
    end = len(lines)
    quote = None  # otwarty ciąg wielowierszowy: nagłówek w jego treści to dane, nie tabela
    for i, line in enumerate(lines):
        m = TOML_HEADER.match(line) if quote is None else None
        quote = toml_open_quote(line, quote)
        if not m:
            continue
        # Klucze z kropkami dzielone z poszanowaniem cudzysłowów: `"project-guides.helper"` to jeden klucz.
        keys = [k[1:-1] if k[:1] in "\"'" else k for k in TOML_KEY.findall(m.group(1))]
        is_kit = keys[:2] == ["mcp_servers", server]
        if start is None and is_kit:
            start = i
        elif start is not None and not is_kit:
            end = i
            break
    if start is None:
        return None
    # Komentarze i puste linie tuż przed następną tabelą należą do niej, nie do kita.
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return start, end


def merge_toml(old_text: str) -> str:
    # ponytail: tekstowa podmiana tabeli; wpis kita zapisany inaczej (dotted key, inline
    # table) da duplikat — łapie go walidacja wyniku niżej, na Pythonie < 3.11 nie ma
    # `tomllib`, więc wtedy bez walidacji.
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib:
        tomllib.loads(old_text)
    new_lines = text.splitlines(keepends=True)
    s, e = toml_kit_span(new_lines)
    kit_block = new_lines[s:e]
    old_lines = old_text.splitlines(keepends=True)
    for legacy in LEGACY_KIT_SERVERS:
        # Do skutku: podtabela legacy oddzielona cudzą tabelą to osobny zakres.
        while legacy_span := toml_kit_span(old_lines, legacy):
            old_lines = old_lines[: legacy_span[0]] + old_lines[legacy_span[1] :]
    span = toml_kit_span(old_lines)
    if span is None:
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        sep = ["\n"] if old_lines and old_lines[-1].strip() else []
        merged = old_lines + sep + kit_block
    else:
        merged = old_lines[: span[0]] + kit_block + old_lines[span[1] :]
    result = "".join(merged)
    if tomllib:
        tomllib.loads(result)
    return result


if dest.is_file():
    old_text = dest.read_text(encoding="utf-8")
    try:
        text = merge_toml(old_text) if dest.suffix == ".toml" else merge_json(old_text)
    except Exception as exc:
        backup = dest.with_name(dest.name + ".bak")
        backup.write_text(old_text, encoding="utf-8", newline="\n")
        print(
            f"  ! {dest.name}: nie da się scalić ({exc.__class__.__name__}) — oryginał w "
            f"{backup.name}, przenieś swoje wpisy ręcznie"
        )
    else:
        if text == old_text:
            raise SystemExit(0)
dest.write_text(text, encoding="utf-8", newline="\n")
PY
}

# Wstaw (albo odśwież) sekcję kita w .gitignore repo aplikacji.
#
# Bootstrap instaluje kilkadziesiąt plików konfiguracji AI, ale to repo konsumenta
# decyduje, co trafia do gita — a typowy .gitignore ma `.claude/` wpisane hurtem, więc
# hooki bezpieczeństwa i komendy zostają tylko na maszynie, gdzie odpalono bootstrap.
#
# Sekcja jest ograniczona markerami i podmieniana w całości, więc kolejne przebiegi
# nie duplikują wpisów, a reguły spoza markerów zostają nietknięte. Marker końcowy
# jest wymagany: bez niego nie wiemy, gdzie kończy się nasza sekcja, więc wtedy
# dopisujemy nową na końcu, zamiast zgadywać i skasować cudze reguły.
GITIGNORE_BEGIN="# >>> instruction-kit >>>"
GITIGNORE_END="# <<< instruction-kit <<<"

# Pliki, które bootstrap renderuje ze ścieżką TEJ maszyny: `fill_mcp` wstawia do konfigów
# MCP lokalny klon kita (`uv run --project`, `--kit-root`) i absolutny `--workspace`,
# stamp zapisuje `kit_from`. Zacommitowane z jednej maszyny psują serwer MCP na każdej
# innej, więc idą do .gitignore (sekcja kita) i są sprawdzane w indeksie po instalacji.
# Ścieżki względem $TARGET, w składni .gitignore (wiodący `/` = tylko root repo).
MACHINE_FILES=(
  "/.mcp.json"
  "/.cursor/mcp.json"
  "/.vscode/mcp.json"
  "/.codex/config.toml"
  "/.kiro/settings/mcp.json"
  "/.kilocode/mcp.json"
  "/.agents/mcp_config.json"
  "/opencode.json"
  "/.ai/.kit-bootstrap.json"
  "/.ai/.kit-doctor.json"
)

sync_gitignore_section() {
  local target_file="$TARGET/.gitignore"
  local template="$KIT_ROOT/templates/gitignore-kit.txt"
  [[ -f "$template" ]] || return 0

  BEGIN_MARK="$GITIGNORE_BEGIN" END_MARK="$GITIGNORE_END" \
  SHARED_SKILLS="$SHARED_SKILLS" SHARED_AGENTS="$SHARED_AGENTS" CURSOR_SKILLS="$KIT_ROOT/templates/cursor/skills" \
  MACHINE_FILES="$(printf '%s\n' "${MACHINE_FILES[@]#/}")" \
  TEMPLATE="$template" DEST="$target_file" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

begin = os.environ["BEGIN_MARK"]
end = os.environ["END_MARK"]
dest = Path(os.environ["DEST"])
body = Path(os.environ["TEMPLATE"]).read_text(encoding="utf-8").strip("\n")


def skill_allow(dest_prefix: str, *source_dirs: str, names: tuple[str, ...] = ()) -> str:
    """Wyjątki `!` dla skilli kita — po nazwie, żeby nie wciągnąć cudzych.

    Katalog skilli u konsumenta miesza dwa źródła: te z kita (pliki) i dowiązania do
    `.agents/skills/` z `npx skills add` (ignorowane). Wersjonujemy tylko pierwsze.
    ``names`` dokłada nazwy spoza katalogów (agenty są plikami `*.md`).
    """
    collected: list[str] = list(names)
    for source in source_dirs:
        root = Path(source)
        if not root.is_dir():
            continue
        collected.extend(sorted(p.name for p in root.iterdir() if p.is_dir()))
    lines: list[str] = []
    for name in sorted(set(collected)):
        lines.append(f"!{dest_prefix}/{name}/")
        lines.append(f"!{dest_prefix}/{name}/**")
    return "\n".join(lines) if lines else f"# (kit nie dostarcza skilli dla {dest_prefix})"


shared = os.environ["SHARED_SKILLS"]
# Agenty tego przebiegu (po filtrze Tierów) trafiają do .agents/skills/ jako skille Antigravity.
agent_names = tuple(sorted(p.stem for p in Path(os.environ["SHARED_AGENTS"]).glob("*.md")))
body = body.replace(
    "@KIT_SKILLS_AGENTS@",
    skill_allow(".agents/skills", shared, names=agent_names),
)
body = body.replace("@KIT_SKILLS_CLAUDE@", skill_allow(".claude/skills", shared))
body = body.replace(
    "@KIT_SKILLS_CURSOR@",
    skill_allow(".cursor/skills", shared, os.environ["CURSOR_SKILLS"]),
)
# Wiodący `/` doklejamy dopiero tutaj: w env Git Bash (MSYS) zamieniłby pierwszą
# linię `/.mcp.json` na `C:/Program Files/Git/.mcp.json`.
# Do tego `.bak`, które `fill_mcp` zostawia przy nieparsowalnym konfigu — ta sama treść,
# często z tokenami w `env` serwerów MCP.
machine_files = "\n".join(
    f"/{line}\n/{line}.bak" if line.endswith((".json", ".toml")) and "kit-bootstrap" not in line
    else "/" + line
    for line in os.environ["MACHINE_FILES"].splitlines()
)
body = body.replace("@KIT_MACHINE_FILES@", machine_files)

section = f"{begin}\n{body}\n{end}\n"

existing = dest.read_text(encoding="utf-8") if dest.is_file() else ""

if begin in existing and end in existing:
    head, _, rest = existing.partition(begin)
    _, _, tail = rest.partition(end)
    updated = f"{head}{section}{tail.lstrip(chr(10))}"
    action = "zaktualizowano"
else:
    prefix = existing if not existing or existing.endswith("\n") else existing + "\n"
    separator = "\n" if prefix.strip() else ""
    updated = f"{prefix}{separator}{section}"
    action = "dodano"

if updated != existing:
    dest.write_text(updated, encoding="utf-8", newline="\n")
    print(f"  + .gitignore ({action} sekcję instruction-kit)")
PY
}

# Wpis w .gitignore nie odśledza pliku, który już siedzi w indeksie — repo zbootstrapowane
# zanim konfigi MCP trafiły do MACHINE_FILES mają je zacommitowane. Podajemy gotową
# komendę, ale indeksu nie ruszamy: co wypada z repo, decyduje użytkownik, nie instalator.
warn_tracked_machine_files() {
  git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  local tracked
  tracked="$(git -C "$TARGET" ls-files -- "${MACHINE_FILES[@]#/}" 2>/dev/null | tr '\n' ' ')"
  tracked="${tracked% }"
  [[ -n "$tracked" ]] || return 0
  echo ""
  echo "UWAGA: pliki per maszyna są wciąż śledzone przez git (zacommitowane przed tą wersją kita)."
  echo "Na innych maszynach psują serwer MCP. Odśledź je (zostają na dysku) i zacommituj:"
  echo "  git -C \"$TARGET\" rm --cached $tracked"
}

# Tiery z Profilu: `backend` gdy Tier backend wybrany, `client` gdy web lub mobile.
# Bez PyYAML (bootstrap leci na systemowym Pythonie) — Profil ma płaskie klucze Tierów.
# Legacy `stacks:` liczy się do Tierów tak jak w resolverze (`_filled_tiers`).
profile_tiers() {
  "$PYTHON_BIN" - "$TARGET/.ai/project.profile.yaml" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8") if path.is_file() else ""
empty = {"", "none", "null", "~", "false", "0", "no"}
filled = set()
for tier in ("backend", "web", "mobile"):
    match = re.search(rf"^{tier}:[ \t]*['\"]?([^'\"\s#]*)", text, re.MULTILINE)
    if match and match.group(1).lower() not in empty:
        filled.add(tier)
legacy = re.search(r"^stacks:[ \t]*\n((?:[ \t]+\S.*\n?)*)", text, re.MULTILINE)
for name, value in re.findall(r"^[ \t]+([\w-]+):[ \t]*(.*)$", legacy.group(1) if legacy else "", re.MULTILINE):
    if value.strip().strip("'\"").lower() in empty:
        continue
    if name == "django-drf":
        filled.add("backend")
    elif name == "expo-router":
        filled.update({"web", "mobile"})
tags = (["backend"] if "backend" in filled else []) + (["client"] if filled & {"web", "mobile"} else [])
print(" ".join(tags))
PY
}

# Agenci z `tier:` we frontmatterze trafiają do klienta tylko przy wybranym Tierze
# (`backend` / `client` = web lub mobile). Bloki `<!-- clients: a,b -->…<!-- /clients -->`
# zostają (bez znaczników) tylko, gdy któryś z wymienionych klientów jest w `--clients`
# projektu (#189). Staging w katalogu tymczasowym, bez linii `tier:` — wszystkie
# instalatory niżej czytają już przefiltrowany zestaw. Na stdout: nazwy pominiętych
# agentów (do sprzątnięcia z poprzedniego Bootstrapu).
stage_shared_agents() {
  local dest="$1"
  SRC="$SHARED_AGENTS" DEST="$dest" TIERS="$PROFILE_TIERS" HEADLESS="$HEADLESS" \
    CLIENTS="${CLIENTS_LIST[*]}" "$PYTHON_BIN" - <<'PY'
import os
import re
from pathlib import Path

chosen = set(os.environ["TIERS"].split())
clients = set(os.environ["CLIENTS"].split())
BLOCK = re.compile(r"<!-- clients: ([\w ,-]+) -->\n(.*?)<!-- /clients -->\n?", re.DOTALL)


def gate(match: re.Match) -> str:
    names = {name.strip() for name in match.group(1).split(",")}
    return match.group(2) if names & clients else ""


dest = Path(os.environ["DEST"])
for src in sorted(Path(os.environ["SRC"]).glob("*.md")):
    # /kit-ai:headless ma sens dopiero przy dwóch klientach z trybem headless (#169).
    if src.stem == "headless" and os.environ["HEADLESS"] != "1":
        print(src.stem)
        continue
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    tier = next(
        (line.partition(":")[2].strip() for line in lines[1:end] if line.startswith("tier:")),
        None,
    )
    if tier and tier not in chosen:
        print(src.stem)
        continue
    # `model-tier:` czyta tylko model_tiers.py, `classification:` guides.agent_classes
    # (oba z template) — klienci ich nie znają.
    kept = [
        line for i, line in enumerate(lines)
        if not (0 < i < end and line.startswith(("tier:", "model-tier:", "classification:")))
    ]
    text = BLOCK.sub(gate, "".join(kept))
    # Literówka w znaczniku nie może po cichu wypuścić treści bloku do innych klientów.
    if "<!-- clients" in text or "<!-- /clients" in text:
        raise SystemExit(f"{src.name}: niedomknięty albo zagnieżdżony blok <!-- clients: … -->")
    (dest / src.name).write_text(text, encoding="utf-8", newline="\n")
PY
}

# Dokument przekazania sesji designu (#189) — plik kita jak agenci: nadpisywany przy
# każdym bootstrapie, tylko z `claude` w `--clients` i Tierem web/mobile. Bez Tieru
# znika; bez `claude` znika razem z resztą plików claude (nie przy --keep-unselected-clients).
DESIGN_HANDOFF=docs/agents/design-handoff.md
install_design_handoff() {
  if [[ " ${CLIENTS_LIST[*]} " == *" claude "* ]]; then
    if [[ " $PROFILE_TIERS " == *" client "* ]]; then
      mkdir -p "$TARGET/docs/agents"
      copy_prefixed shared "$KIT_ROOT/templates/shared/docs/design-handoff.md" "$TARGET/$DESIGN_HANDOFF"
      echo "  + $DESIGN_HANDOFF (sesja designu: Claude Code)"
    else
      kit_rm "$DESIGN_HANDOFF"
    fi
  elif [[ "$PRUNE_CLIENTS" -eq 1 ]]; then
    kit_rm "$DESIGN_HANDOFF"
  fi
}

# /kit-ai:headless (#169): wrapper wspólny dla hostów + `@KIT_HOST@` w pliku agenta każdego
# klienta, żeby wrapper wiedział, kto woła (wykonawca != host). Wykonawcy = klienci
# z trybem headless i guardami kita — ta sama lista co EXECUTORS w headless.mjs.
HEADLESS_EXECUTORS="claude opencode antigravity"

headless_enabled() {
  local c n=0
  for c in "${CLIENTS_LIST[@]}"; do
    [[ " $HEADLESS_EXECUTORS " == *" $c "* ]] && n=$((n + 1))
  done
  [[ "$n" -ge 2 && "$SKIP_AGENTS" -eq 0 ]]
}


install_worktree() {
  mkdir -p "$TARGET/.ai"
  copy_prefixed shared "$KIT_ROOT/templates/shared/worktree/worktree.mjs" "$TARGET/.ai/worktree.mjs"
  chmod +x "$TARGET/.ai/worktree.mjs" 2>/dev/null || true
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_worktree.py" \
    "$TARGET" "$TARGET/.ai/project.profile.yaml" || echo "  ! worktree.json nie wyrenderowany" >&2
}

install_integrations() {
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_integrations.py" \
    "$TARGET" "$TARGET/.ai/project.profile.yaml" "$KIT_ROOT" || echo "  ! błąd renderowania integracji" >&2
}

install_headless() {
  local c rel
  if [[ "$HEADLESS" != "1" ]]; then
    kit_rm .ai/headless.mjs
    return 0
  fi
  copy_prefixed shared "$KIT_ROOT/templates/shared/headless/headless.mjs" "$TARGET/.ai/headless.mjs"
  for c in "${CLIENTS_LIST[@]}"; do
    case "$c" in
      cursor) set -- .cursor/agents/headless.md ;;
      claude) set -- .claude/agents/headless.md .claude/skills/kit-ai/skills/headless/SKILL.md ;;
      codex) set -- .codex/skills/headless/SKILL.md ;;
      vscode) set -- .github/prompts/headless.prompt.md ;;
      kiro) set -- .kiro/agents/headless.md ;;
      kilo) set -- .kilocode/workflows/headless.md ;;
      antigravity) set -- .agents/skills/headless/SKILL.md ;;
      opencode) set -- .opencode/commands/kit-ai/headless.md ;;
    esac
    for rel in "$@"; do
      [[ -f "$TARGET/$rel" ]] || continue
      # Bez `sed -i` — GNU i BSD różnią się składnią.
      sed "s/@KIT_HOST@/$c/g" "$TARGET/$rel" > "$TARGET/$rel.tmp" && mv "$TARGET/$rel.tmp" "$TARGET/$rel"
    done
  done
  echo "  + .ai/headless.mjs (/kit-ai:headless — wykonawcy: $HEADLESS_EXECUTORS)"
}

# Watchdog nocy /kit-ai:night-run (#249): skrypt odpalany przez Bash w tle — tylko z klientem claude
# (tam działa `run_in_background`). Bez claude albo z --skip-agents: usuwany przy reloadzie.
install_night_run_watchdog() {
  if ! client_enabled claude || [[ "$SKIP_AGENTS" -ne 0 ]]; then
    kit_rm .ai/night-run-watchdog.sh
    return 0
  fi
  copy_prefixed shared "$KIT_ROOT/templates/shared/night-run/watchdog.sh" "$TARGET/.ai/night-run-watchdog.sh"
  chmod +x "$TARGET/.ai/night-run-watchdog.sh"
  echo "  + .ai/night-run-watchdog.sh (watchdog /kit-ai:night-run)"
}

# Karta transportu T3 Code dla /kit-ai:night-run (#474) — instalowana jako .ai/night-run-t3.md
# tylko gdy Profil ma `t3code` w `integrations:` (#514). Bez agentów (--skip-agents) albo bez
# `t3code` karta jest usuwana przy reloadzie. Profil nieczytelny, niejednoznaczny lub bez PyYAML: stan karty bez zmian.
install_night_run_t3() {
  local rc=0
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    kit_rm .ai/night-run-t3.md
    return 0
  fi
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_integrations.py" \
    --has t3code "$TARGET" "$TARGET/.ai/project.profile.yaml" "$KIT_ROOT" || rc=$?
  case "$rc" in
    0) ;;
    3) kit_rm .ai/night-run-t3.md; return 0 ;;
    2) return 0 ;;  # Profil nieczytelny, niejednoznaczny lub bez PyYAML: karta bez zmian (ostrzeżenie wypisał Python)
    *) echo "  ! nie ustalono t3code (kod $rc) — karta T3 bez zmian" >&2; return 0 ;;
  esac
  copy_prefixed shared "$KIT_ROOT/templates/shared/night-run/t3.md" "$TARGET/.ai/night-run-t3.md"
  echo "  + .ai/night-run-t3.md (karta transportu T3 /kit-ai:night-run)"
}

# Usuwa katalog skilla kita, gdy zawiera samo SKILL.md. Drugi argument 1 = agent wyłączony Tierem:
# przy dodatkowych plikach usuwa tylko SKILL.md (komenda znika z pluginu), zasoby zostają z komunikatem.
prune_kit_skill_dir() {
  local dir="$1" drop_skill_md="${2:-0}"
  [[ -d "$dir" ]] || return 0
  # Dowiązanie to cudzy skill; find go nie przejdzie, a rm -rf skasowałby sam link.
  if [[ -L "$dir" ]]; then
    echo "  ! $dir zostaje: dowiązanie"
    return 0
  fi
  if [[ -z "$(find "$dir" -mindepth 1 ! -name SKILL.md)" ]]; then
    rm -rf "$dir"
    echo "  - $dir (usunięto)"
  elif [[ "$drop_skill_md" == 1 && -f "$dir/SKILL.md" ]]; then
    rm -f "$dir/SKILL.md"
    echo "  - $dir/SKILL.md (usunięto, zasoby zostają)"
  else
    echo "  ! $dir zostaje: ma pliki spoza SKILL.md"
  fi
}

# Pliki agentów pominiętych przez Tier — po nazwie, we wszystkich formatach klientów
# (mapa 1:1 z copy_shared_agents / render_agent_commands / install_codex_agents).
# Tier zmieniony na `none` = agenci znikają przy reload.
prune_tier_agents() {
  local name
  for name in $SKIPPED_AGENTS; do
    rm -f "$TARGET/.claude/agents/$name.md" \
      "$TARGET/.cursor/agents/$name.md" "$TARGET/.kiro/agents/$name.md" \
      "$TARGET/.github/prompts/$name.prompt.md" "$TARGET/.kilocode/workflows/$name.md" \
      "$TARGET/.agents/workflows/$name.md" "$TARGET/.opencode/commands/kit-ai/$name.md"
    prune_kit_skill_dir "$TARGET/.claude/skills/kit-ai/skills/$name" 1
    rm -rf "$TARGET/.codex/skills/$name" "$TARGET/.agents/skills/$name"
  done
}

# Sekcje `<!-- tier:X -->…<!-- /tier:X -->` w BUGBOT.md zostają tylko dla wybranych Tierów.
# Reszta pliku odświeża się z szablonu przy każdym reloadzie, ale blok
# `<!-- project:rules -->…<!-- /project:rules -->` przechodzi bez zmian (reguły projektu).
# Plik dostosowany przed wprowadzeniem bloku jest migrowany po historii szablonu (#240);
# gdy migracja jest niepewna, plik zostaje, a reload wypisuje jedną linię z trybem naprawy (#266).
# Na stdout: komunikat migracji albo ostrzeżenie (ścieżka „utworzono” należy do bash).
copy_bugbot_md() {
  SRC="$KIT_ROOT/templates/cursor/BUGBOT.md" \
    DEST="$1" \
    LABEL="${2:-BUGBOT.md}" \
    TIERS="$PROFILE_TIERS" \
    KIT_ROOT="$KIT_ROOT" \
    OVERLAY="$TARGET/.ai/project.md" \
    CHECK_ONLY="${CHECK_ONLY:-}" \
    "$PYTHON_BIN" "$KIT_ROOT/scripts/bugbot_md.py"
}

# Exit 0, gdy plik to nietknięty render BUGBOT.md kita — wtedy wolno go usunąć.
bugbot_pristine() {
  CHECK_ONLY=1 copy_bugbot_md "$1" >/dev/null
}

# `model:` i `effort:` z `targets.claude.<tier>` Profilu dla agentów kita (#168, ADR-0018).
# Bez wpisu pliki zostają jak z template — agent dziedziczy model sesji.
apply_model_tiers() {
  [[ "$SKIP_AGENTS" -eq 0 ]] || return 0
  "$PYTHON_BIN" "$KIT_ROOT/scripts/model_tiers.py" apply "$1" "$TARGET/.ai/project.profile.yaml" "$2"
}

copy_shared_agents() {
  local dest_dir="$1" target="$2"
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    return 0
  fi
  if [[ ! -d "$SHARED_AGENTS" ]]; then
    echo "Brak $SHARED_AGENTS — nie skopiowano agentów" >&2
    exit 1
  fi
  mkdir -p "$dest_dir"
  local src dest
  for src in "$SHARED_AGENTS/"*.md; do
    dest="$dest_dir/$(basename "$src")"
    copy_prefixed "$target" "$src" "$dest"
    # Kopie Claude: opis cytowany, bo " #" i ": " w nim ucinają albo psują YAML (#547).
    if [[ "$target" == claude ]]; then
      "$PYTHON_BIN" "$KIT_ROOT/scripts/quote_agent_description.py" "$dest"
    fi
  done
  echo "  + $dest_dir (shared agents)"
}

# Skille ze wspólnego źródła. Trzy klienty mają natywny katalog skilli, pozostałe
# dostają je jako komendę `/nazwa` — mapę i degradację trzyma install_shared_skills.py,
# tutaj zostaje tylko decyzja "czy w ogóle" i dokąd.
copy_shared_skills() {
  local client="$1" dest_dir="$2"
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    return 0
  fi
  # Puste źródło to poprawny stan (kit bez skilli) — inaczej niż przy agentach,
  # gdzie brak katalogu znaczy uszkodzony kit.
  if ! compgen -G "$SHARED_SKILLS/*/SKILL.md" >/dev/null; then
    return 0
  fi
  "$PYTHON_BIN" "$KIT_ROOT/scripts/install_shared_skills.py" \
    "$client" "$SHARED_SKILLS" "$dest_dir"
  echo "  + $dest_dir (shared skills, $client)"
}

# Kitowe skille w katalogu, który dzielimy z użytkownikiem (.claude/skills,
# .agents/skills — tam lądują też skille instalowane spoza kita). Kasujemy więc
# po nazwach ze źródła, nigdy całego katalogu.
prune_shared_skills() {
  local dest_dir="$1" skill
  [[ -d "$dest_dir" ]] || return 0
  for skill in "$SHARED_SKILLS"/*/; do
    [[ -d "$skill" ]] || continue
    rm -rf "$dest_dir/$(basename "$skill")"
  done
  rmdir "$dest_dir" 2>/dev/null || true
}

# AGENTS.md tym samym modelem co BUGBOT.md (#269): część kita z szablonu przy każdym
# reloadzie, treść projektu w bloku `<!-- project:agents -->`; plik sprzed bloku migrowany
# po historii `templates/AGENTS.md`, a niepewna migracja to jedna linia z trybem C.
# Blok `kit:brief` (#307) dostaje brief wyrenderowany z Profilu i overlayu — ten sam,
# który serwer MCP wkłada w swoje instructions.
install_agenty_md_once() {
  local existed=0
  [[ -f "$TARGET/AGENTS.md" ]] && existed=1
  SRC="$KIT_ROOT/templates/AGENTS.md" \
    DEST="$TARGET/AGENTS.md" \
    LABEL="AGENTS.md" \
    BLOCK="agents" \
    KIT_ROOT="$KIT_ROOT" \
    BRIEF="${BRIEF_FILE:-}" \
    BRIEF_RULES="${BRIEF_RULES_FILE:-}" \
    "$PYTHON_BIN" "$KIT_ROOT/scripts/bugbot_md.py"
  if [[ "$existed" -eq 0 ]]; then
    echo "  + AGENTS.md"
  fi
}

# Exit 0, gdy AGENTS.md to nietknięty render szablonu kita (brief dowolny) — wolno go usunąć.
agents_pristine() {
  SRC="$KIT_ROOT/templates/AGENTS.md" \
    DEST="$TARGET/AGENTS.md" \
    BLOCK="agents" \
    KIT_ROOT="$KIT_ROOT" \
    CHECK_ONLY=1 \
    "$PYTHON_BIN" "$KIT_ROOT/scripts/bugbot_md.py" >/dev/null
}

# Brief projektu (#307): jedno źródło z resolverem — czyta Profil i overlay, a wynik
# trafia do bloku `kit:brief` w AGENTS.md (Claude widzi go przez import `@AGENTS.md`
# w CLAUDE.md). Ścieżkę workspace'u podajemy przez KIT_WORKSPACE w dry-runie.
render_project_brief() {
  WORKSPACE="$WORKSPACE_PATH" LANGUAGE="$LANGUAGE" \
    "$PYTHON_BIN" "$KIT_ROOT/scripts/project_brief.py"
}

# Reguły briefu (#355, ADR-0010): renderowane z wariantu językowego Profilu.
render_brief_rules() {
  LANGUAGE="$LANGUAGE" KIT_ROOT="$KIT_ROOT" "$PYTHON_BIN" -c '
import os, sys
from pathlib import Path
kit_root = Path(os.environ["KIT_ROOT"])
sys.path.insert(0, str(kit_root / "src"))
from guides.brief_rules import get_brief_rules
lang = os.environ.get("LANGUAGE", "pl")
sys.stdout.write(get_brief_rules(lang).strip() + "\n")
'
}


# Kontrakt skilli Matta (#241): brakujące `docs/agents/*` z ziaren setupu Matta,
# blok `## Agent skills` w AGENTS.md i `CODING_STANDARDS.md` (indeks źródeł standardów).
# Wołane po AGENTS.md/BUGBOT.md/overlay, bo indeks wymienia tylko istniejące pliki.
# Brak `skills-lock.json` z `mattpocock/skills` albo ziaren = krok pomijany bez błędu.
install_matt_contract() {
  "$PYTHON_BIN" "$KIT_ROOT/scripts/matt_contract.py" "$TARGET" "$KIT_ROOT"
}

# BUGBOT.md w root — niezależnie od --clients, bo /kit-ai:review-bugbot (manualny odpowiednik)
# ma działać dla WSZYSTKICH klientów (Claude, Codex, VS Code…), nie tylko Cursor.
# .cursor/BUGBOT.md (install_cursor) zostaje osobno — to dla natywnej usługi Cursor
# BugBot, która czyta z tamtej ścieżki; ta funkcja to nie duplikat, to inny konsument.
install_bugbot_md_once() {
  local existed=0
  [[ -f "$TARGET/BUGBOT.md" ]] && existed=1
  copy_bugbot_md "$TARGET/BUGBOT.md"
  if [[ "$existed" -eq 0 ]]; then
    echo "  + BUGBOT.md (root — dla /kit-ai:review-bugbot wszystkich klientów)"
  fi
}

# Guardraile maja jedno zrodlo (templates/shared/guards) i trafiaja do katalogu
# hooków wybranego klienta. Kontrakt tlumaczy invoke-hook.js, wiec pliki sa te same.
install_guards() {
  local dest="$1"
  local target_client="${2:-shared}"
  mkdir -p "$dest"
  # Guards v1 (gate-*) kasowane po nazwie — reinstalacja na Workspace sprzed v2
  # ma zostawic wylacznie nowy zestaw.
  rm -f "$dest/gate-destructive.sh" "$dest/gate-push.sh" "$dest/gate-file-writes.mjs"
  copy_prefixed "$target_client" "$SHARED_GUARDS/git-guard.mjs" "$dest/git-guard.mjs"
  copy_prefixed "$target_client" "$SHARED_GUARDS/sensitive-files-guard.mjs" "$dest/sensitive-files-guard.mjs"
  copy_prefixed "$target_client" "$SHARED_GUARDS/server-guard.mjs" "$dest/server-guard.mjs"
  # Wspólna detekcja hosta importowana przez server-guard i language-reminder (ADR-0011).
  copy_prefixed "$target_client" "$SHARED_GUARDS/host-profile.mjs" "$dest/host-profile.mjs"
  copy_prefixed "$target_client" "$SHARED_GUARDS/invoke-hook.js" "$dest/invoke-hook.js"
  # Lista deny kita + rozwinięte wrappery (Taskfile / package.json / turbo) + sekcja
  # `server:` z Profilu → server-guard.json obok guarda. Guard bez reloadu działa
  # na starej liście wrapperów. Render nigdy nie wywala bootstrapu (ADR-0004).
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_server_guard.py" \
    "$WORKSPACE_PATH" "$dest" "$TARGET/.ai/project.profile.yaml" || echo "  ! server-guard.json nie wyrenderowany — guard działa na wbudowanej liście kita" >&2
}

install_cursor() {
  mkdir -p "$TARGET/.cursor/hooks" "$TARGET/.cursor/rules" "$TARGET/.ai"
  fill_mcp "$KIT_ROOT/templates/cursor/mcp.json" "$TARGET/.cursor/mcp.json"
  echo "  + .cursor/mcp.json"

  cp "$KIT_ROOT/templates/cursor/hooks.json" "$TARGET/.cursor/hooks.json"
  install_guards "$TARGET/.cursor/hooks" cursor
  echo "  + .cursor/hooks.json (node invoke-hook → guardy .mjs)"

  copy_prefixed cursor "$KIT_ROOT/templates/cursor/rules/use-guides.mdc" "$TARGET/.cursor/rules/use-guides.mdc"
  copy_prefixed cursor "$KIT_ROOT/templates/cursor/rules/code-review.mdc" "$TARGET/.cursor/rules/code-review.mdc"
  copy_prefixed cursor "$KIT_ROOT/templates/cursor/rules/git-branch-pr.mdc" "$TARGET/.cursor/rules/git-branch-pr.mdc"
  copy_bugbot_md "$TARGET/.cursor/BUGBOT.md" ".cursor/BUGBOT.md"

  copy_shared_agents "$TARGET/.cursor/agents" cursor

  if [[ -d "$KIT_ROOT/templates/cursor/skills" ]]; then
    mkdir -p "$TARGET/.cursor/skills"
    cp -R "$KIT_ROOT/templates/cursor/skills/." "$TARGET/.cursor/skills/"
    echo "  + .cursor/skills/ (Cursor-only, np. /compact)"
  fi

  copy_shared_skills cursor "$TARGET/.cursor/skills"
}

install_claude() {
  fill_mcp "$KIT_ROOT/templates/claude/mcp.json" "$TARGET/.mcp.json"
  echo "  + .mcp.json (Claude Code)"

  install_guards "$TARGET/.claude/hooks" claude
  # Tylko Claude Code: Cursor nie ma narzedzia Bash w tym sensie (bash-guard),
  # nie zwraca kontekstu z afterFileEdit (linters-guard) ani nie ma SessionStart.
  copy_prefixed claude "$SHARED_GUARDS/bash-guard.mjs" "$TARGET/.claude/hooks/bash-guard.mjs"
  copy_prefixed claude "$SHARED_GUARDS/linters-guard.mjs" "$TARGET/.claude/hooks/linters-guard.mjs"
  copy_prefixed claude "$SHARED_GUARDS/rtk-check.mjs" "$TARGET/.claude/hooks/rtk-check.mjs"
  # Przypomnienie o otwartej partii doctora (#269) — SessionStart, też Codex i Copilot.
  copy_prefixed claude "$SHARED_GUARDS/kit-doctor-reminder.mjs" "$TARGET/.claude/hooks/kit-doctor-reminder.mjs"
  # Skaner sesji po jej zakończeniu (#371): SessionEnd, tylko Claude Code.
  copy_prefixed claude "$SHARED_GUARDS/retro-session-end.mjs" "$TARGET/.claude/hooks/retro-session-end.mjs"
  # Blokada narzędzi zdalnej sesji dla subagentów (#403): przestrzeń istnieje tylko w Claude Code.
  copy_prefixed claude "$SHARED_GUARDS/subagent-remote-guard.mjs" "$TARGET/.claude/hooks/subagent-remote-guard.mjs"
  # Przypomnienie języka (#248, #356): hook UserPromptSubmit dla każdego języka (ADR 0010).
  cp "$KIT_ROOT/templates/claude/language-reminder.mjs" "$TARGET/.claude/hooks/language-reminder.mjs"
  SETTINGS_TEMPLATE="$(mktemp)"
  "$PYTHON_BIN" -c 'import json,sys
t = json.load(open(sys.argv[1], encoding="utf-8"))
t["hooks"]["UserPromptSubmit"] = json.load(open(sys.argv[2], encoding="utf-8"))["hooks"]["UserPromptSubmit"]
print(json.dumps(t))' "$KIT_ROOT/templates/claude/settings.json" "$KIT_ROOT/templates/claude/settings.language.json" > "$SETTINGS_TEMPLATE"
  # settings.json nalezy do uzytkownika — scalamy tylko wpisy kita.
  "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" install     "$TARGET/.claude/settings.json" "$SETTINGS_TEMPLATE"
  rm -f "$SETTINGS_TEMPLATE"
  # Matcher ponytaila poza gitem: lista agentów zależy od wersji kita (#316).
  "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" sync-local  "$TARGET/.claude/settings.local.json"
  # Claude Code czyta CLAUDE.md, nie AGENTS.md: import, żeby reguła języka była w kontekście.
  if [[ ! -f "$TARGET/CLAUDE.md" ]]; then
    printf '@AGENTS.md\n' > "$TARGET/CLAUDE.md"
    echo "  + CLAUDE.md (import @AGENTS.md)"
  fi
  echo "  + .claude/hooks/ + wpisy hookow kita w .claude/settings.json"

  copy_shared_agents "$TARGET/.claude/agents" claude
  apply_model_tiers claude "$TARGET/.claude/agents"
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    # Komendy od #526 to plugin skills-dir: `.claude/skills/kit-ai/` + `/kit-ai:<nazwa>`.
    # Stare płaskie `.claude/commands/*.md` z poprzednich wersji kita znikają przy reloadzie.
    prune_legacy_claude_commands
    render_agent_commands claude "$TARGET/.claude/skills/kit-ai"
  fi
  copy_shared_skills claude "$TARGET/.claude/skills"
}

# Agenci z templates/shared/agents/*.md → skille Codexa w .codex/skills/<nazwa>/.
# Codex nie ma formatu TOML-agentów od wycofania custom prompts; natywny format
# to katalog skilla z SKILL.md. Curated TOML-e z templates/codex/agents/ są
# przestarzałe — źródłem prawdy pozostaje templates/shared/agents/.
install_codex_agents() {
  "$PYTHON_BIN" "$KIT_ROOT/scripts/install_agent_skills.py" "$SHARED_AGENTS" "$TARGET/.codex/skills" codex
  echo "  + .codex/skills/ (agenty jako natywne skille Codexa)"
}

install_codex() {
  fill_mcp "$KIT_ROOT/templates/codex/config.toml" "$TARGET/.codex/config.toml" "$WORKSPACE_PATH"
  echo "  + .codex/config.toml"
  # Guardy kita (git-guard, sensitive-files-guard, server-guard) przed każdym
  # narzędziem Codexa — PreToolUse woła invoke-hook.js --to codex, deny działa
  # tak samo jak w Claude Code.
  install_guards "$TARGET/.codex/hooks" codex
  copy_prefixed codex "$SHARED_GUARDS/kit-doctor-reminder.mjs" "$TARGET/.codex/hooks/kit-doctor-reminder.mjs"
  cp "$KIT_ROOT/templates/codex/hooks.json" "$TARGET/.codex/hooks.json"
  echo "  + .codex/hooks/ + .codex/hooks.json (guardy kita PreToolUse, przypomnienie doctora SessionStart)"
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    # Codex czyta skille natywnie (.agents/skills i .codex/skills) — agenci i
    # skille z kita lądują jako katalogi SKILL.md, nie jako TOML-prompts
    # (custom prompts zostały wycofane w Codex CLI).
    install_codex_agents
    copy_shared_skills codex "$TARGET/.codex/skills"
  fi
}

render_agent_commands() {
  local fmt="$1" dest_dir="$2"
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    return 0
  fi
  if [[ ! -d "$SHARED_AGENTS" ]]; then
    echo "Brak $SHARED_AGENTS — nie wyrenderowano komend ($fmt)" >&2
    exit 1
  fi
  if [[ "$fmt" == "claude" && -d "$dest_dir/skills" ]]; then
    local orphan_dir orphan_name
    for orphan_dir in "$dest_dir/skills"/*; do
      [[ -d "$orphan_dir" ]] || continue
      orphan_name="$(basename "$orphan_dir")"
      if [[ ! -f "$ALL_AGENTS/$orphan_name.md" ]]; then
        prune_kit_skill_dir "$orphan_dir"
      fi
    done
  fi
  "$PYTHON_BIN" "$KIT_ROOT/scripts/render_agent_commands.py" "$fmt" "$SHARED_AGENTS" "$dest_dir"
  echo "  + $dest_dir ($fmt slash commands)"
}

install_vscode() {
  mkdir -p "$TARGET/.vscode" "$TARGET/.github"
  fill_mcp "$KIT_ROOT/templates/vscode/mcp.json" "$TARGET/.vscode/mcp.json"
  echo "  + .vscode/mcp.json"
  if [[ -f "$KIT_ROOT/templates/vscode/github/copilot-instructions.md" ]]; then
    copy_prefixed vscode "$KIT_ROOT/templates/vscode/github/copilot-instructions.md" \
      "$TARGET/.github/copilot-instructions.md"
    echo "  + .github/copilot-instructions.md"
  fi
  # Guardy kita przed każdym narzędziem Copilota (VS Code Local i Copilot CLI czytają
  # `.github/hooks/*.json`): PreToolUse woła invoke-hook.js --to copilot, deny działa
  # jak w Claude Code. bash-guard/linters-guard/rtk-check zostają wyłącznie dla Claude
  # Code — Copilot ma jedno narzędzie powłoki, więc nie ma czego rozdzielać.
  install_guards "$TARGET/.github/hooks" vscode
  copy_prefixed vscode "$SHARED_GUARDS/kit-doctor-reminder.mjs" "$TARGET/.github/hooks/kit-doctor-reminder.mjs"
  cp "$KIT_ROOT/templates/vscode/github/hooks/kit-guards.json" \
    "$TARGET/.github/hooks/kit-guards.json"
  echo "  + .github/hooks/ + .github/hooks/kit-guards.json (guardy kita PreToolUse, przypomnienie doctora SessionStart)"
  # rtk dla Copilota istnieje tylko per-repo (`rtk init --copilot` nie ma trybu globalnego),
  # a bootstrap nadpisuje copilot-instructions.md — więc hook idzie z kita, nie z `rtk init`.
  # No-op bez `rtk` w PATH: hook nie odpali, Copilot przepuszcza komendę bez zmian.
  if [[ -f "$KIT_ROOT/templates/vscode/github/hooks/rtk-rewrite.json" ]]; then
    mkdir -p "$TARGET/.github/hooks"
    cp "$KIT_ROOT/templates/vscode/github/hooks/rtk-rewrite.json" \
      "$TARGET/.github/hooks/rtk-rewrite.json"
    echo "  + .github/hooks/rtk-rewrite.json (rtk hook copilot)"
  fi
  render_agent_commands vscode "$TARGET/.github/prompts"
  copy_shared_skills vscode "$TARGET/.github/prompts"
}

install_kiro() {
  mkdir -p "$TARGET/.kiro/settings" "$TARGET/.kiro/steering"
  fill_mcp "$KIT_ROOT/templates/kiro/settings/mcp.json" "$TARGET/.kiro/settings/mcp.json"
  echo "  + .kiro/settings/mcp.json"
  if [[ -f "$KIT_ROOT/templates/kiro/steering/instruction-kit.md" ]]; then
    copy_prefixed kiro "$KIT_ROOT/templates/kiro/steering/instruction-kit.md" \
      "$TARGET/.kiro/steering/instruction-kit.md"
  fi
  copy_shared_agents "$TARGET/.kiro/agents" kiro
  copy_shared_skills kiro "$TARGET/.kiro/agents"
}

install_kilo() {
  mkdir -p "$TARGET/.kilocode"
  fill_mcp "$KIT_ROOT/templates/kilo/mcp.json" "$TARGET/.kilocode/mcp.json"
  echo "  + .kilocode/mcp.json"
  render_agent_commands kilo "$TARGET/.kilocode/workflows"
  copy_shared_skills kilo "$TARGET/.kilocode/workflows"
}

install_antigravity() {
  mkdir -p "$TARGET/.agents"
  fill_mcp "$KIT_ROOT/templates/antigravity/mcp_config.json" "$TARGET/.agents/mcp_config.json"
  echo "  + .agents/mcp_config.json"
  # Guardy kita przed każdym narzędziem Antigravity: workspace'owy `.agents/hooks.json`
  # (nazwany hook `kit-guards`, PreToolUse) woła invoke-hook.js --to antigravity.
  # Plik dzielimy z użytkownikiem — scalamy wyłącznie klucz kita (`kit-guards`).
  install_guards "$TARGET/.agents/hooks" antigravity
  "$PYTHON_BIN" "$KIT_ROOT/scripts/antigravity_hooks.py" install \
    "$TARGET/.agents/hooks.json" "$KIT_ROOT/templates/antigravity/hooks.json"
  echo "  + .agents/hooks/ + .agents/hooks.json (guardy kita, PreToolUse)"
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    # agy (Antigravity CLI) nie zna workflow — tylko skille .agents/skills/<nazwa>/SKILL.md.
    "$PYTHON_BIN" "$KIT_ROOT/scripts/install_agent_skills.py" "$SHARED_AGENTS" "$TARGET/.agents/skills" antigravity
    echo "  + .agents/skills/ (agenty jako skille Antigravity)"
    # Workflow ze starszych wersji kita — po nazwie, cudze zostają.
    for name in "$ALL_AGENTS"/*.md; do
      kit_rm ".agents/workflows/$(basename "$name")"
    done
  fi
  copy_shared_skills antigravity "$TARGET/.agents/skills"
}

# `model` z globalnego configu opencode, gdy projektowy `opencode.json` go nie ma (#167).
# Katalog jak w opencode: `$XDG_CONFIG_HOME` albo `<home>/.config` (home z Pythona — na
# Windows USERPROFILE, nie `$HOME` Git Basha); pliki `config.json`, `opencode.json`,
# `opencode.jsonc`, ostatni z `model` wygrywa. Własny `model` projektu wygrywa; brak
# configu, pola albo nieczytelny plik = brak pola, bez błędu.
inherit_opencode_model() {
  DEST="$TARGET/opencode.json" "$PYTHON_BIN" - <<'PY'
import json
import os
import re
from pathlib import Path

dest = Path(os.environ["DEST"])
STRING = r'("(?:\\.|[^"\\])*")'


def load_jsonc(text: str):
    # Komentarze `//` i `/* */` oraz przecinki końcowe — poza stringami.
    text = re.sub(STRING + r"|//[^\n]*|/\*.*?\*/", lambda m: m.group(1) or "", text, flags=re.S)
    text = re.sub(STRING + r"|,(\s*[}\]])", lambda m: m.group(1) or m.group(2), text)
    return json.loads(text)


try:
    text = dest.read_text(encoding="utf-8")
    project = json.loads(text)
except (OSError, ValueError):
    raise SystemExit(0)
if not isinstance(project, dict) or "model" in project:
    raise SystemExit(0)
config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
model, source = None, None
for name in ("config.json", "opencode.json", "opencode.jsonc"):
    try:
        value = load_jsonc((config_dir / name).read_text(encoding="utf-8-sig")).get("model")
    except (OSError, ValueError, AttributeError):
        continue
    if isinstance(value, str) and value:
        model, source = value, config_dir / name
if model is None:
    raise SystemExit(0)
# Wstawka zamiast json.dumps — układ pliku z fill_mcp (tablice w linii) zostaje.
line = f'  "model": {json.dumps(model, ensure_ascii=False)},\n'
updated = re.sub(r"\A\{[ \t]*\n", lambda m: m.group(0) + line, text, count=1)
try:
    ok = json.loads(updated).get("model") == model
except ValueError:
    ok = False
if not ok:
    updated = json.dumps({"model": model, **project}, indent=2, ensure_ascii=False) + "\n"
dest.write_text(updated, encoding="utf-8", newline="\n")
print(f"  + opencode.json: model {model} (z {source})")
PY
}

install_opencode() {
  mkdir -p "$TARGET/.opencode"
  fill_mcp "$KIT_ROOT/templates/opencode/opencode.json" "$TARGET/opencode.json" "$WORKSPACE_PATH"
  echo "  + opencode.json"
  inherit_opencode_model
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    # Komendy kitu od #527 to plugin commands-dir: `.opencode/commands/kit-ai/` +
    # `/kit-ai:<nazwa>`. Stare `.opencode/command/<nazwa>.md` z poprzednich wersji znikają.
    prune_legacy_opencode_commands
  fi
  render_agent_commands opencode "$TARGET/.opencode/commands/kit-ai"
  apply_model_tiers opencode "$TARGET/.opencode/commands/kit-ai"
  copy_shared_skills opencode "$TARGET/.opencode/commands/kit-ai"
  # /kit-ai/goal i /kit-ai/loop (#567) — pętlę prowadzi plugin kit-loop.js, który rozpoznaje te formy.
  mkdir -p "$TARGET/.opencode/commands/kit-ai" "$TARGET/.opencode/plugins"
  cp "$KIT_ROOT/templates/opencode/commands/kit-ai/"*.md "$TARGET/.opencode/commands/kit-ai/"
  cp "$KIT_ROOT/templates/opencode/plugins/kit-loop.js" "$TARGET/.opencode/plugins/kit-loop.js"
  echo "  + .opencode/commands/kit-ai/ (komendy kitu, w tym goal i loop) + .opencode/plugins/kit-loop.js"
  # Guardy kita (git-guard, sensitive-files-guard) przed każdym narzędziem — plugin woła
  # adapter `invoke-hook.js --to opencode`, deny działa także przy `allow` w permission.
  install_guards "$TARGET/.opencode/hooks" opencode
  cp "$KIT_ROOT/templates/opencode/plugins/kit-guards.js" "$TARGET/.opencode/plugins/kit-guards.js"
  echo "  + .opencode/plugins/kit-guards.js + .opencode/hooks/ (guardy kita)"
}

install_plugins() {
  echo ""
  echo "== --with-plugins =="
  if command -v npx >/dev/null 2>&1; then
    echo "  -> mattpocock/skills (npx skills@latest add mattpocock/skills)"
    (cd "$TARGET" && npx --yes skills@latest add mattpocock/skills) || \
      echo "  ! npx skills add nie powiodło się — doinstaluj ręcznie w $TARGET" >&2
  else
    echo "  ! brak npx w PATH — pomiń mattpocock/skills albo zainstaluj Node.js, potem ręcznie:" >&2
    echo "      cd $TARGET && npx skills@latest add mattpocock/skills" >&2
  fi
  cat <<'EOF'
  -> Superpowers (Claude Code plugin marketplace) — bez CLI, ręcznie w Claude Code:
       /plugin marketplace add obra/superpowers-marketplace
       /plugin install superpowers@superpowers-marketplace
  -> Autopilot (Cursor) — ręcznie w Cursor: Settings → Extensions/Skills → Autopilot.
  Te trzy to zewnętrzne ekosystemy pluginów (Claude/Cursor), nie ten kit — zob. dokumentację kita
  „Narzędzia zewnętrzne”.
EOF
}

# Sekcja kita w .gitignore — wycięta razem z pustą linią, którą dokłada sync.
# Plik, w którym poza sekcją nic nie było, znika.
strip_gitignore_section() {
  [[ -f "$TARGET/.gitignore" ]] || return 0
  BEGIN_MARK="$GITIGNORE_BEGIN" END_MARK="$GITIGNORE_END" DEST="$TARGET/.gitignore" \
    "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

begin, end = os.environ["BEGIN_MARK"], os.environ["END_MARK"]
dest = Path(os.environ["DEST"])
text = dest.read_text(encoding="utf-8")
if begin in text and end in text:
    head, _, rest = text.partition(begin)
    _, _, tail = rest.partition(end)
    kept = (head.rstrip("\n") + "\n" if head.strip() else "") + tail.lstrip("\n")
    if kept.strip():
        dest.write_text(kept, encoding="utf-8", newline="\n")
        print("  - .gitignore (sekcja instruction-kit)")
    else:
        dest.unlink()
        print("  - .gitignore")
PY
}

# `--remove`: repo ma wyglądać jak przed kitem — poza plikami z treścią użytkownika.
# Kit nie robi kopii, więc niczego nie przywraca; usuwa tylko to, co sam położył.
remove_kit() {
  local id
  echo "Usuwanie instruction-kit → $TARGET"
  # Kontrakt Matta i indeks standardów — tylko gdy to nietknięty render kita (#241).
  # Przed porównaniem AGENTS.md z szablonem: zdejmujemy blok `## Agent skills`, żeby
  # plik utworzony przez kit znów był identyczny z szablonem. Przed prune_client,
  # żeby porównanie z renderem widziało repo (ziarna, źródła indeksu) jak przy reloadzie.
  "$PYTHON_BIN" "$KIT_ROOT/scripts/matt_contract.py" "$TARGET" "$KIT_ROOT" --remove
  for id in cursor claude codex vscode kiro kilo antigravity opencode; do
    prune_client "$id"
  done
  # Pliki tworzone raz: tylko gdy identyczne z szablonem — zmienione należą do użytkownika.
  # AGENTS.md niesie brief z Profilu (#307), więc nie `cmp`: nietknięty = render szablonu
  # z dowolną treścią bloku `kit:brief` (ta sama reguła co BUGBOT.md).
  if [[ -f "$TARGET/AGENTS.md" ]] && agents_pristine; then
    kit_rm AGENTS.md
  fi
  if bugbot_pristine "$TARGET/BUGBOT.md"; then
    kit_rm BUGBOT.md
  fi
  if [[ -f "$TARGET/.gitattributes" ]] \
     && cmp -s "$TARGET/.gitattributes" "$KIT_ROOT/templates/gitattributes.txt"; then
    kit_rm .gitattributes
  fi
  strip_gitignore_section
  kit_rm .ai/project.profile.yaml
  kit_rm .ai/.kit-bootstrap.json
  kit_rm .ai/.kit-doctor.json
  kit_rm .ai/headless.mjs
  kit_rm .ai/worktree.mjs
  kit_rm .ai/worktree.json
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_worktree.py" \
    --remove-hook "$TARGET" || true
  PYTHONPATH="$KIT_ROOT/src" "$PYTHON_BIN" "$KIT_ROOT/scripts/render_integrations.py" \
    --remove "$TARGET" "$TARGET/.ai/project.profile.yaml" "$KIT_ROOT" || true
  kit_rm .ai/night-run-watchdog.sh
  kit_rm .ai/night-run-t3.md
  kit_rm "$DESIGN_HANDOFF"
  echo ""
  echo "Gotowe. Zostały: .ai/project.md, CONTEXT.md, docs/adr/ i pliki zmienione przez Ciebie."
}

if [[ "$REMOVE" -eq 1 ]]; then
  remove_kit
  exit 0
fi

echo "Bootstrap instruction-kit → $TARGET"
echo "  language=$LANGUAGE"
echo "  clients=$CLIENTS_ARG"
echo "  from=$FROM_SRC"

mkdir -p "$TARGET/.ai"
# Profil przed wszystkim innym — z niego biorą się Tiery (agenci, BUGBOT.md).
if [[ ! -f "$TARGET/.ai/project.profile.yaml" ]]; then
  TMP_PROFILE="$(mktemp)"
  trap 'rm -f "$TMP_PROFILE"' EXIT
  copy_prefixed shared "$KIT_ROOT/templates/project.profile.yaml" "$TMP_PROFILE"
  sed -e "s/^name: my-project$/name: $(basename "$TARGET")/" \
    -e "s/^language: .*/language: $LANGUAGE/" \
    -e "s/^clients: .*/clients: $CLIENTS_ARG/" \
    "$TMP_PROFILE" > "$TARGET/.ai/project.profile.yaml"
  rm -f "$TMP_PROFILE"
  trap - EXIT
  echo "  + .ai/project.profile.yaml (Tiery: backend/web/mobile = none — wybierz Stacki)"
fi

if [[ "$SKIP_AGENTS" -eq 0 ]]; then
  # Blok `agents:` (model tiers, #168) — walidacja i dopisanie agentów kita przed renderem.
  "$PYTHON_BIN" "$KIT_ROOT/scripts/model_tiers.py" sync "$TARGET/.ai/project.profile.yaml" "$SHARED_AGENTS"
fi
PROFILE_TIERS="$(profile_tiers)"
HEADLESS=0
if headless_enabled; then HEADLESS=1; fi
STAGED_AGENTS="$(mktemp -d)"
BRIEF_FILE="$(mktemp)"
BRIEF_RULES_FILE="$(mktemp)"
trap 'rm -rf "$STAGED_AGENTS" "$BRIEF_FILE" "$BRIEF_RULES_FILE"' EXIT
SKIPPED_AGENTS="$(stage_shared_agents "$STAGED_AGENTS")"
# Python na Windowsie kończy linie `\r\n` — `\r` przykleja się do nazwy i `rm -f` chybia.
SKIPPED_AGENTS="${SKIPPED_AGENTS//$'\r'/}"
SHARED_AGENTS="$STAGED_AGENTS"
echo "  tiers=${PROFILE_TIERS:-brak} (agenci Tierów: backend → *-backend, client → *-frontend, review-ui)"

# Brief to dodatek: błąd renderowania (uszkodzony Profil, manifest) nie zatrzymuje instalacji.
render_project_brief > "$BRIEF_FILE" || { echo "  ! brief nie wyrenderowany" >&2; : > "$BRIEF_FILE"; }
render_brief_rules > "$BRIEF_RULES_FILE" || { echo "  ! reguły briefu nie wyrenderowane" >&2; : > "$BRIEF_RULES_FILE"; }
install_agenty_md_once
install_bugbot_md_once
prune_tier_agents

if [[ "$PRUNE_CLIENTS" -eq 1 ]]; then
  prune_unselected_clients
  echo "  (sprzątnięto kitowe pliki klientów spoza --clients ${CLIENTS_ARG}; wyłącz: --keep-unselected-clients)"
fi

for c in "${CLIENTS_LIST[@]}"; do
  case "$c" in
    cursor) install_cursor ;;
    claude) install_claude ;;
    codex) install_codex ;;
    vscode) install_vscode ;;
    kiro) install_kiro ;;
    kilo) install_kilo ;;
    antigravity) install_antigravity ;;
    opencode) install_opencode ;;
    *)
      echo "Nieobsługiwany klient po expand: $c" >&2
      exit 1
      ;;
  esac
done

install_headless
install_night_run_watchdog
install_night_run_t3
install_design_handoff

if [[ "$WITH_OVERLAY" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.md" ]]; then
    copy_prefixed shared "$KIT_ROOT/templates/project.md" "$TARGET/.ai/project.md"
    echo "  + .ai/project.md"
  fi
fi

# Po overlay: CODING_STANDARDS.md wymienia tylko źródła, które naprawdę są w repo.
install_matt_contract

sync_gitignore_section

# Końce linii: bez `* ... eol=lf` Windows z core.autocrlf=true trzyma CRLF na dysku
# i ten sam branch jest czysty na Linuksie, a "zmieniony" na Windowsie.
# Własnego .gitattributes projektu nie ruszamy — tylko ostrzeżenie.
if [[ ! -f "$TARGET/.gitattributes" ]]; then
  cp "$KIT_ROOT/templates/gitattributes.txt" "$TARGET/.gitattributes"
  echo "  + .gitattributes (LF, CRLF tylko dla .bat/.cmd/.ps1)"
elif ! grep -qE '^\*[[:space:]].*eol=lf' "$TARGET/.gitattributes"; then
  echo "  ! .gitattributes bez reguły LF — dopisz na górze: * text=auto eol=lf" >&2
fi

if [[ "$WITH_PLUGINS" -eq 1 ]]; then
  install_plugins
fi

# Stamp — commit kita w momencie bootstrapu, do taniego "czy trzeba re-bootstrapować"
# (MCP tool check_kit_status). Pusty kit_commit gdy --from to zdalny URL / nie-git.
# Z koła (`uv tool install git+…`) nie ma `.git` — commit podaje `kit-ai` z metadanych
# instalacji (KIT_COMMIT). Bez `.git` nie pytamy gita: `_data` w `.venv` repo aplikacji
# zwróciłoby HEAD aplikacji, nie kita.
if [[ -e "$KIT_ROOT/.git" ]]; then
  KIT_COMMIT="$(git -C "$KIT_ROOT" rev-parse HEAD 2>/dev/null || true)"
else
  KIT_COMMIT="${KIT_COMMIT:-}"
fi
BOOTSTRAPPED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$TARGET/.ai"
cat > "$TARGET/.ai/.kit-bootstrap.json" <<JSON
{
  "kit_commit": "${KIT_COMMIT}",
  "kit_from": "${FROM_SRC}",
  "kit_version": "${KIT_VERSION:-}",
  "bootstrapped_at": "${BOOTSTRAPPED_AT}",
  "language": "${LANGUAGE}",
  "clients": "${CLIENTS_ARG}"
}
JSON
echo "  + .ai/.kit-bootstrap.json (stamp dla check_kit_status)"

install_worktree
install_integrations

warn_tracked_machine_files

echo ""
echo "Gotowe. Zrestartuj IDE w $TARGET."
echo "Clients: ${CLIENTS_ARG}"
echo "Slash: /kit-ai:git-start, /kit-ai:git-check, /kit-ai:git-commit, /kit-ai:git-end, /kit-ai:review-*, /kit-ai:subagent-*, /kit-ai:teacher-*"
if client_enabled cursor; then
  echo "Slash (Cursor): /compact (= Summarize; nie dla Claude/Codex)"
fi
echo "MCP: --language ${LANGUAGE} --clients ${CLIENTS_ARG} --workspace …"
