# FAQ

## Czy kit kopiuje moduły do mojego projektu?

Nie. Treści modułów czyta serwer MCP na żywo. Do projektu trafiają pliki klientów, agentów, komend, hooków, Profil i overlay.

## Czy muszę restartować klienta?

Tak, po każdym `install`, `reload` i zmianie konfiguracji MCP. Komendy i MCP ładują się przy starcie.

## Czy mogę mieć własne reguły projektu?

Tak. Wpisuj je w blok `project:rules` w `BUGBOT.md` i `project:agents` w `AGENTS.md`. Ten blok przechodzi przez każdy reload bez zmian. Reguły specyficzne dla repo idą też do overlayu, `.ai/project.md`.

## Czy mogę wyłączyć guard?

Nie na stałe, i to celowo. Dla wyjątku w projekcie dodajesz `allow` w Profilu. Heurystykę hosta korygujesz zmienną środowiskową na maszynie. Wyłączenie `server.guard: off` w Profilu wyłączyłoby guard także na VPS, więc nie rób tego w repo, które trafia na serwer.

## Jak usunąć kit z projektu?

```bash title="Git Bash · bash"
kit-ai remove --dry-run    # pokaż listę, nic nie usuwa
kit-ai remove
```

Usuwa pliki kita wszystkich klientów, konfiguracje MCP, sekcję w `.gitignore`, Profil i stamp. Zostają `.ai/project.md`, `CONTEXT.md`, `docs/adr/` i twoje pliki. Kit nie robi kopii zapasowej, więc niczego nie przywraca.

## Czy kit działa na Windows?

Tak. Pracuj w Git Bash. Zob. [Windows](../hosty/windows.md).

## Czy kit działa na Linuksie bez Windowsa?

Tak. Na serwerze profil `vps` włącza tryb lekki i server guard. Zob. [Linux VPS](../hosty/linux-vps.md).

## Gdzie kit zapisuje logi i cache?

Poza projektem, w katalogu cache:

- `~/.cache/kit-ai/headless/<repo>/`: logi wykonawców headless,
- `~/.cache/kit-ai/retro/<repo>/`: wyniki analizy sesji,
- `~/.cache/night-run-<repo>-<data>/`: kontekst nocy.

## Które klienty są zweryfikowane na żywo?

Formaty VS Code, Kilo, Antigravity i opencode oparte są na dokumentacji z sierpnia 2026. Nie były testowane na żywych instalacjach. Format Kiro też nie jest zweryfikowany. Zob. [Klienci AI](../konfiguracja/klienci.md).

## Czy kit wymaga GitHuba?

Procedury issue i PR (`git-*`, `create-task`, `night-run`) używają `gh`. Bez `gh` działa reszta: instrukcje, review i konfiguracja.

## Co zrobić po aktualizacji kita?

`uv tool upgrade guides-mcp`, potem `kit-ai reload` w każdym projekcie. Zob. [Aktualizacja](../start/aktualizacja.md).
