# templates/shared

Kanon treści instrukcji (niezależny od IDE):

| Katalog | Rola |
|---------|------|
| `agents/*.md` | Slash/subagenci (`/git-*`, `/review-*`, `/subagent-*`) |
| `rules/*.md` | Reguły flow (git, review, warstwy MCP) — bez frontmatter Cursor |

Adaptery (`templates/cursor`, `claude`, `codex`, `vscode`, `kiro`, `kilo`, `antigravity`) tylko formatują MCP i mapują te pliki na natywne ścieżki klienta.

Bootstrap: `scripts/bootstrap-project.sh --clients all|…`
