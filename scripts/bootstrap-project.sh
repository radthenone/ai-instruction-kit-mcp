#!/usr/bin/env bash
# Bootstrap instruction-kit w repo aplikacji (multi-client).
#
# Użycie:
#   ./scripts/bootstrap-project.sh /sciezka/do/projektu [--from PATH|URL] [--preset shop]
#   ./scripts/bootstrap-project.sh ../app --clients cursor
#   ./scripts/bootstrap-project.sh ../app --clients all
#
# Domyślny preset: _base. Domyślni klienci: all.
# Kategoria e-commerce: --preset shop
# Agenci: templates/shared/agents → natywne ścieżki klienta.

set -euo pipefail

usage() {
  cat <<'EOF'
Użycie: bootstrap-project.sh TARGET_DIR [opcje]

Opcje:
  --preset NAME       Kategoria z kita (domyślnie: _base). Przykład: shop
  --language LANG     Język prozy instrukcji: pl|en (domyślnie: pl). Tytuły issue/PR zawsze EN
  --codegen NAME      Generator klienta API: orval (schema → frontend/src/api/generated
                      + mutatory) | none (tool-agnostyczny/ręczny) | graphql (GraphQL zamiast
                      REST). Domyślnie: orval
  --clients LIST      all | cursor | claude | codex | vscode | kiro | kilo | antigravity | opencode
                      (lista po przecinku; alias: copilot→vscode). Domyślnie: all
  --from SOURCE       Źródło uvx: ścieżka lokalna lub git+https://… (domyślnie: placeholder GitHub)
  --with-profile      Skopiuj templates/project.profile.yaml → .ai/project.profile.yaml (tylko fork)
  --with-overlay      Skopiuj templates/project.md → .ai/project.md (jeśli brak)
  --skip-agents       Nie kopiuj agentów (/git-*, /review-*, /subagent-*)
  --with-plugins      Best-effort doinstaluj zewnętrzne pluginy (mattpocock skills przez npx;
                      Superpowers/Autopilot tylko instrukcja — to marketplace pluginów Claude/Cursor,
                      nie da się zainstalować z skryptu). Wymaga npx w PATH (Node.js)
  --keep-unselected-clients
                      Nie usuwaj plików klientów spoza --clients (domyślnie: sprzątane —
                      declarative sync, np. --clients claude usuwa .cursor/.codex/… kitowe pliki)
  -h, --help          Ta pomoc

Przykład (tylko Cursor):
  ./scripts/bootstrap-project.sh ../moj-projekt \
    --clients cursor \
    --from /m/projects/ai-instruction-kit-mcp \
    --with-overlay

Przykład (kategoria shop, wszyscy klienci):
  ./scripts/bootstrap-project.sh ../moj-sklep \
    --preset shop \
    --clients all \
    --from /m/projects/ai-instruction-kit-mcp
EOF
}

TARGET=""
PRESET="_base"
LANGUAGE="pl"
CODEGEN="orval"
CLIENTS_RAW="all"
FROM_SRC="git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git"
WITH_PROFILE=0
WITH_OVERLAY=0
SKIP_AGENTS=0
WITH_PLUGINS=0
PRUNE_CLIENTS=1

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_AGENTS="$KIT_ROOT/templates/shared/agents"
SHARED_GUARDS="$KIT_ROOT/templates/shared/guards"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) PRESET="${2:?}"; shift 2 ;;
    --language)
      LANGUAGE="$(echo "${2:?}" | tr '[:upper:]' '[:lower:]')"
      if [[ "$LANGUAGE" != "pl" && "$LANGUAGE" != "en" ]]; then
        echo "Nieprawidłowy --language: $LANGUAGE (dozwolone: pl, en)" >&2
        exit 1
      fi
      shift 2
      ;;
    --clients) CLIENTS_RAW="${2:?}"; shift 2 ;;
    --codegen)
      CODEGEN="$(echo "${2:?}" | tr '[:upper:]' '[:lower:]')"
      if [[ "$CODEGEN" != "orval" && "$CODEGEN" != "none" && "$CODEGEN" != "graphql" ]]; then
        echo "Nieprawidłowy --codegen: $CODEGEN (dozwolone: orval, none, graphql)" >&2
        exit 1
      fi
      shift 2
      ;;
    --from) FROM_SRC="${2:?}"; shift 2 ;;
    --with-profile) WITH_PROFILE=1; shift ;;
    --with-overlay) WITH_OVERLAY=1; shift ;;
    --skip-agents) SKIP_AGENTS=1; shift ;;
    --with-plugins) WITH_PLUGINS=1; shift ;;
    --keep-unselected-clients) PRUNE_CLIENTS=0; shift ;;
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
if command -v python3 >/dev/null 2>&1; then
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

CLIENTS_ARG="$(echo "$CLIENTS_PARSE" | head -n1 | tr -d '\r')"
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

# Usuwa TYLKO pliki/foldery, które ten sam bootstrap sam kiedyś wygenerował dla danego
# klienta (mapa 1:1 z install_*() niżej). Nigdy nie rusza sąsiednich plików tego samego
# katalogu spoza kita (np. .vscode/settings.json, .github/workflows/, .kilocode/rules/).
prune_client() {
  local id="$1"
  case "$id" in
    cursor)
      rm -f "$TARGET/.cursor/mcp.json" "$TARGET/.cursor/hooks.json" \
        "$TARGET/.cursor/hooks/gate-push.sh" "$TARGET/.cursor/hooks/gate-destructive.sh" \
        "$TARGET/.cursor/hooks/invoke-hook.js" \
        "$TARGET/.cursor/rules/use-guides.mdc" "$TARGET/.cursor/rules/code-review.mdc" \
        "$TARGET/.cursor/rules/git-branch-pr.mdc" "$TARGET/.cursor/BUGBOT.md"
      rm -rf "$TARGET/.cursor/agents" "$TARGET/.cursor/skills"
      rmdir "$TARGET/.cursor/hooks" "$TARGET/.cursor/rules" "$TARGET/.cursor" 2>/dev/null || true
      ;;
    claude)
      rm -f "$TARGET/.mcp.json"
      rm -rf "$TARGET/.claude/agents" "$TARGET/.claude/commands" "$TARGET/.claude/hooks"
      if [[ -f "$TARGET/.claude/settings.json" ]]; then
        "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" prune "$TARGET/.claude/settings.json"
      fi
      rmdir "$TARGET/.claude" 2>/dev/null || true
      ;;
    codex)
      rm -f "$TARGET/.codex/config.toml"
      rm -rf "$TARGET/.codex/agents"
      rmdir "$TARGET/.codex" 2>/dev/null || true
      ;;
    vscode)
      rm -f "$TARGET/.vscode/mcp.json" "$TARGET/.github/copilot-instructions.md"
      if [[ -d "$TARGET/.github/prompts" ]]; then
        rm -f "$TARGET/.github/prompts/"*.prompt.md 2>/dev/null || true
        rmdir "$TARGET/.github/prompts" 2>/dev/null || true
      fi
      rmdir "$TARGET/.vscode" 2>/dev/null || true
      ;;
    kiro)
      rm -f "$TARGET/.kiro/settings/mcp.json" "$TARGET/.kiro/steering/instruction-kit.md"
      rm -rf "$TARGET/.kiro/agents"
      rmdir "$TARGET/.kiro/settings" "$TARGET/.kiro/steering" "$TARGET/.kiro" 2>/dev/null || true
      ;;
    kilo)
      rm -f "$TARGET/.kilocode/mcp.json"
      rm -rf "$TARGET/.kilocode/workflows"
      rmdir "$TARGET/.kilocode" 2>/dev/null || true
      ;;
    antigravity)
      rm -f "$TARGET/.agents/mcp_config.json"
      rm -rf "$TARGET/.agents/workflows"
      rmdir "$TARGET/.agents" 2>/dev/null || true
      ;;
    opencode)
      rm -f "$TARGET/opencode.json"
      rm -rf "$TARGET/.opencode"
      ;;
  esac
}

prune_unselected_clients() {
  local id
  for id in cursor claude codex vscode kiro kilo antigravity opencode; do
    if ! client_enabled "$id"; then
      prune_client "$id"
    fi
  done
}

# Wypełnij szablon MCP (JSON/TOML): from, preset, language, clients, opcjonalnie workspace.
fill_mcp() {
  local src="$1" dest="$2" workspace_repl="${3:-}"
  mkdir -p "$(dirname "$dest")"
  FROM_SRC="$FROM_SRC" PRESET="$PRESET" LANGUAGE="$LANGUAGE" CODEGEN="$CODEGEN" \
  CLIENTS_ARG="$CLIENTS_ARG" \
  WORKSPACE_REPL="$workspace_repl" SRC="$src" DEST="$dest" "$PYTHON_BIN" - <<'PY'
import os
import re
from pathlib import Path

src = Path(os.environ["SRC"])
dest = Path(os.environ["DEST"])
text = src.read_text(encoding="utf-8")
text = text.replace(
    "git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git",
    os.environ["FROM_SRC"],
)
text = re.sub(
    r'("--preset",\s*")[^"]*(")',
    rf'\g<1>{os.environ["PRESET"]}\2',
    text,
)
text = re.sub(
    r'("--language",\s*")[^"]*(")',
    rf'\g<1>{os.environ["LANGUAGE"]}\2',
    text,
)
text = re.sub(
    r'("--codegen",\s*")[^"]*(")',
    rf'\g<1>{os.environ["CODEGEN"]}\2',
    text,
)
text = re.sub(
    r'("--clients",\s*")[^"]*(")',
    rf'\g<1>{os.environ["CLIENTS_ARG"]}\2',
    text,
)
# TOML: "--preset", "_base" style already covered; also bare strings in toml lists
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
dest.write_text(text, encoding="utf-8")
PY
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
  if [[ ! -f "$TARGET/BUGBOT.md" ]]; then
    cp "$KIT_ROOT/templates/cursor/BUGBOT.md" "$TARGET/BUGBOT.md"
    echo "  + BUGBOT.md (root — dla /review-bugbot wszystkich klientów)"
  fi
}

# Guardraile maja jedno zrodlo (templates/shared/guards) i trafiaja do katalogu
# hooków wybranego klienta. Kontrakt tlumaczy invoke-hook.js, wiec pliki sa te same.
install_guards() {
  local dest="$1"
  mkdir -p "$dest"
  cp "$SHARED_GUARDS/gate-destructive.sh" "$dest/gate-destructive.sh"
  cp "$SHARED_GUARDS/gate-push.sh" "$dest/gate-push.sh"
  cp "$SHARED_GUARDS/invoke-hook.js" "$dest/invoke-hook.js"
  chmod +x "$dest/gate-destructive.sh" "$dest/gate-push.sh"
}

install_cursor() {
  mkdir -p "$TARGET/.cursor/hooks" "$TARGET/.cursor/rules" "$TARGET/.ai"
  fill_mcp "$KIT_ROOT/templates/cursor/mcp.json" "$TARGET/.cursor/mcp.json"
  echo "  + .cursor/mcp.json"

  cp "$KIT_ROOT/templates/cursor/hooks.json" "$TARGET/.cursor/hooks.json"
  install_guards "$TARGET/.cursor/hooks"
  echo "  + .cursor/hooks.json (node invoke-hook → bash)"

  cp "$KIT_ROOT/templates/cursor/rules/use-guides.mdc" "$TARGET/.cursor/rules/use-guides.mdc"
  cp "$KIT_ROOT/templates/cursor/rules/code-review.mdc" "$TARGET/.cursor/rules/code-review.mdc"
  cp "$KIT_ROOT/templates/cursor/rules/git-branch-pr.mdc" "$TARGET/.cursor/rules/git-branch-pr.mdc"
  if [[ ! -f "$TARGET/.cursor/BUGBOT.md" ]]; then
    cp "$KIT_ROOT/templates/cursor/BUGBOT.md" "$TARGET/.cursor/BUGBOT.md"
  fi

  copy_shared_agents "$TARGET/.cursor/agents"

  if [[ -d "$KIT_ROOT/templates/cursor/skills" ]]; then
    mkdir -p "$TARGET/.cursor/skills"
    cp -R "$KIT_ROOT/templates/cursor/skills/." "$TARGET/.cursor/skills/"
    echo "  + .cursor/skills/ (Cursor-only, np. /compact)"
  fi
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
    (dest_dir / src.name).write_text(out, encoding="utf-8")
PY
  echo "  + $dest_dir (Claude slash commands, \$ARGUMENTS wired)"
}

install_claude() {
  fill_mcp "$KIT_ROOT/templates/claude/mcp.json" "$TARGET/.mcp.json"
  echo "  + .mcp.json (Claude Code)"

  install_guards "$TARGET/.claude/hooks"
  cp "$SHARED_GUARDS/gate-file-writes.mjs" "$TARGET/.claude/hooks/gate-file-writes.mjs"
  # settings.json nalezy do uzytkownika — scalamy tylko wpisy kita.
  "$PYTHON_BIN" "$KIT_ROOT/scripts/claude_settings.py" install     "$TARGET/.claude/settings.json" "$KIT_ROOT/templates/claude/settings.json"
  echo "  + .claude/hooks/ + wpisy PreToolUse w .claude/settings.json"

  copy_shared_agents "$TARGET/.claude/agents"
  copy_claude_commands "$TARGET/.claude/commands"
}

install_codex() {
  mkdir -p "$TARGET/.codex/agents"
  fill_mcp "$KIT_ROOT/templates/codex/config.toml" "$TARGET/.codex/config.toml" "$TARGET"
  echo "  + .codex/config.toml"
  if [[ "$SKIP_AGENTS" -eq 0 ]]; then
    if [[ -d "$KIT_ROOT/templates/codex/agents" ]]; then
      cp "$KIT_ROOT/templates/codex/agents/"*.toml "$TARGET/.codex/agents/" 2>/dev/null || true
    fi
    # Reszta shared agentów bez ręcznego .toml: auto-render (curated ma pierwszeństwo).
    "$PYTHON_BIN" "$KIT_ROOT/scripts/render_agent_commands.py" codex "$SHARED_AGENTS" \
      "$TARGET/.codex/agents" "$KIT_ROOT/templates/codex/agents"
    echo "  + .codex/agents/ (curated + auto-rendered)"
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
  render_agent_commands vscode "$TARGET/.github/prompts"
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
}

install_kilo() {
  mkdir -p "$TARGET/.kilocode"
  fill_mcp "$KIT_ROOT/templates/kilo/mcp.json" "$TARGET/.kilocode/mcp.json"
  echo "  + .kilocode/mcp.json"
  render_agent_commands kilo "$TARGET/.kilocode/workflows"
}

install_antigravity() {
  mkdir -p "$TARGET/.agents"
  fill_mcp "$KIT_ROOT/templates/antigravity/mcp_config.json" "$TARGET/.agents/mcp_config.json"
  echo "  + .agents/mcp_config.json"
  render_agent_commands antigravity "$TARGET/.agents/workflows"
}

install_opencode() {
  mkdir -p "$TARGET/.opencode"
  fill_mcp "$KIT_ROOT/templates/opencode/opencode.json" "$TARGET/opencode.json" "$TARGET"
  echo "  + opencode.json"
  render_agent_commands opencode "$TARGET/.opencode/command"
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

install_git_pre_push_reminder() {
  # Dla klientów bez Cursor hooks — szablon do ręcznej instalacji / copy do .git/hooks
  if [[ -f "$KIT_ROOT/templates/git-hooks/pre-push" ]]; then
    mkdir -p "$TARGET/git-hooks"
    cp "$KIT_ROOT/templates/git-hooks/pre-push" "$TARGET/git-hooks/pre-push"
    chmod +x "$TARGET/git-hooks/pre-push"
    echo "  + git-hooks/pre-push (zainstaluj do .git/hooks/pre-push)"
  fi
}

echo "Bootstrap instruction-kit → $TARGET"
echo "  preset=$PRESET"
echo "  language=$LANGUAGE"
echo "  codegen=$CODEGEN"
echo "  clients=$CLIENTS_ARG"
echo "  from=$FROM_SRC"

mkdir -p "$TARGET/.ai"
install_agenty_md_once
install_bugbot_md_once

if [[ "$PRUNE_CLIENTS" -eq 1 ]]; then
  prune_unselected_clients
  echo "  (sprzątnięto kitowe pliki klientów spoza --clients ${CLIENTS_ARG}; wyłącz: --keep-unselected-clients)"
fi

NEED_GIT_HOOK=0
for c in "${CLIENTS_LIST[@]}"; do
  case "$c" in
    cursor) install_cursor ;;
    claude) install_claude; NEED_GIT_HOOK=1 ;;
    codex) install_codex; NEED_GIT_HOOK=1 ;;
    vscode) install_vscode; NEED_GIT_HOOK=1 ;;
    kiro) install_kiro; NEED_GIT_HOOK=1 ;;
    kilo) install_kilo; NEED_GIT_HOOK=1 ;;
    antigravity) install_antigravity; NEED_GIT_HOOK=1 ;;
    opencode) install_opencode; NEED_GIT_HOOK=1 ;;
    *)
      echo "Nieobsługiwany klient po expand: $c" >&2
      exit 1
      ;;
  esac
done

if [[ "$NEED_GIT_HOOK" -eq 1 ]] && ! client_enabled cursor; then
  install_git_pre_push_reminder
elif [[ "$NEED_GIT_HOOK" -eq 1 ]] && client_enabled cursor; then
  : # Cursor ma gate-*; opcjonalnie i tak zostaw szablon
  if [[ ! -f "$TARGET/git-hooks/pre-push" ]] && [[ -f "$KIT_ROOT/templates/git-hooks/pre-push" ]]; then
    install_git_pre_push_reminder
  fi
fi

if [[ "$WITH_PROFILE" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.profile.yaml" ]]; then
    sed "s/my-project/$(basename "$TARGET")/; s|profiles/_base.yaml|profiles/${PRESET}.yaml|" \
      "$KIT_ROOT/templates/project.profile.yaml" > "$TARGET/.ai/project.profile.yaml"
    echo "  + .ai/project.profile.yaml (extends profiles/${PRESET}.yaml)"
  fi
fi

if [[ "$WITH_OVERLAY" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.md" ]]; then
    cp "$KIT_ROOT/templates/project.md" "$TARGET/.ai/project.md"
    echo "  + .ai/project.md"
  fi
fi

if [[ "$WITH_PLUGINS" -eq 1 ]]; then
  install_plugins
fi

# Stamp — commit kita w momencie bootstrapu, do taniego "czy trzeba re-bootstrapować"
# (MCP tool check_kit_status). Pusty kit_commit gdy --from to zdalny URL / nie-git.
KIT_COMMIT="$(git -C "$KIT_ROOT" rev-parse HEAD 2>/dev/null || true)"
BOOTSTRAPPED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$TARGET/.ai"
cat > "$TARGET/.ai/.kit-bootstrap.json" <<JSON
{
  "kit_commit": "${KIT_COMMIT}",
  "kit_from": "${FROM_SRC}",
  "bootstrapped_at": "${BOOTSTRAPPED_AT}",
  "preset": "${PRESET}",
  "language": "${LANGUAGE}",
  "codegen": "${CODEGEN}",
  "clients": "${CLIENTS_ARG}"
}
JSON
echo "  + .ai/.kit-bootstrap.json (stamp dla check_kit_status)"

echo ""
echo "Gotowe. Zrestartuj IDE w $TARGET."
echo "Clients: ${CLIENTS_ARG}"
echo "Slash: /git-start, /git-check, /git-commit, /git-end, /review-*, /subagent-*, /teacher-*"
if client_enabled cursor; then
  echo "Slash (Cursor): /compact (= Summarize; nie dla Claude/Codex)"
fi
echo "MCP: --preset ${PRESET} --language ${LANGUAGE} --codegen ${CODEGEN} --clients ${CLIENTS_ARG} --workspace …"
