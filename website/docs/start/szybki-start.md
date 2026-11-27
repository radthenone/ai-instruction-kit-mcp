# Szybki start

Cykl życia kita w projekcie to trzy kroki. Szczegóły każdego są na osobnych stronach.

## 1. Instalacja

```bash title="Git Bash · bash"
uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
cd /m/projects/moja-appka          # repo aplikacji, nie repo kita
kit-ai install
```

Bez `@` instalujesz gałąź domyślną (`master`). Nowsze, jeszcze nie wydane zmiany są na `dev`: dopisz ref, np. `…/ai-instruction-kit-mcp@dev`. Pełne kroki: [Instalacja](instalacja.md).

## 2. Konfiguracja

Zrestartuj IDE albo CLI, a potem w kliencie AI. Komenda podana w formie Claude Code. W innych klientach inny przedrostek, zob. [Przegląd komend](../komendy/przeglad.md).

```text
/kit-ai:kit-project-begin      # pierwszy raz: pytania o stack, karta Profilu i .ai/project.md
/kit-ai:kit-project-edit "…"   # później: jedna zmiana, np. "zmień web na angular"
```

Po zapisie zrestartuj klienta jeszcze raz. Szczegóły: [Pierwsza konfiguracja](pierwsza-konfiguracja.md).

## 3. Aktualizacja

```bash title="Git Bash · bash"
uv tool upgrade guides-mcp     # nowa wersja kita
kit-ai reload                  # odśwież pliki kita w projekcie
kit-ai status                  # w agencie: narzędzie check_kit_status
kit-ai doctor                  # ścieżki i komendy w regułach vs repo
```

Szczegóły i tabela tego, co nadpisywane: [Aktualizacja](aktualizacja.md).

## Jednorazowo, bez instalowania narzędzia

```bash title="bash"
uvx --from git+https://github.com/radthenone/ai-instruction-kit-mcp kit-ai install
```
