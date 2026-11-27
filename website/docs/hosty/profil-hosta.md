# Profil hosta

**Host** to maszyna, na której działa agent. Kit rozpoznaje dwa profile: `local` i `vps`. Od profilu zależy, co agent może zrobić i które guardy są aktywne.

| | `local`: host lokalny | `vps`: serwer Linux |
|---|---|---|
| Kiedy | komputer dewelopera, Windows, macOS, WSL, CI | mały serwer Linux bez CI |
| Buildy i instalacje | dozwolone | zakazane poza lockfile |
| Moduł dodatkowy | brak | `infra:vps-lightweight` do każdego bundla |
| Server guard | nieaktywny | aktywny |

## Jak wykrywany jest VPS

Automatycznie, bez nazw hostów. Profil `vps` dostaje maszyna, która spełnia wszystkie warunki:

- Linux, bez CI,
- nie WSL,
- małe zasoby: CPU ≤ 2, RAM ≤ 8 GB, brak swapu,
- sygnał serwerowy: wirtualizacja (`systemd-detect-virt`) albo brak desktopu.

CI dostaje `local`, bo pełna weryfikacja należy do CI. Wyjątek: wymuszenie `KIT_HOST_PROFILE=vps` ma pierwszeństwo przed wykrywaniem CI.

## Sprawdzenie

```bash title="bash"
kit-ai host        # wypisuje: vps albo local
```

## Wymuszenie

Gdy heurystyka się pomyli, ustaw zmienną środowiskową **na tej maszynie**:

```bash title="~/.profile albo ~/.bashrc (Linux), Git Bash"
export KIT_HOST_PROFILE=vps        # alias: GUIDES_HOST_PROFILE
```

```powershell title="PowerShell (Windows): trwała zmienna użytkownika"
setx KIT_HOST_PROFILE local
```

Nie ustawiaj tego w repo. Profil w repo jest wspólny dla wszystkich maszyn. Gdybyś wyłączył guard w Profilu, wyłączyłbyś go też na VPS.

## Co zmienia profil `vps`

- `get_bundle` dokleja `infra:vps-lightweight` do każdego bundla. `get_index` pokazuje `Host: vps`.
- Server guard blokuje ciężkie komendy. Zob. [Server guard](server-guard.md).
- Reload zapisuje `UV_NO_SYNC=1` do `.claude/settings.local.json` tylko na VPS. Na `local` wpis kita jest zdejmowany, a ręczna wartość inna niż `1` zostaje.
- Brief w `AGENTS.md` nie zawiera hosta, żeby plik nie starzał się między maszynami. Host pojawia się tylko w instrukcjach MCP.

Podział na Windows i Linux: [Windows](windows.md), [Linux VPS](linux-vps.md).
