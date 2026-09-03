# templates/shared

Kanon treści instrukcji (niezależny od IDE):

| Katalog | Rola |
|---------|------|
| `agents/*.md` | Slash/subagenci (`/git-*`, `/review-*`, `/subagent-*`) |
| `rules/*.md` | Reguły flow (git, review, warstwy MCP) — bez frontmatter Cursor |
| `guards/*` | Polityka guardraili + adapter (hooki klienta) |
| `skills/<nazwa>/SKILL.md` | Skille — wiedza, którą model ładuje sam z `description` |

Adaptery (`templates/cursor`, `claude`, `codex`, `vscode`, `kiro`, `kilo`, `antigravity`) tylko formatują MCP i mapują te pliki na natywne ścieżki klienta.

Skille trafiają natywnie do `claude`, `cursor` i `antigravity`; pozostali klienci dostają
je jako komendę `/nazwa` — szczegóły degradacji w `scripts/install_shared_skills.py`
i w skillu `skill-authoring`.

Bootstrap: `scripts/bootstrap-project.sh --clients all|…`
