# Shell proxy — RTK + shell POSIX

Przed wykonaniem komend shell (git, testy, grep/find, listowanie plików, docker, gh, itp.)
sprawdź czy w `PATH` jest dostępny CLI `rtk` (Rust Token Killer).

## Shell — zawsze POSIX, nigdy PowerShell/cmd

Komendy deweloperskie uruchamiaj **zawsze w shellu POSIX**, niezależnie od
domyslnego shella klienta na danej maszynie:

- **Windows:** Git Bash (`bash.exe` z Git for Windows) — sprawdzaj po kolei:
  `bash` w `PATH` → `C:\Program Files\Git\bin\bash.exe` →
  `C:\Program Files\Git\usr\bin\bash.exe` →
  `%LocalAppData%\Programs\Git\bin\bash.exe`.
  Nigdy nie uruchamiaj komend deweloperskich przez `powershell`/`pwsh`/`cmd`.
- **Linux / macOS:** domyslny shell POSIX (`bash` / `zsh`), bez zmian.
- Skladnia komend (`&&`, `|`, redirecty, globbing, ścieżki `/c/...` na Windows)
  to zawsze składnia POSIX, także gdy klient ma domyślnie inny shell.
- Wyjątek: komendy specyficzne dla PowerShell (np. `Get-ChildItem`) są dozwolone
  tylko wtedy, gdy klient nie potrafi uruchomić basha — wtedy opisz to wprost.

## RTK — prefiks komend

- **Jeśli `rtk` istnieje:** prefiksuj nim komendy developerskie, np. `rtk git status`,
  `rtk grep "pattern" src/`, `rtk docker ps`, `rtk gh pr list`. RTK filtruje/kompresuje
  output przed trafieniem do kontekstu — 60–90% oszczędności tokenów na typowych
  operacjach dev.
- **Jeśli `rtk` nie istnieje:** wykonuj komendy normalnie (bez prefiksu) — nie instaluj
  go, nie traktuj braku jako błędu.
- **Meta-komendy** (zawsze bez filtrowania, wołane bezpośrednio): `rtk gain`,
  `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (raw, debug).
- Nie myl z narzędziem o tej samej nazwie (`reachingforthejack/rtk` — Rust Type Kit) —
  jeśli `rtk --version` / `rtk gain` nie działa, to zły binarny `rtk`, pomiń prefiksowanie.

Zasada ogólna (nie zależy od presetu/domeny) — dotyczy każdego projektu bootstrapowanego
tym kitem, niezależnie od `--preset`.

Świadomy wyjątek od `core:repo-first` / "Nowa zasada architektoniczna — dokąd ją zapisać":
to preferencja operatora kita, nie fakt jednego produktu ani zasada specyficzna dla kategorii —
zostaje w `core:*` bo jest bezpieczna (no-op gdy `rtk` nie ma w PATH) i ma obowiązywać wszędzie
gdzie ten kit jest używany, niezależnie od projektu.
