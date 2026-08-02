#!/usr/bin/env bash
# Bootstrap instruction-kit w repo aplikacji.
#
# Użycie:
#   ./scripts/bootstrap-project.sh /sciezka/do/projektu [--from PATH|URL] [--preset shop]
#
# Domyślny preset: _base (nie trzeba podawać).
# Kategoria e-commerce: --preset shop
# Lokalny fork kategorii: --with-profile

set -euo pipefail

usage() {
  cat <<'EOF'
Użycie: bootstrap-project.sh TARGET_DIR [opcje]

Opcje:
  --preset NAME       Kategoria z kita (domyślnie: _base). Przykład: shop
  --language LANG     Język prozy instrukcji: pl|en (domyślnie: pl). Tytuły issue/PR zawsze EN
  --from SOURCE       Źródło uvx: ścieżka lokalna lub git+https://… (domyślnie: placeholder GitHub)
  --with-profile      Skopiuj templates/project.profile.yaml → .ai/project.profile.yaml (tylko fork)
  --with-overlay      Skopiuj templates/project.md → .ai/project.md (jeśli brak)
  --skip-agents       Nie kopiuj .cursor/agents
  -h, --help          Ta pomoc

Przykład (generyczny — default _base, język PL):
  ./scripts/bootstrap-project.sh ../moj-projekt \
    --from /m/projects/ai-instruction-kit-mcp \
    --with-overlay

Przykład (kategoria shop / e-commerce, EN prose):
  ./scripts/bootstrap-project.sh ../olivin-app \
    --preset shop \
    --language en \
    --from /m/projects/ai-instruction-kit-mcp
EOF
}

TARGET=""
PRESET="_base"
LANGUAGE="pl"
FROM_SRC="git+https://github.com/TWOJ_USER/ai-instruction-kit-mcp.git"
WITH_PROFILE=0
WITH_OVERLAY=0
SKIP_AGENTS=0

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
    --from) FROM_SRC="${2:?}"; shift 2 ;;
    --with-profile) WITH_PROFILE=1; shift ;;
    --with-overlay) WITH_OVERLAY=1; shift ;;
    --skip-agents) SKIP_AGENTS=1; shift ;;
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

# Normalizuj --from: lokalna ścieżka → absolutna (uvx lubi absolutne).
if [[ -d "$FROM_SRC" ]]; then
  FROM_SRC="$(cd "$FROM_SRC" && pwd)"
fi

echo "Bootstrap instruction-kit → $TARGET"
echo "  preset=$PRESET"
echo "  language=$LANGUAGE"
echo "  from=$FROM_SRC"

mkdir -p "$TARGET/.cursor/hooks" "$TARGET/.cursor/rules" "$TARGET/.ai"

# --- MCP (Cursor): preset + workspace + language ---
cat > "$TARGET/.cursor/mcp.json" <<EOF
{
  "mcpServers": {
    "project-guides": {
      "command": "uvx",
      "args": [
        "--from", "${FROM_SRC}",
        "guides-mcp",
        "--preset", "${PRESET}",
        "--language", "${LANGUAGE}",
        "--workspace", "\${workspaceFolder}"
      ]
    }
  }
}
EOF

# --- Hooks ---
cp "$KIT_ROOT/templates/cursor/hooks.json" "$TARGET/.cursor/hooks.json"
cp "$KIT_ROOT/templates/cursor/hooks/gate-push.sh" "$TARGET/.cursor/hooks/gate-push.sh"
cp "$KIT_ROOT/templates/cursor/hooks/gate-destructive.sh" "$TARGET/.cursor/hooks/gate-destructive.sh"
chmod +x "$TARGET/.cursor/hooks/gate-push.sh" "$TARGET/.cursor/hooks/gate-destructive.sh"

# --- Rules / Bugbot / AGENTS ---
cp "$KIT_ROOT/templates/cursor/rules/use-guides.mdc" "$TARGET/.cursor/rules/use-guides.mdc"
cp "$KIT_ROOT/templates/cursor/rules/code-review.mdc" "$TARGET/.cursor/rules/code-review.mdc"
cp "$KIT_ROOT/templates/cursor/rules/git-branch-pr.mdc" "$TARGET/.cursor/rules/git-branch-pr.mdc"
if [[ ! -f "$TARGET/.cursor/BUGBOT.md" ]]; then
  cp "$KIT_ROOT/templates/cursor/BUGBOT.md" "$TARGET/.cursor/BUGBOT.md"
fi
if [[ ! -f "$TARGET/AGENTS.md" ]]; then
  cp "$KIT_ROOT/templates/AGENTS.md" "$TARGET/AGENTS.md"
fi

# --- Agents ---
if [[ "$SKIP_AGENTS" -eq 0 ]]; then
  mkdir -p "$TARGET/.cursor/agents"
  cp "$KIT_ROOT/templates/claude/agents/"*.md "$TARGET/.cursor/agents/"
fi

# --- Cursor-only skills (NIE kopiować do Claude/Codex) ---
# /compact = alias UI Summarize wyłącznie w Cursorze; nie definiuje compact dla innych klientów.
if [[ -d "$KIT_ROOT/templates/cursor/skills" ]]; then
  mkdir -p "$TARGET/.cursor/skills"
  cp -R "$KIT_ROOT/templates/cursor/skills/." "$TARGET/.cursor/skills/"
  echo "  + .cursor/skills/ (Cursor-only, np. /compact → Summarize)"
fi

# --- Opcjonalny lokalny profil / overlay ---
if [[ "$WITH_PROFILE" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.profile.yaml" ]]; then
    sed "s/my-project/$(basename "$TARGET")/; s|profiles/_base.yaml|profiles/${PRESET}.yaml|" \
      "$KIT_ROOT/templates/project.profile.yaml" > "$TARGET/.ai/project.profile.yaml"
    echo "  + .ai/project.profile.yaml (extends profiles/${PRESET}.yaml)"
  fi
  # Przy lokalnym profilu mcp może używać --profile zamiast --preset — zostawiamy preset;
  # lokalny profil jest opcjonalnym dokumentem / przyszłym nadpisaniem.
fi

if [[ "$WITH_OVERLAY" -eq 1 ]]; then
  if [[ ! -f "$TARGET/.ai/project.md" ]]; then
    cp "$KIT_ROOT/templates/project.md" "$TARGET/.ai/project.md"
    echo "  + .ai/project.md"
  fi
fi

echo ""
echo "Gotowe. Zrestartuj okno Cursor w $TARGET."
echo "Slash (Cursor): /compact (= Summarize; nie dla Claude/Codex)"
echo "Slash: /git-start, /git-check, /git-commit, /git-end, /review-*, /subagent-*"
echo "MCP: --preset ${PRESET} --language ${LANGUAGE} --workspace \${workspaceFolder}"
