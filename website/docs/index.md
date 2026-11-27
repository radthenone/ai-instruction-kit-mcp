<section class="kit-hero">
  <p class="kit-eyebrow">instruction-kit · serwer MCP <code>kit-ai-mcp</code></p>
  <h1>kit-ai</h1>
  <p class="kit-lead">Reguły pracy z agentami AI w każdym repo: stack, konwencje gita, review i Managed Worktree. Agent pobiera je z serwera MCP na żądanie, a projekt dostaje konfigurację i instrukcje.</p>
  <div class="kit-actions">
    <a class="kit-btn kit-btn--primary" href="start/instalacja/">Zainstaluj</a>
    <a class="kit-btn" href="https://github.com/radthenone/ai-instruction-kit-mcp">Repozytorium</a>
  </div>
</section>

## Szybki start

```bash title="Git Bash (Windows) · bash (Linux)"
uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
cd /m/projects/moja-appka        # repo aplikacji; na Linux: ~/projects/moja-appka
kit-ai install
```

Potem w kliencie AI uruchom `/kit-ai:kit-project-begin` (Claude Code; w OpenCode `/kit-ai/kit-project-begin`, w VS Code `/kit-project-begin`). Trzy kroki cyklu życia: [Szybki start](start/szybki-start.md).

## Mapa dokumentacji

- **Start**: [instalacja](start/instalacja.md), [pierwsza konfiguracja](start/pierwsza-konfiguracja.md), [aktualizacja](start/aktualizacja.md), [narzędzia zewnętrzne](start/narzedzia-zewnetrzne.md).
- **Koncepcja**: [jak działa kit](koncepcja/jak-dziala-kit.md), [warstwy AI](koncepcja/warstwy-ai.md), [przepływ zmiany](koncepcja/przeplyw-zmiany.md), [Managed Worktree](koncepcja/managed-worktree.md), [glosariusz](koncepcja/glosariusz.md).
- **Konfiguracja**: [profil](konfiguracja/profil.md), [tiery i stacki](konfiguracja/tiery-i-stacki.md), [overlay](konfiguracja/overlay.md), [moduły i bundle](konfiguracja/moduly-i-bundle.md), [klienci](konfiguracja/klienci.md).
- **Hosty**: [Windows](hosty/windows.md), [Linux VPS](hosty/linux-vps.md), [server guard](hosty/server-guard.md).
- **Komendy**: [przegląd](komendy/przeglad.md), [git](komendy/git.md), [review](komendy/review.md), [praca nocna i headless](komendy/praca-nocna-i-headless.md).
- **MCP**: [narzędzia](mcp/narzedzia.md), [konfiguracja serwera](mcp/konfiguracja-serwera.md).
- **Guardy**, **Diagnostyka** (doctor, retro, rozwiązywanie problemów, FAQ) i **Dla autorów kita**.

## Co dostajesz

- **`kit-ai install`** wpisuje serwer MCP i instrukcje do konfiguracji wybranych klientów (Claude, Codex, VS Code, Cursor, Kiro, Kilo, Antigravity, OpenCode).
- **`kit-ai-mcp`** to serwer MCP. Agent pobiera z niego moduły (`get_bundle`) i nadpisania tylko dla tego repo (`get_overlay`).
- **Procedury** `git-start`, `git-commit`, `git-end`, `review-*` prowadzą branch, commit, review i PR według jednej metody.
