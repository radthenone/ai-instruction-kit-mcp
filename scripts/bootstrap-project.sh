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

usage() {
  cat <<'EOF'
Użycie: bootstrap-project.sh TARGET_DIR [opcje]

Opcje:
  --language LANG     Język prozy instrukcji: pl|en (domyślnie: pl). Tytuły issue/PR zawsze EN
  --clients LIST      all | cursor | claude | codex | vscode | kiro | kilo | antigravity | opencode
                      (lista po przecinku; alias: copilot→vscode). Domyślnie: all
  --from SOURCE       Źródło uvx: ścieżka lokalna lub git+https://… (domyślnie: placeholder GitHub)
  --with-overlay      Skopiuj templates/project.md → .ai/project.md (jeśli brak)
  --skip-agents       Nie kopiuj agentów (/git-*, /review-*, /subagent-*) ani skilli
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

if [[ -d "$FROM_SRC" ]]; then
  FROM_SRC="$(cd "$FROM_SRC" && pwd)"
fi

# python3 (Linux/macOS) albo python (Windows / pyenv) — bez twardego `python`.
# `kit-ai` / serwer MCP podają własny interpreter (KIT_PYTHON): przy instalacji z koła
# (`uv tool install`) tylko on widzi pakiet `guides` — klonu z `src/` nie ma.
if [[ -n "${KIT_PYTHON:-}" ]]; then
  PYTHON_BIN="$KIT_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Brak interpretera Python (python3 lub python) w PATH" >&2
  exit 1
fi

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
# `claude_settings.py prune`.
kit_files() {
  local id="$1" sandbox
  sandbox="$(mktemp -d)"
  if ! ( TARGET="$sandbox" SHARED_AGENTS="$ALL_AGENTS" SKIP_AGENTS=0; "install_$id" ) >/dev/null 2>&1; then
    rm -rf "$sandbox"
    echo "Nie udało się ustalić plików kita klienta $id" >&2
    return 1
  fi
  (cd "$sandbox" && find . -type f ! -path ./.claude/settings.json | sed 's|^\./||' | sort)
  rm -rf "$sandbox"
}

# Usuń jeden plik kita (ścieżka względem $TARGET) i puste katalogi nad nim, aż do $TARGET.
# Cudzy plik w tym samym katalogu blokuje rmdir, więc katalog zostaje razem z nim.
kit_rm() {
  local rel="$1" dir
  [[ -e "$TARGET/$rel" || -L "$TARGET/$rel" ]] || return 0
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
      ;;
  esac
  if [[ "$id" == "claude" && -f "$TARGET/.claude/settings.json" ]]; then
    "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" prune "$TARGET/.claude/settings.json"
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
# `project-guides`, resztę zostawiamy. Pliku, którego nie umiemy sparsować (JSONC
# z komentarzami, uszkodzony JSON/TOML), nie scalamy: oryginał idzie do `.bak`.
KIT_SERVER = "project-guides"


def merge_json(old_text):
    old = json.loads(old_text)
    new = json.loads(text)
    key = next(k for k in ("mcpServers", "servers", "mcp") if k in new)
    if not isinstance(old, dict) or not isinstance(old.get(key, {}), dict):
        raise ValueError(f"`{key}` nie jest obiektem")
    merged = json.loads(json.dumps(old))
    for k, v in new.items():
        if k != key:
            merged.setdefault(k, v)
    merged.setdefault(key, {})[KIT_SERVER] = new[key][KIT_SERVER]
    if merged == old:
        return old_text
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


TOML_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def toml_kit_span(lines):
    """Zakres linii tabeli `[mcp_servers.project-guides]` (z podtabelami) albo None."""
    start = None
    for i, line in enumerate(lines):
        m = TOML_HEADER.match(line)
        if not m:
            continue
        name = m.group(1).replace('"', "")
        is_kit = name == f"mcp_servers.{KIT_SERVER}" or name.startswith(f"mcp_servers.{KIT_SERVER}.")
        if start is None and is_kit:
            start = i
        elif start is not None and not is_kit:
            return start, i
    return None if start is None else (start, len(lines))


def merge_toml(old_text):
    try:
        import tomllib
    except ImportError:  # Python < 3.11: walidacja niedostępna, scalamy tekstowo
        tomllib = None
    if tomllib:
        tomllib.loads(old_text)
    new_lines = text.splitlines(keepends=True)
    s, e = toml_kit_span(new_lines)
    kit_block = new_lines[s:e]
    old_lines = old_text.splitlines(keepends=True)
    span = toml_kit_span(old_lines)
    if span is None:
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        sep = ["\n"] if old_lines and old_lines[-1].strip() else []
        merged = old_lines + sep + kit_block
    else:
        merged = old_lines[: span[0]] + kit_block + old_lines[span[1] :]
    return "".join(merged)


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
)

sync_gitignore_section() {
  local target_file="$TARGET/.gitignore"
  local template="$KIT_ROOT/templates/gitignore-kit.txt"
  [[ -f "$template" ]] || return 0

  BEGIN_MARK="$GITIGNORE_BEGIN" END_MARK="$GITIGNORE_END" \
  SHARED_SKILLS="$SHARED_SKILLS" CURSOR_SKILLS="$KIT_ROOT/templates/cursor/skills" \
  MACHINE_FILES="$(printf '%s\n' "${MACHINE_FILES[@]#/}")" \
  TEMPLATE="$template" DEST="$target_file" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

begin = os.environ["BEGIN_MARK"]
end = os.environ["END_MARK"]
dest = Path(os.environ["DEST"])
body = Path(os.environ["TEMPLATE"]).read_text(encoding="utf-8").strip("\n")


def skill_allow(dest_prefix: str, *source_dirs: str) -> str:
    """Wyjątki `!` dla skilli kita — po nazwie, żeby nie wciągnąć cudzych.

    Katalog skilli u konsumenta miesza dwa źródła: te z kita (pliki) i dowiązania do
    `.agents/skills/` z `npx skills add` (ignorowane). Wersjonujemy tylko pierwsze.
    """
    names: list[str] = []
    for source in source_dirs:
        root = Path(source)
        if not root.is_dir():
            continue
        names.extend(sorted(p.name for p in root.iterdir() if p.is_dir()))
    lines: list[str] = []
    for name in sorted(set(names)):
        lines.append(f"!{dest_prefix}/{name}/")
        lines.append(f"!{dest_prefix}/{name}/**")
    return "\n".join(lines) if lines else f"# (kit nie dostarcza skilli dla {dest_prefix})"


shared = os.environ["SHARED_SKILLS"]
body = body.replace("@KIT_SKILLS_CLAUDE@", skill_allow(".claude/skills", shared))
body = body.replace(
    "@KIT_SKILLS_CURSOR@",
    skill_allow(".cursor/skills", shared, os.environ["CURSOR_SKILLS"]),
)
# Wiodący `/` doklejamy dopiero tutaj: w env Git Bash (MSYS) zamieniłby pierwszą
# linię `/.mcp.json` na `C:/Program Files/Git/.mcp.json`.
machine_files = "\n".join("/" + line for line in os.environ["MACHINE_FILES"].splitlines())
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
# (`backend` / `client` = web lub mobile). Staging w katalogu tymczasowym, bez linii
# `tier:` — wszystkie instalatory niżej czytają już przefiltrowany zestaw. Na stdout:
# nazwy pominiętych agentów (do sprzątnięcia z poprzedniego Bootstrapu).
stage_shared_agents() {
  local dest="$1"
  SRC="$SHARED_AGENTS" DEST="$dest" TIERS="$PROFILE_TIERS" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

chosen = set(os.environ["TIERS"].split())
dest = Path(os.environ["DEST"])
for src in sorted(Path(os.environ["SRC"]).glob("*.md")):
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    tier = next(
        (line.partition(":")[2].strip() for line in lines[1:end] if line.startswith("tier:")),
        None,
    )
    if tier and tier not in chosen:
        print(src.stem)
        continue
    kept = [line for i, line in enumerate(lines) if not (0 < i < end and line.startswith("tier:"))]
    (dest / src.name).write_text("".join(kept), encoding="utf-8", newline="\n")
PY
}

# Pliki agentów pominiętych przez Tier — po nazwie, we wszystkich formatach klientów
# (mapa 1:1 z copy_shared_agents / copy_claude_commands / install_codex_agents /
# render_agent_commands). Tier zmieniony na `none` = agenci znikają przy reload.
prune_tier_agents() {
  local name
  for name in $SKIPPED_AGENTS; do
    rm -f "$TARGET/.claude/agents/$name.md" "$TARGET/.claude/commands/$name.md" \
      "$TARGET/.cursor/agents/$name.md" "$TARGET/.kiro/agents/$name.md" \
      "$TARGET/.github/prompts/$name.prompt.md" "$TARGET/.kilocode/workflows/$name.md" \
      "$TARGET/.agents/workflows/$name.md" "$TARGET/.opencode/command/$name.md"
    rm -rf "$TARGET/.codex/skills/$name"
  done
}

# Sekcje `<!-- tier:X -->…<!-- /tier:X -->` w BUGBOT.md zostają tylko dla wybranych Tierów.
# Plik nadpisywany, gdy go brak albo gdy to nietknięty render kita (dowolny zestaw Tierów)
# — zmiana Tierów + reload odświeża sekcje, a ręcznie dostosowany BUGBOT.md zostaje.
# Na stdout: ścieżka, gdy plik powstał od zera.
copy_bugbot_md() {
  SRC="$KIT_ROOT/templates/cursor/BUGBOT.md" DEST="$1" TIERS="$PROFILE_TIERS" "$PYTHON_BIN" - <<'PY'
import os
import re
from pathlib import Path

source = Path(os.environ["SRC"]).read_text(encoding="utf-8")
dest = Path(os.environ["DEST"])


def render(chosen: set[str]) -> str:
    def keep(match: re.Match) -> str:
        return match.group(2).strip("\n") + "\n" if match.group(1) in chosen else ""

    text = re.sub(r"<!-- tier:(\w+) -->\n(.*?)<!-- /tier:\1 -->\n?", keep, source, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text)


pristine = dest.is_file() and dest.read_text(encoding="utf-8") in {
    render(c) for c in (set(), {"backend"}, {"client"}, {"backend", "client"})
}
if os.environ.get("CHECK_ONLY"):
    raise SystemExit(0 if pristine else 1)
if dest.is_file() and not pristine:
    raise SystemExit(0)
if not dest.is_file():
    print(dest)
dest.write_text(render(set(os.environ["TIERS"].split())), encoding="utf-8", newline="\n")
PY
}

# Exit 0, gdy plik to nietknięty render BUGBOT.md kita — wtedy wolno go usunąć.
bugbot_pristine() {
  CHECK_ONLY=1 copy_bugbot_md "$1" >/dev/null
}

copy_shared_agents() {
  local dest_dir="$1"
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    return 0
  fi
  if [[ ! -d "$SHARED_AGENTS" ]]; then
    echo "Brak $SHARED_AGENTS — nie skopiowano agentów" >&2
    exit 1
  fi
  mkdir -p "$dest_dir"
  cp "$SHARED_AGENTS/"*.md "$dest_dir/"
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

install_agenty_md_once() {
  if [[ ! -f "$TARGET/AGENTS.md" ]]; then
    cp "$KIT_ROOT/templates/AGENTS.md" "$TARGET/AGENTS.md"
    echo "  + AGENTS.md"
  fi
}

# BUGBOT.md w root — niezależnie od --clients, bo /review-bugbot (manualny odpowiednik)
# ma działać dla WSZYSTKICH klientów (Claude, Codex, VS Code…), nie tylko Cursor.
# .cursor/BUGBOT.md (install_cursor) zostaje osobno — to dla natywnej usługi Cursor
# BugBot, która czyta z tamtej ścieżki; ta funkcja to nie duplikat, to inny konsument.
install_bugbot_md_once() {
  if [[ -n "$(copy_bugbot_md "$TARGET/BUGBOT.md")" ]]; then
    echo "  + BUGBOT.md (root — dla /review-bugbot wszystkich klientów)"
  fi
}

# Guardraile maja jedno zrodlo (templates/shared/guards) i trafiaja do katalogu
# hooków wybranego klienta. Kontrakt tlumaczy invoke-hook.js, wiec pliki sa te same.
install_guards() {
  local dest="$1"
  mkdir -p "$dest"
  # Guards v1 (gate-*) kasowane po nazwie — reinstalacja na Workspace sprzed v2
  # ma zostawic wylacznie nowy zestaw.
  rm -f "$dest/gate-destructive.sh" "$dest/gate-push.sh" "$dest/gate-file-writes.mjs"
  cp "$SHARED_GUARDS/git-guard.mjs" "$dest/git-guard.mjs"
  cp "$SHARED_GUARDS/sensitive-files-guard.mjs" "$dest/sensitive-files-guard.mjs"
  cp "$SHARED_GUARDS/invoke-hook.js" "$dest/invoke-hook.js"
}

install_cursor() {
  mkdir -p "$TARGET/.cursor/hooks" "$TARGET/.cursor/rules" "$TARGET/.ai"
  fill_mcp "$KIT_ROOT/templates/cursor/mcp.json" "$TARGET/.cursor/mcp.json"
  echo "  + .cursor/mcp.json"

  cp "$KIT_ROOT/templates/cursor/hooks.json" "$TARGET/.cursor/hooks.json"
  install_guards "$TARGET/.cursor/hooks"
  echo "  + .cursor/hooks.json (node invoke-hook → guardy .mjs)"

  cp "$KIT_ROOT/templates/cursor/rules/use-guides.mdc" "$TARGET/.cursor/rules/use-guides.mdc"
  cp "$KIT_ROOT/templates/cursor/rules/code-review.mdc" "$TARGET/.cursor/rules/code-review.mdc"
  cp "$KIT_ROOT/templates/cursor/rules/git-branch-pr.mdc" "$TARGET/.cursor/rules/git-branch-pr.mdc"
  copy_bugbot_md "$TARGET/.cursor/BUGBOT.md" >/dev/null

  copy_shared_agents "$TARGET/.cursor/agents"

  if [[ -d "$KIT_ROOT/templates/cursor/skills" ]]; then
    mkdir -p "$TARGET/.cursor/skills"
    cp -R "$KIT_ROOT/templates/cursor/skills/." "$TARGET/.cursor/skills/"
    echo "  + .cursor/skills/ (Cursor-only, np. /compact)"
  fi

  copy_shared_skills cursor "$TARGET/.cursor/skills"
}

copy_claude_commands() {
  local dest_dir="$1"
  if [[ "$SKIP_AGENTS" -ne 0 ]]; then
    return 0
  fi
  if [[ ! -d "$SHARED_AGENTS" ]]; then
    echo "Brak $SHARED_AGENTS — nie skopiowano komend" >&2
    exit 1
  fi
  mkdir -p "$dest_dir"
  # Claude Code custom slash commands: bez literalnego $ARGUMENTS w treści, tekst po
  # `/nazwa ...` jest ignorowany (nie trafia do Claude). Wstrzykujemy go tu — tylko
  # w kopii dla Claude, źródło w shared/agents zostaje nietknięte (Cursor ma inny mechanizm).
  SHARED_AGENTS="$SHARED_AGENTS" DEST_DIR="$dest_dir" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

src_dir = Path(os.environ["SHARED_AGENTS"])
dest_dir = Path(os.environ["DEST_DIR"])

for src in sorted(src_dir.glob("*.md")):
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines[0].strip() == "---", f"{src}: brak frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    # `name:`/`readonly:` to pola formatu subagentów — command frontmatter ich nie zna.
    fm_lines = [
        l for l in lines[1:end]
        if not l.startswith("name:") and not l.startswith("readonly:")
    ]
    body = lines[end + 1:]
    while body and body[0].strip() == "":
        body.pop(0)

    out = "---\n" + "".join(fm_lines) + "argument-hint: [args]\n---\n\n"
    out += "Argumenty użytkownika (surowy tekst po komendzie): $ARGUMENTS\n\n"
    out += "".join(body)
    (dest_dir / src.name).write_text(out, encoding="utf-8", newline="\n")
PY
  echo "  + $dest_dir (Claude slash commands, \$ARGUMENTS wired)"
}

install_claude() {
  fill_mcp "$KIT_ROOT/templates/claude/mcp.json" "$TARGET/.mcp.json"
  echo "  + .mcp.json (Claude Code)"

  install_guards "$TARGET/.claude/hooks"
  # Tylko Claude Code: Cursor nie ma narzedzia Bash w tym sensie (bash-guard),
  # nie zwraca kontekstu z afterFileEdit (linters-guard) ani nie ma SessionStart.
  cp "$SHARED_GUARDS/bash-guard.mjs" "$TARGET/.claude/hooks/bash-guard.mjs"
  cp "$SHARED_GUARDS/linters-guard.mjs" "$TARGET/.claude/hooks/linters-guard.mjs"
  cp "$SHARED_GUARDS/rtk-check.mjs" "$TARGET/.claude/hooks/rtk-check.mjs"
  # settings.json nalezy do uzytkownika — scalamy tylko wpisy kita.
  "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" install     "$TARGET/.claude/settings.json" "$KIT_ROOT/templates/claude/settings.json"
  echo "  + .claude/hooks/ + wpisy hookow kita w .claude/settings.json"

  copy_shared_agents "$TARGET/.claude/agents"
  copy_claude_commands "$TARGET/.claude/commands"
  copy_shared_skills claude "$TARGET/.claude/skills"
}

# Agenci z templates/shared/agents/*.md → skille Codexa w .codex/skills/<nazwa>/.
# Codex nie ma formatu TOML-agentów od wycofania custom prompts; natywny format
# to katalog skilla z SKILL.md. Curated TOML-e z templates/codex/agents/ są
# przestarzałe — źródłem prawdy pozostaje templates/shared/agents/.
install_codex_agents() {
  "$PYTHON_BIN" "$KIT_ROOT/scripts/install_agent_skills.py" "$SHARED_AGENTS" "$TARGET/.codex/skills"
  echo "  + .codex/skills/ (agenty jako natywne skille Codexa)"
}

install_codex() {
  fill_mcp "$KIT_ROOT/templates/codex/config.toml" "$TARGET/.codex/config.toml" "$TARGET"
  echo "  + .codex/config.toml"
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
  "$PYTHON_BIN" "$KIT_ROOT/scripts/render_agent_commands.py" "$fmt" "$SHARED_AGENTS" "$dest_dir"
  echo "  + $dest_dir ($fmt slash commands)"
}

install_vscode() {
  mkdir -p "$TARGET/.vscode" "$TARGET/.github"
  fill_mcp "$KIT_ROOT/templates/vscode/mcp.json" "$TARGET/.vscode/mcp.json"
  echo "  + .vscode/mcp.json"
  if [[ -f "$KIT_ROOT/templates/vscode/github/copilot-instructions.md" ]]; then
    cp "$KIT_ROOT/templates/vscode/github/copilot-instructions.md" \
      "$TARGET/.github/copilot-instructions.md"
    echo "  + .github/copilot-instructions.md"
  fi
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
    cp "$KIT_ROOT/templates/kiro/steering/instruction-kit.md" \
      "$TARGET/.kiro/steering/instruction-kit.md"
  fi
  copy_shared_agents "$TARGET/.kiro/agents"
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
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    # agy (Antigravity CLI) nie zna workflow — tylko skille .agents/skills/<nazwa>/SKILL.md.
    "$PYTHON_BIN" "$KIT_ROOT/scripts/install_agent_skills.py" "$SHARED_AGENTS" "$TARGET/.agents/skills"
    echo "  + .agents/skills/ (agenty jako skille Antigravity)"
    # Workflow ze starszych wersji kita — po nazwie, cudze zostają.
    for name in "$ALL_AGENTS"/*.md; do
      kit_rm ".agents/workflows/$(basename "$name")"
    done
  fi
  copy_shared_skills antigravity "$TARGET/.agents/skills"
}

install_opencode() {
  mkdir -p "$TARGET/.opencode"
  fill_mcp "$KIT_ROOT/templates/opencode/opencode.json" "$TARGET/opencode.json" "$TARGET"
  echo "  + opencode.json"
  render_agent_commands opencode "$TARGET/.opencode/command"
  copy_shared_skills opencode "$TARGET/.opencode/command"
  # /goal i /loop jak w Claude Code: komendy + plugin, który po session.execution.succeeded
  # wznawia turę (sam markdown kończy się z końcem tury).
  mkdir -p "$TARGET/.opencode/command" "$TARGET/.opencode/plugins"
  cp "$KIT_ROOT/templates/opencode/command/"*.md "$TARGET/.opencode/command/"
  cp "$KIT_ROOT/templates/opencode/plugins/kit-loop.js" "$TARGET/.opencode/plugins/kit-loop.js"
  echo "  + .opencode/command/{goal,loop}.md + .opencode/plugins/kit-loop.js"
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
  Te trzy to zewnętrzne ekosystemy pluginów (Claude/Cursor), nie ten kit — zob. README
  "Skills / pluginy zewnętrzne".
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
  for id in cursor claude codex vscode kiro kilo antigravity opencode; do
    prune_client "$id"
  done
  # Pliki tworzone raz: tylko gdy identyczne z szablonem — zmienione należą do użytkownika.
  if [[ -f "$TARGET/AGENTS.md" ]] && cmp -s "$TARGET/AGENTS.md" "$KIT_ROOT/templates/AGENTS.md"; then
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
  sed -e "s/^name: my-project$/name: $(basename "$TARGET")/" \
    -e "s/^language: .*/language: $LANGUAGE/" \
    -e "s/^clients: .*/clients: $CLIENTS_ARG/" \
    "$KIT_ROOT/templates/project.profile.yaml" > "$TARGET/.ai/project.profile.yaml"
  echo "  + .ai/project.profile.yaml (Tiery: backend/web/mobile = none — wybierz Stacki)"
fi

PROFILE_TIERS="$(profile_tiers)"
STAGED_AGENTS="$(mktemp -d)"
trap 'rm -rf "$STAGED_AGENTS"' EXIT
SKIPPED_AGENTS="$(stage_shared_agents "$STAGED_AGENTS")"
# Python na Windowsie kończy linie `\r\n` — `\r` przykleja się do nazwy i `rm -f` chybia.
SKIPPED_AGENTS="${SKIPPED_AGENTS//$'\r'/}"
SHARED_AGENTS="$STAGED_AGENTS"
echo "  tiers=${PROFILE_TIERS:-brak} (agenci Tierów: backend → *-backend, client → *-frontend, review-ui)"

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

if [[ "$WITH_OVERLAY" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.md" ]]; then
    cp "$KIT_ROOT/templates/project.md" "$TARGET/.ai/project.md"
    echo "  + .ai/project.md"
  fi
fi

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

warn_tracked_machine_files

echo ""
echo "Gotowe. Zrestartuj IDE w $TARGET."
echo "Clients: ${CLIENTS_ARG}"
echo "Slash: /git-start, /git-check, /git-commit, /git-end, /review-*, /subagent-*, /teacher-*"
if client_enabled cursor; then
  echo "Slash (Cursor): /compact (= Summarize; nie dla Claude/Codex)"
fi
echo "MCP: --language ${LANGUAGE} --clients ${CLIENTS_ARG} --workspace …"
