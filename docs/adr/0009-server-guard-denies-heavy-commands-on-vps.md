# ADR 0009: Server guard blokuje ciężkie komendy na VPS

Data: 2026-10-15
Status: accepted

## Kontekst

Incydent z 2026-10-15: na VPS w kontenerze LXC (ok. 4 GB RAM, bez swapu,
1 vCPU), obok produkcyjnych kontenerów innych projektów, subagent uruchomił
`uv run ruff` bez `--no-sync`. uv zaczął kompilować zależność natywną ze źródeł,
a w tej samej komendzie poszedł pytest na całych katalogach. Pamięć się skończyła
i serwer zrestartował się po ok. 45 minutach.

Reguła „na VPS tylko lekkie komendy" istniała wyłącznie jako tekst
w `modules/infra/vps-lightweight.md`. Sekcja „Bez hooka blokującego" świadomie
odrzuciła twardą blokadę — z obawy, że hook zablokuje celowe operacje (deploy,
ręczny restart, automatyzację). Incydent pokazuje, że sam tekst nie wystarcza:
subagent pod night-run nie czyta overlayu tak uważnie jak sesja interaktywna.
Wykrywanie VPS już istniało (`src/guides/host_profile.py`), brakowało egzekucji.

## Decyzja

Wprowadzamy `templates/shared/guards/server-guard.mjs` — twardy guard (allow/deny,
ADR 0006), aktywny **tylko na słabym hoście serwerowym**, z decyzją w runtime:

1. `server.guard: off` w Profilu → allow (ucieczka, gdy heurystyka się myli
   w drugą stronę).
2. `KIT_HOST_PROFILE` / `GUIDES_HOST_PROFILE` = `vps` / `local` → wymuszenie
   (tylko na wypadek pomyłki heurystyki; normalnie nieustawiane).
3. Heurystyka 1:1 z `host_profile.py` → aktywny na VPS.
4. W pozostałych przypadkach → allow (PC i CI przepuszczają wszystko).

## Dlaczego lista jest krótka

Guard odrzuca tylko komendy, które w kilka minut zjadają RAM/CPU albo zatrzymują
cudze usługi: kontenery i ich budowanie, instalację/budowanie paczek, buildy
produkcyjne, przeglądarki/e2e oraz `pytest -xdist`. Świadomie poza listą:
dev serwery i watchery, `pytest` bez ścieżki, `eslint .`, `systemctl` / `pkill` —
na serwerze z kilkoma GB RAM nie zawieszają go same z siebie (projekt dopisuje
je w `server.deny`, README podaje gotowe propozycje).

Krótka lista = mało fałszywych blokad = agent nie uczy się obchodzić guarda.
Każdy deny niesie powód z alternatywą (linter zamiast builda, `uv run --no-sync`
zamiast `uv run`, CI zamiast e2e).

## Dlaczego wrappery rozwijane przy reload

Guard widzi tylko tekst komendy. `task test:backend` nie zawiera słowa `docker`,
choć task w środku odpala `docker-compose`. Dlatego `kit-ai reload` rozwija
Taskfile, skrypty `package.json` i `turbo run` do deny wrapperów z łańcuchem
powodu (`bun run build → turbo run build → next build`). Bez reloadu guard działa
na starej liście — README mówi to wprost.

## Konsekwencje

- `vps-lightweight.md`: sekcja „Bez hooka blokującego" zastąpiona odwołaniem
  do server-guarda i tego ADR-a.
- Lokalne pluginy guardów w projektach stają się zbędne: podbij wersję kita,
  `kit-ai reload`, usuń własny plugin.
- Czego guard tekstowy nie złapie: agent zapisuje własny skrypt i go odpala.
  Dlatego README zaleca też higienę hosta (Playwright MCP wyłączony na serwerze,
  użytkownik agenta poza grupą `docker`, limit pamięci na sesję).
