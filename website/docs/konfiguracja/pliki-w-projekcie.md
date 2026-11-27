# Pliki w projekcie

Bootstrap zapisuje do repo aplikacji pliki zgodne z Profilem. Część z nich powinna być w gicie, część zostaje lokalnie.

## Co bootstrap zapisuje

- konfigurację MCP każdego wybranego klienta,
- agentów i komendy klienta (`.claude/agents/`, `.claude/skills/kit-ai/`, `.cursor/agents/`, `.github/prompts/`, `.opencode/commands/kit-ai/`, …),
- skille (`.claude/skills/`, `.codex/skills/`, `.agents/skills/`),
- hooki guardów klienta,
- `BUGBOT.md` (oraz `.cursor/BUGBOT.md` dla Cursora),
- `AGENTS.md` (kopiowany tylko, gdy go brak),
- `.ai/project.profile.yaml` (Profil) i `.ai/project.md` (Overlay, tylko gdy go brak),
- `.ai/.kit-bootstrap.json` (stamp z commitem kita).

Treści modułów kit nie kopiuje. Czyta je serwer MCP.

## Wersjonowane czy nie

Zasada: **konfiguracja AI jest częścią repo.** Hooki bezpieczeństwa, agenci i komendy mają działać u każdego, kto sklonuje projekt.

| Wersjonowane | Ignorowane |
|---|---|
| `.claude/{agents,commands,hooks,skills}/`, `.claude/settings.json` | `.claude/settings.local.json` (uprawnienia na maszynie) |
| `.codex/skills/` | `.codex/config.toml` (MCP) i reszta `.codex/` (stan sesji) |
| `.github/prompts/`, `.github/copilot-instructions.md`, `.github/hooks/` | `.vscode/mcp.json` (MCP) |
| `AGENTS.md`, `BUGBOT.md`, `.ai/project.md` | `.mcp.json`, `.cursor/mcp.json`, `.kiro/settings/mcp.json`, `.kilocode/mcp.json`, `.agents/mcp_config.json`, `opencode.json` (MCP), `.ai/.kit-bootstrap.json` (stamp) |
| | `.agents/skills/`, `skills-lock.json` (skille z `npx skills`, globalne) |

Konfiguracje MCP i stamp są **per maszyna**. Przy lokalnym klonie kita bootstrap wpisuje do nich absolutną ścieżkę klona. Plik zacommitowany z Windowsa (`M:/projects/…`) na Linuksie daje `CONNECTION_CLOSED` bez czytelnego powodu. Każda maszyna uruchamia `kit-ai reload` u siebie.

## Sekcja w `.gitignore`

Bootstrap wstawia do `.gitignore` repo aplikacji sekcję między markerami:

```text
# >>> instruction-kit >>>
…
# <<< instruction-kit <<<
```

Przy kolejnych przebiegach podmienia ją w całości, więc wpisy się nie duplikują. Reguły poza markerami zostają nietknięte.

Typowy `.gitignore` ma `.claude/` wpisane hurtem. Wtedy hooki i komendy nigdy nie trafiają do repo. Kit używa więc formy „ignoruj katalog, odwróć dla plików kita”, bo git nie wchodzi do zignorowanego katalogu.

## Repo zbootstrapowane wcześniej

Pliki MCP mogą być już w indeksie, a sam wpis w `.gitignore` ich nie odśledzi. Bootstrap wykrywa to i wypisuje komendę. Pliki zostają na dysku:

```bash title="Git Bash · bash"
git -C "$APP" rm --cached .mcp.json .vscode/mcp.json .codex/config.toml .ai/.kit-bootstrap.json
```

## Bloki chronione

- **`BUGBOT.md`**: własne reguły wpisujesz między `<!-- project:rules -->` i `<!-- /project:rules -->`. Ten blok przechodzi przez reload bajt w bajt.
- **`AGENTS.md`**: sekcja `kit:brief` i `kit:brief-rules` jest zarządzana przez kit. Twoje linie wpisujesz w blok `project:agents`.

Plik dostosowany przed wprowadzeniem bloku jest migrowany po historii szablonu. Gdy migracja jest niepewna, plik zostaje bez zmian, a reload wypisuje instrukcję ręcznego przeniesienia. Zob. [Doctor](../diagnostyka/doctor.md).
