# Konfiguracja serwera MCP

Serwer uruchamia się przez `uvx` albo przez lokalny klon kita. Wpis wstawia bootstrap, ale znajomość flag pomaga, gdy coś się nie zgadza.

## Przykład wpisu (Claude Code)

```json title=".mcp.json (przykład)"
{
  "mcpServers": {
    "kit-ai-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/radthenone/ai-instruction-kit-mcp.git",
        "guides-mcp",
        "--language", "pl",
        "--clients", "all",
        "--workspace", "${CLAUDE_PROJECT_DIR:-.}"
      ]
    }
  }
}
```

Kolejność: najpierw `--from` i nazwa pakietu `guides-mcp`, potem flagi.

## Flagi

| Flaga | Wymagana | Rola |
|---|---|---|
| `--from SOURCE` | przy `uvx` | źródło kita: `git+https://…@ref`. Przy lokalnym klonie bootstrap generuje `uv run --project` |
| `--language pl\|en` | nie | język prozy. Domyślnie `language:` z Profilu, potem `pl` |
| `--clients LISTA` | nie | metadane klientów: `all`, `cursor`, `claude`, `codex`, `vscode`, `kiro`, `kilo`, `antigravity`, `opencode`. Nie zmienia treści bundli |
| `--kit-root PATH` | nie | klon kita, z którego serwer czyta manifest i moduły. Bootstrap dodaje go sam przy lokalnym źródle |
| `--workspace PATH` | zalecana | root aplikacji. Stąd Profil i Overlay. Ścieżka absolutna albo zmienna klienta |
| `--overlay PATH` | nie | dodatkowy plik Markdown, można podać wielokrotnie. Rzadko potrzebne |

Stare flagi `--preset`, `--profile` i `--codegen` są ignorowane. Bootstrap zapisuje tylko `--language` i `--clients`.

## Zmienne środowiskowe

| Zmienna | Odpowiednik | Uwaga |
|---|---|---|
| `GUIDES_LANGUAGE` | `--language` | |
| `GUIDES_CLIENTS` | `--clients` | |
| `GUIDES_KIT_ROOT` | `--kit-root` | |
| `GUIDES_WORKSPACE` | `--workspace` | bez niej `bootstrap_workspace` odmawia zapisu |
| `KIT_HOST_PROFILE` | profil hosta | alias `GUIDES_HOST_PROFILE`. Zob. [Profil hosta](../hosty/profil-hosta.md) |

## Źródło zdalne czy lokalny klon

- **Zdalne** (`uvx --from git+https://…`): pakiet jest cache'owany pod wersję. Zmiana w kodzie bez zmiany wersji nie dociera do klienta.
- **Lokalny klon** (`uv run --project <klon>`): kod i moduły czytane są wprost z klona. Zmiany działają po restarcie klienta.

Szczegóły i objaw nieaktualnego cache: [Aktualizacja kita](../start/aktualizacja.md).

## Wpis per klient

Każdy klient ma inny plik i klucz. Tabela: [Klienci AI](../konfiguracja/klienci.md). Dla Codexa format to TOML:

```toml title=".codex/config.toml (przykład)"
[mcp_servers.kit-ai-mcp]
command = "uvx"
args = ["--from", "git+https://github.com/radthenone/ai-instruction-kit-mcp.git", "guides-mcp", "--language", "pl", "--clients", "all", "--workspace", "/m/projects/moja-appka"]
```

Codex nie rozwiązuje `${workspaceFolder}`, więc ścieżka musi być absolutna.

!!! warning "Po zmianie konfiguracji zrestartuj klienta"
    MCP ładuje się przy starcie. Bez restartu zobaczysz stan sprzed zmiany.
