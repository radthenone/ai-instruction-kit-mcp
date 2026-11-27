# Windows (host lokalny)

Na Windows kit pracuje w profilu `local`. Guardy serwerowe są wtedy nieaktywne, a buildy i instalacje dozwolone. Najwięcej problemów na Windows bierze się z powłoki i ścieżek, więc przejrzyj tę stronę przed pierwszą instalacją.

## Git Bash

Agent na Windows używa **Git Bash** (Git for Windows). Guard `bash-guard` blokuje `pwsh`, `powershell` i `cmd` uruchamiane z narzędzia Bash. Narzędzie PowerShell nie jest blokowane, ale instrukcje kita piszą komendy pod Bash.

Ścieżka w Git Bash to `/m/projects/moja-appka`, a w Windows `M:\projects\moja-appka`. Nie mieszaj obu form w jednym pliku konfiguracji.

## Instalacja

```bash title="Git Bash"
uv tool install git+https://github.com/radthenone/ai-instruction-kit-mcp
cd /m/projects/moja-appka
kit-ai install
```

## Narzędzia

```bash title="Git Bash"
winget install rtk-ai.rtk          # rtk, działa też z Git Bash
```

`node`, `uv` i `gh` instaluj zgodnie z ich dokumentacją. Hooki Ponytaila i Cavemana potrzebują `node` w PATH **powłoki nieinteraktywnej**. Przy nvm to częsta pułapka.

## Serwery MCP przez npx

Lokalny serwer stdio odpalany przez `npx` uruchamiaj na Windows jako `cmd /c npx …`. Serwery zdalne (Context7, GitHub) tego nie potrzebują.

## Symlinki przy skillach

`npx skills` domyślnie tworzy symlinki. Na Windows wymagają Developer Mode albo uprawnień administratora. Dodaj flagę `--copy`.

## Caveman

Na Windows użyj pełnego instalatora `install.ps1`, nie `install.sh`. Hooki i tak wołają wersje PowerShell.

## Zmienne z tokenami

```powershell title="PowerShell: trwała zmienna użytkownika"
setx GITHUB_PAT_TOKEN "…"
```

```bash title="Git Bash: tylko bieżąca sesja"
export GITHUB_PAT_TOKEN=…
```

Klient musi wystartować już z ustawioną zmienną. Zmienna dodana po starcie klienta nie zadziała.

## WSL

WSL jest traktowany jak dev na Windows, nie jak VPS, nawet przy małych zasobach. Guard serwerowy jest w nim nieaktywny. Zob. [Profil hosta](profil-hosta.md).
