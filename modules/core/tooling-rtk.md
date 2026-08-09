# Shell proxy — RTK (jeśli dostępny)

Przed wykonaniem komend shell (git, testy, grep/find, listowanie plików, docker, gh, itp.)
sprawdź czy w `PATH` jest dostępny CLI `rtk` (Rust Token Killer).

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
