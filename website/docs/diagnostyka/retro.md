# Retro: analiza sesji

Retro zbiera sygnały z rozmów agentów: odrzucenia przez guard, błędy narzędzi, pętle, koszt sesji. Grupuje je w znaleziska i proponuje zmiany. Niczego nie zakłada samo.

## Pojęcia

- **Sesja**: jeden zapis rozmowy razem z subagentami, albo jeden przebieg headless lub nocny ticket.
- **Sygnał**: pojedyncze wykrycie w logu, np. odrzucenie przez guard.
- **Znalezisko**: sygnały o tym samym znaczeniu, zgrupowane po **fingerprincie**. Fingerprint jest stały między sesjami i maszynami.
- **Koszt**: liczba tokenów sesji (wejście, cache i wyjście). To nie jest kwota w pieniądzach.
- **Propozycja**: zmiana kitu, projektu albo karta do założenia. Wymaga twojej akceptacji, zanim cokolwiek trafi na GitHub.

## Komendy

```bash title="Git Bash · bash"
kit-ai retro scan                       # skan sesji Claude Code tego repo
kit-ai retro scan --session <ID>        # jedna sesja, np. z hooka SessionEnd
kit-ai retro scan --since 2026-11-01    # sesje od daty albo z ostatnich Nd
kit-ai retro report                     # propozycje z wielu repo (co najmniej 3 sesje albo 2 repo)
```

Wyniki leżą w cache poza projektem: `~/.cache/kit-ai/retro/<repo>/`. Skan nie zmienia repo.

## Automatyczny skan

W Claude Code hook `retro-session-end` uruchamia skan po zakończeniu każdej sesji. Działa w tle i nigdy nie blokuje zamknięcia sesji.

## Klasyfikacja: `/kit-ai:kit-retro`

Skill klasyfikuje znaleziska do czterech kategorii:

- **kit**: problem w instrukcjach albo guardzie kita. Propozycja to zmiana w kicie, np. karta `create-task` w repo kita.
- **projekt**: problem w regułach albo overlayu tego repo. Propozycja to zmiana w `.ai/project.md` albo `BUGBOT.md`.
- **agent**: problem w zachowaniu agenta, np. pominął procedurę. Propozycja to wzmocnienie promptu.
- **zewnętrzne**: problem w cudzym pluginie albo narzędziu.

Z flagą `--kit` w repo kita skill bierze propozycje z agregacji wielu repo (`kit-ai retro report`).

Skill **nie edytuje plików**. Każda propozycja wymaga twojej akceptacji przed zapisem na GitHub.

## Dane

Skan czyta sesje lokalnie z katalogu sesji klienta i zapisuje wyniki do cache. Fragmenty dowodów w znaleziskach są maskowane.
