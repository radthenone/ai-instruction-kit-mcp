# Instalacja

Kit instalujesz w **repo aplikacji**, nie w repo kita. Nie potrzebujesz klona kita: narzędzie `kit-ai` instaluje się przez `uv` prosto z GitHuba.

## Wymagania

| Narzędzie | Po co |
|---|---|
| `uv` w `PATH` | instalacja narzędzia `kit-ai` i serwera MCP |
| `git` | pobranie kita, branche, worktree |
| `bash` (Windows: Git for Windows, czyli Git Bash) | skrypt bootstrapu i hooki agentów |
| `node` | hooki guardów (`.mjs`) w klientach |
| `python3`, major 3 | bootstrap i skrypty pomocnicze |
| `gh` (GitHub CLI) | procedury issue i PR (`git-*`, `create-task`) |
| `npx` (opcjonalnie) | zewnętrzne skille i pluginy |
| `rtk` (opcjonalnie) | przepisywanie komend na `rtk …`, zob. [Narzędzia zewnętrzne](narzedzia-zewnetrzne.md) |

## Krok 1: narzędzie `kit-ai`

=== "Windows (host lokalny)"

    Pracuj w **Git Bash**. Ścieżki w stylu `/m/projects/…`.

    ```bash title="Git Bash"
    uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
    ```

=== "Linux (serwer VPS)"

    ```bash title="bash"
    uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
    ```

Ref po `@` wybiera wersję: `…ai-instruction-kit-mcp@dev` to gałąź `dev`, a `@<tag>` albo `@<commit>` to konkretny stan. Bez `@` jest gałąź domyślna.

Jednorazowo, bez instalowania narzędzia:

```bash title="bash"
uvx --from git+https://github.com/radthenone/ai-instruction-kit-mcp kit-ai install
```

## Krok 2: install w repo aplikacji

=== "Windows (host lokalny)"

    ```bash title="Git Bash"
    cd /m/projects/moja-appka          # repo aplikacji
    kit-ai install                     # bez ścieżki = bieżący katalog
    ```

=== "Linux (serwer VPS)"

    ```bash title="bash"
    cd ~/projects/moja-appka           # repo aplikacji
    kit-ai install
    ```

`install` pyta o dwie rzeczy: `Język [pl/en] (pl)` i `Klienci (…) (all)`. Flagi `--language` i `--clients` pomijają pytania. Bez terminala (TTY) pytań nie ma wcale, więc w skryptach podawaj flagi:

```bash title="bash"
kit-ai install --language pl --clients claude,codex
```

Co się dzieje:

- powstaje `.ai/project.profile.yaml` (puste Tiery oznaczają sam core) oraz `.ai/project.md` (overlay),
- bootstrap zapisuje pliki wybranych klientów: agentów, komendy, hooki guardów, konfigurację MCP,
- na końcu wypisywany jest JSON serwera MCP i miejsce, w którym leży konfiguracja każdego klienta.

Repo, w którym kit już jest zainstalowany, `install` odrzuca. Wtedy uruchom `kit-ai reload`.

## Krok 3: restart i weryfikacja

1. Zrestartuj IDE albo CLI. MCP i komendy ładują się przy starcie.
2. W sesji agenta poproś o narzędzie `check_kit_status`. Oczekiwany wynik: `Kit status: aktualny`.
3. Sprawdź działanie guardu. W Claude Code polecenie powinno wypisać `deny`:

```bash title="Git Bash · bash"
printf '%s' '{"tool_input":{"command":"git reset --hard HEAD"}}' \
  | node .claude/hooks/git-guard.mjs
```

4. Sprawdź, co wchodzi do repo, a co zostaje lokalnie:

```bash title="Git Bash · bash"
git status --short -uall .claude .codex .github/prompts
```

Dalej: [Pierwsza konfiguracja projektu](pierwsza-konfiguracja.md).
