# Code review — lokalnie, GitHub, raporty

## Cel

Warstwowy pipeline review: szybkie bramki deterministyczne lokalnie, AI przed pushem, Bugbot na PR, CI przed merge.

## Warstwy (kolejność)

```text
1. pre-commit     → ruff, eslint (format + oczywiste błędy)
2. lokalny AI     → /review-bugbot lub /review-security w Cursor
3. commit + push
4. PR             → Bugbot na GitHub (automatycznie lub cursor review)
5. CI             → testy, typy, api-contract
6. merge          → branch protection + (opcjonalnie) review człowieka
```

Nie zastępuj testów review AI. AI łapie logikę i kontekst; CI łapie regresje.

## Lokalnie — przed commitem i pushem

### Komendy Cursor (3.7+)

| Skill | Kiedy |
|-------|-------|
| `/review-bugbot` | Domyślnie — bugi, logika, jakość |
| `/review-security` | Auth, płatności, uprawnienia, sekrety |
| `/review` | Wybór między Bugbot a Security |

**Zakres diffu:**

- Domyślnie `branch changes` — wszystko względem bazy (`main`), committed + uncommitted.
- `uncommitted changes` — tylko przed pierwszym commitem lub gdy chcesz wąski feedback.

**Sync z GitHub:** po lokalnym `/review-bugbot` i otwarciu PR z tym samym diffem Bugbot na GitHubie może pominąć ponowny review (ten sam patch ID).

### Cursor Hooks — przypomnienie przed `git push`

W projekcie skopiuj z instruction-kit:

- `.cursor/hooks.json`
- `.cursor/hooks/gate-push.sh`

Hook `beforeShellExecution` pyta o potwierdzenie przed `git push`, gdy są niepushnięte commity. Bypass: `SKIP_PUSH_REVIEW=1 git push`.

### Git pre-push (deterministyczne)

Szablon `templates/git-hooks/pre-push` — uruchamia testy/linty z Taskfile (jeśli istnieje). Nie uruchamia AI (wymaga Cursor IDE).

Instalacja w projekcie:

```bash
cp templates/git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

## GitHub — Bugbot

### Setup (jednorazowo)

1. Cursor Dashboard → Integrations → GitHub — podłącz org/repo.
2. Bugbot dashboard — włącz repo.
3. (Opcjonalnie) Branch protection — wymagaj check `Cursor Bugbot` + CI.

### Trigger na PR

- Automatycznie przy każdym push do PR.
- Ręcznie: komentarz `cursor review` lub `bugbot run`.
- Verbose: `cursor review verbose=true`.

### Check status

| Status | Znaczenie |
|--------|-----------|
| `success` | Brak findings + brak nierozwiązanych komentarzy Bugbota |
| `neutral` | Są findings lub run anulowany (domyślne przy findings) |
| `failure` | Fail-on-unresolved włączone i są nierozwiązane issues |

Aby blokować merge przy findings — włącz fail-on-unresolved w ustawieniach Bugbota (jeśli dostępne dla org).

### Autofix

Bugbot może spawnować Cloud Agent i pushować fix na branch lub nowy branch. Konfiguracja w Bugbot dashboard.

## Reguły review — `.cursor/BUGBOT.md`

Bugbot ładuje reguły w kolejności: Team Rules → repo rules → `.cursor/BUGBOT.md` (root + nested przy changed files) → User Rules.

Szablon dla projektów: `templates/cursor/BUGBOT.md`.

Przykłady reguł (dashboard lub BUGBOT.md):

- Zmiana `backend/**` bez testów → blocking bug.
- Zmiana serializerów/viewsetów bez `task ovral:generate` → blocking bug.
- `eval()`, `exec()`, hardcoded secrets → blocking bug.
- Import GPL w lockfile → compliance bug.

Uczenie inline: `@cursor remember [fakt]` w komentarzu PR.

## Raporty

| Źródło | Co dostajesz |
|--------|--------------|
| Cursor po `/review-bugbot` | Tabela: Severity, Location, Finding |
| GitHub PR | Komentarze inline + check status |
| Bugbot dashboard | Analytics, acceptance rate, rule performance |
| Bugbot API (Enterprise) | `POST /bugbot/review` + `GET /analytics/team/bugbot-reviews` |

**Dry-run API** (`dryRun: true`): pełna analiza bez publikacji na PR — raport w analytics, billing jak normalny run.

## Integracja z CI (ten sam repo)

W `arch:ci-cd` masz joby lint/test/typecheck. Bugbot **uzupełnia** CI, nie go zastępuje.

Rekomendowany branch protection:

```text
Wymagane checks:
  - backend-test (lub odpowiednik z Taskfile)
  - frontend-types
  - api-contract (gdy PR dotyka API)
  - Cursor Bugbot (opcjonalnie, soft lub hard)
```

## Kiedy który review

| Zmiana | Minimum |
|--------|---------|
| Drobna poprawka, 1–2 pliki | lint + typecheck |
| Feature / refactor | `/review-bugbot` przed pushem |
| Auth, ACL, płatności, webhooki | `/review-security` + Bugbot na PR |
| Kontrakt API | lint + `task ovral:generate` + api-contract CI |
| Merge do main | CI green + Bugbot + (opcjonalnie) człowiek |

## Pliki do skopiowania z instruction-kit

```text
templates/cursor/BUGBOT.md
templates/cursor/hooks.json
templates/cursor/hooks/gate-push.sh
templates/git-hooks/pre-push
```

W projekcie docelowym:

```text
.cursor/BUGBOT.md          ← dostosuj do stacku
.cursor/hooks.json
.cursor/hooks/gate-push.sh
.git/hooks/pre-push        ← opcjonalnie, z szablonu
```

## Powiązane

- `core:workflow` — tryby bugfix/feature/refactor
- `arch:ci-cd` — joby CI i branch protection
