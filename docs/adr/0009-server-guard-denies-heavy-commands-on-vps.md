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

## Wyjątek „tylko lockfile” (#317)

Ticket, który dodaje zależność, musi móc zaktualizować lockfile także na VPS.
Guard nadal blokuje instalację, ale dopuszcza formy, które tylko rozwiązują
wersje i zapisują lockfile:

| Ekosystem | Allow | Wymagane flagi |
|---|---|---|
| uv | `uv lock` | `--no-build` |
| uv | `uv add` / `uv remove` | `--no-sync` **i** `--no-build` |
| npm | `npm install` | `--package-lock-only` **i** `--ignore-scripts` |
| pnpm | `pnpm install` | `--lockfile-only` **i** `--ignore-scripts` |
| bun | `bun install` | `--lockfile-only` **i** `--ignore-scripts` |

Każda inna forma tych komend zostaje deny, a powód wskazuje dozwoloną formę.
`server.deny` w Profilu może te formy z powrotem zablokować (precedencja:
`server.allow` > `server.deny` > allow kita > deny kita), a `server.guard: off`
dalej wyłącza cały guard.

**Sufit wyjątku.** `--no-build` w uv zatrzymuje budowanie zależności, ale nie
budowanie samego projektu: uv nadal czyta metadane workspace'u (PEP 517), więc
projekt z ciężkim backendem (maturin, scikit-build) może przy `uv lock` coś
skompilować. Dlatego aktualizacja locka nie jest gwarancją „zero kompilacji” —
jest gwarancją „bez instalacji zależności”. Gdy lock-only i tak padnie na buildzie
paczki (uv „no build”, odpowiednik npm/pnpm/bun), ticket traktuje się jak
blokujący deny z #315: etykieta `needs-local` i komentarz z nazwą paczki i powodem.
`pnpm install --lockfile-only` nadal wykonuje `.pnpmfile.cjs` projektu (hooki
`readPackage` / `afterAllResolved`) — `--ignore-scripts` tego nie blokuje; to kod
z repo, nie z rejestru, ale też część sufitu.

**Dopasowanie formy lock-only.** Wymagane flagi liczą się tylko przed pierwszym
samodzielnym `--` i przed komentarzem `#`; negacja (`--no-<flaga>`, `--<flaga>=false`,
uv `--build` / `--sync`) daje deny, podobnie `$`, `` ` ``, `\`, `{` i flagi w
cudzysłowach (powłoka mogłaby z nich zrobić `--` albo negację). Skutek uboczny
precedencji: `server.deny: "uv run"` blokuje teraz także `uv run --no-sync`.

**Yarn zostaje deny.** Yarn Berry ma `--mode=update-lockfile` (bez linkowania,
[`yarn install`](https://yarnpkg.com/cli/install)), ale Yarn Classic go nie zna,
a Berry nie ma `--ignore-scripts`; guard nie rozpoznaje wersji Yarn w projekcie,
więc bezpieczniejsza jest odmowa. Bun potwierdza oba tryby w
[oficjalnej dokumentacji `bun install`](https://bun.sh/docs/pm/cli/install)
(`--lockfile-only`, `--ignore-scripts`), dlatego dostał allow.

## Dlaczego wrappery rozwijane przy reload

Guard widzi tylko tekst komendy. `task test:backend` nie zawiera słowa `docker`,
choć task w środku odpala `docker-compose`. Dlatego `kit-ai reload` rozwija
Taskfile, skrypty `package.json` i `turbo run` do deny wrapperów z łańcuchem
powodu (`bun run build → turbo run build → next build`). Bez reloadu guard działa
na starej liście — README mówi to wprost.

## Wrappery wykonania: rtk

Osobna pułapka to `rtk` — globalna wtyczka, która przepisuje komendę po stronie
klienta. W opencode wtyczka RTK (`execute.before`) podmienia `input.command` na
`rtk rewrite <cmd>`, a plugin guardów kita działa po niej, więc widzi już
`rtk bun install`, a `next build` dociera jako `rtk next` — bez słowa `build`.
Reguła `bun-pkg` ani `next-build` nie ma wtedy czego dopasować.

Dlatego guard normalizuje `rtk` jak launcher, nie jak zwykły prefiks:

1. zdejmuje flagi rtk (`-v…`, `--ultra-compact`, `--skip-env`);
2. `rtk proxy|err|test|summary <cmd>` ocenia jako `<cmd>`;
3. `rtk run -c "<cmd>"` i cytowany argument ocenia jak `sh -c`; argumenty `run|err|test|summary` rtk skleja w linię powłoki, więc cytowany separator też dzieli komendę;
4. pozostałe `rtk X …` jako `X …`, plus tabela form, w których rtk zgubił
   znaczące słowo: `rtk next X` → `next build X`, `rtk npm X` → `npm X` i `npm run X`.

Deny działa więc niezależnie od tego, czy komenda dotarła do guarda przed
przepisaniem, czy po. W Claude Code hooki `PreToolUse` działają równolegle na
oryginalnym `tool_input`, więc guard widzi komendę sprzed RTK, a deny wygrywa
z `updatedInput`; normalizacja pokrywa ten sam przypadek bez osobnego testu
integracyjnego.

## Konsekwencje

- Jedno źródło profilu także dla agentów (#314): `kit-ai host` wypisuje wynik
  `detect_host_profile()` (z tym samym `KIT_HOST_PROFILE` / `GUIDES_HOST_PROFILE`),
  a `kit-ai night-ctx` składa z niego nagłówek CTX nocy ze znacznikiem generatora.
  Watchdog `/night-run` odrzuca nagłówek bez znacznika albo z `host=` różnym od
  bieżącego `kit-ai host` — nikt już nie wnioskuje Host z treści bundle'a.
- `vps-lightweight.md`: sekcja „Bez hooka blokującego" zastąpiona odwołaniem
  do server-guarda i tego ADR-a.
- Lokalne pluginy guardów w projektach stają się zbędne: podbij wersję kita,
  `kit-ai reload`, usuń własny plugin.
- Czego guard tekstowy nie złapie: agent zapisuje własny skrypt i go odpala.
  Dlatego README zaleca też higienę hosta (Playwright MCP wyłączony na serwerze,
  użytkownik agenta poza grupą `docker`, limit pamięci na sesję).
