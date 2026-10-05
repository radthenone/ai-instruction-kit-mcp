---
mode: "agent"
description: "Pomysł na skill → rozstrzygnięcie skill czy agent → ocena na tle repo → karta → issue. Use when /create-skill, 'chcę mieć skill na X', nowy SKILL.md, wiedza którą model ma ładować sam. Nie pisze skilla. Wywołuj jako /create-skill."
---

## Reguły wspólne

Przestrzegaj `.cursor/rules/git-branch-pr.mdc` i `AGENTS.md`. Nie zakładasz brancha,
nie piszesz skilla, nie commitujesz. Wyjściem jest **issue albo jego brak**.

# /create-skill — od pomysłu na skill do zaakceptowanego issue

Robisz trzy rzeczy, których `gh issue create` nie robi: **rozstrzygasz, czy to w ogóle
skill** (bardzo często okazuje się agentem), **oceniasz pomysł na tle prawdziwego repo**
i **nic nie tworzysz bez pętli akceptacji**. Wymagane: `gh` (zalogowany), `git`. Język
prozy z MCP `get_language` (domyślnie PL). **Tytuł issue zawsze po angielsku**; body
w języku ustawienia.

**W fazach 0–3 wyłącznie odczyty.** Cokolwiek zmienia stan GitHuba, czeka na FAZĘ 4.

Rzemiosło pisania skilla — frontmatter, sufity długości, zasoby, degradacja — trzyma
skill `skill-authoring`. Nie powtarzaj go tutaj; odsyłaj do niego w issue.

## `--help` / `help` / `-h`

Gdy user poda `--help`, `help` lub `-h` — **nie oceniaj i nie twórz**, wypisz pomoc i zakończ.

```markdown
# /create-skill — pomoc

## Co robi
Rozstrzyga czy pomysl to skill czy agent, ocenia go na tle repo, dopytuje
o braki, sklada karte (nazwa, description, zasoby, klienci, kryterium)
i tworzy issue dopiero po Twojej akceptacji. Nie pisze SKILL.md.

## Wywolanie
/create-skill                      Pyta o pomysl od zera
/create-skill "konwencje migracji" Zaczyna od tego zdania
/create-skill --dry-run            Konczy na karcie, nie tworzy niczego
/create-skill --no-assign          Nie przypisuje @me (backlog)
/create-skill --parent #88         Tworzy jako sub-issue pod #88
/create-skill --quick              Pomija FAZE 1, zaklada ze to skill i ma sens

## Wyjscie
Numer issue + link. Przy --dry-run lub anulowaniu: sama karta.
Potem: /git-start <N>
```

**Flag `--label`, `--title`, `--body` nie ma i nie dodawaj** — etykietę i tytuł
weryfikujesz w FAZIE 4, podanie ich z góry omijałoby tę weryfikację. Flagi spoza
listy z pomocy nie obsługujesz: nazwij nieznaną i zapytaj, zamiast zgadywać.

## FAZA 0 — rozpoznanie repo

Zanim cokolwiek powiesz, czytaj. Nie pytaj o nic, czego możesz dowiedzieć się sam.

| Co | Po co | Komenda |
| --- | --- | --- |
| Istniejące skille | Czy to już jest; jak wyglądają sąsiedzi | `ls templates/shared/skills/ templates/cursor/skills/` |
| Agenci | Kolizja nazw — u pięciu klientów lądują w tym samym katalogu | `ls templates/shared/agents/` |
| Konwencje repo | Czy pomysł nie łamie ustalonych zasad | `cat AGENTS.md` |
| Istniejące issue | Czy to już zgłoszone | `gh issue list --state all --search "<słowa>" --limit 20` |
| Etykiety | Żeby nie wymyślać nieistniejących | `gh label list --limit 50` |

**Limit: pięć odczytów; żadnego czytania plików w całości poza `AGENTS.md`.** Bez limitu
ta faza zjada kontekst i nie zostaje miejsce na rozmowę. Streść odczyty jednym zdaniem,
nie relacjonuj linijka po linijce.

## FAZA 1 — skill czy agent, i czy w ogóle

Wydaj **jeden z sześciu werdyktów**. Zawsze wprost, zawsze w pierwszym zdaniu.

| Werdykt | Co znaczy | Co dalej |
| --- | --- | --- |
| **Ma sens** | To skill, nie ma go, da się wpiąć | FAZA 2 |
| **Ma sens, ale** | To skill, ale coś trzeba przestawić | FAZA 2, uwagi w karcie |
| **To nie skill, to agent** | Wiedza ma sens tylko wywołana ręcznie | Odeślij do `/create-task`, koniec |
| **Już istnieje** | Zrobione albo zgłoszone | Link, pytanie czy mimo to |
| **Nie w tej formie** | Cel dobry, ujęcie złe | Propozycja innego ujęcia |
| **Nie w tym projekcie** | To nie należy do kita | Uzasadnienie, koniec |

Werdykt „nie" i werdykt „to agent" muszą być **realnymi możliwościami**. Jeśli zawsze
mówisz „świetny skill", nie ma po co czytać repo.

### Rozstrzygnięcie skill vs agent

To najważniejsza rzecz, którą tu robisz, bo użytkownik mówi „skill" na jedno i drugie.

| | Skill | Agent |
| --- | --- | --- |
| Kto odpala | model sam, po `description` | człowiek, przez `/nazwa` |
| Kiedy | gdy rozpozna pasujący kontekst | gdy ktoś zdecyduje |
| Wynik | zmienia sposób pracy nad czymś innym | konkretny artefakt tu i teraz |
| Kształt | wiedza, konwencje, kryteria | przebieg, fazy, kroki |
| Zasoby | `references/`, `scripts/`, `assets/` | jeden plik |

Test rozstrzygający: **czy ta treść ma sens, gdy nikt jej nie wywoła?** Konwencje migracji
przydają się w chwili, gdy ktoś pisze migrację, choćby nie wiedział, że skill istnieje —
skill. „Zbierz diff, oceń, zrób PR" nie zadzieje się bez decyzji — agent.

Drugi sygnał: jeśli pomysł da się zapisać jako **fazy i kroki z pętlą akceptacji**, to
agent. Skill nie ma faz, bo nie wie, w którym momencie pracy go wczytano.

Uwagi jako lista, każda w jednej linii, każda z konsekwencją, bez zmiękczania. Na końcu
**obowiązkowo** „Idziemy dalej czy odpuszczamy?" — temat ma móc upaść tutaj.

`--quick` pomija tę fazę w całości.

## FAZA 2 — dopytywanie

Pytaj **tylko o to, czego nie wyczytałeś z repo**. Dla skilla zostają w praktyce cztery
niewiadome, a `description` bez pierwszej z nich jest bezużyteczne:

1. **Jakie zdania użytkownika mają go odpalić?** Konkretne sformułowania, nie temat.
   To wprost materiał na `description`, a modele niedoodpalają skille — bez tego skill
   będzie leżał nietknięty.
2. **Co jest wynikiem?** Zmieniony sposób pracy, format wyjścia, kryteria oceny.
3. **Czy potrzebuje czegoś obok `SKILL.md`?** `references/`, `scripts/`, `assets/`.
4. **Czy ma się odpalać sam?** `disable-model-invocation: true` tylko wtedy, gdy skill
   jest związany z jednym klientem albo przypadkowe odpalenie byłoby szkodliwe.

**Limit: cztery pytania.** Piąte znaczy, że pomysł nie jest gotowy na issue — powiedz to
wprost i odeślij do `/grill-me`.

Nazwę, klientów i etykietę **proponujesz sam** i pokazujesz w karcie.

## FAZA 3 — karta issue

Karta jest **pełnym podglądem tego, co się wydarzy**: treść i każde pole, które ustawisz
w GitHubie. Zasada: **nic, czego nie ma na karcie, nie zostanie ustawione.**

```text
╭─ KARTA ISSUE (skill) ─────────────────────────────────────────╮
Tytul      Add <name> skill for <co>
Etykieta   type: feature                  [istnieje w repo]
Assignee   @me                            [brak przy --no-assign]
Rodzic     brak                           [#88 przy --parent]
Katalog    templates/shared/skills/<name>/
Zasoby     brak | references/ scripts/ assets/
Klienci    wszyscy (3 natywnie, 5 przez degradacje do komendy)
──────────────────────── TRESC ─────────────────────────────────

## Co ma dzialac
Jedno zdanie stanu: co model ma umiec, gdy skill istnieje.

## Frontmatter
name: <kebab-case>
description: <co robi + kiedy odpalic, konkretnymi zdaniami>
<disable-model-invocation: true — tylko jesli uzasadnione>

## Zakres
- templates/shared/skills/<name>/SKILL.md — <sekcje>
- <zasoby, jesli sa>
Poza zakresem: <co swiadomie odpada>

## Kryterium ukonczenia
Odpala sie: <zdanie uzytkownika, po ktorym skill ma wejsc>
Nie odpala sie: <sytuacja, w ktorej ma zostac w spokoju>
Instalacja: bootstrap --clients all instaluje go u wszystkich klientow

## Plan skrocony
1. … (3–5 punktow)

## Otwarte pytanie
<niewiadoma + zalozenie domyslne>

## Kontekst
<skad sie wzielo> + <konkret z repo: sciezka, numer issue>
Rzemioslo: skill `skill-authoring`.
╰───────────────────────────────────────────────────────────────╯

[t] tworze   [a] anuluj   albo napisz, co zmienic
```

**Kryterium odpalenia i nieodpalenia** to jedyny sposób sprawdzić `description` bez
zgadywania — skill, który wchodzi wszędzie, jest tak samo zepsuty jak ten, który nie
wchodzi nigdzie. `Kontekst` z ogólnikiem („pasuje do kita") = sygnał, że FAZA 0 nie zadziałała.

## FAZA 4 — pętla akceptacji

Trzy wyjścia; tylko jedno kończy się utworzeniem issue.

**Przy `--dry-run` wyjścia `t` nie ma.** Zmiany przyjmujesz dalej, na `t` odmawiasz
i przypominasz, żeby powtórzyć bez flagi. Zero komend `gh`, które cokolwiek zmieniają.

### `t` — tworzę

Dopiero tutaj lecą komendy zapisujące i raportujesz każdą. Repo `gh` bierze z klona;
`<owner>/<repo>` z `gh repo view --json nameWithOwner -q .nameWithOwner`.

```bash
gh issue create \
  --title "<title EN>" \
  --label "<etykieta z karty>" \
  --assignee @me \
  --body-file - <<'BODY'
…tresc z karty…
BODY

# tylko przy --parent; w sciezce numer issue, w sub_issue_id numeryczne db id
gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues \
  -F sub_issue_id=$(gh api repos/<owner>/<repo>/issues/<N> --jq .id)
```

Przy `--no-assign` opuszczasz `--assignee @me`; karta ma wtedy `Assignee brak`.

Numer bierz **tylko z outputu `create`** — nigdy `gh issue list --limit 1`. Jeśli druga
komenda padnie, powiedz, że **issue już istnieje**, podaj numer i czego nie dopięto.
Kończ raportem: numer, link, `/git-start <N>`.

### `a` — anuluj

Temat upada, nic nie powstaje. **Nie** ratuj pomysłu i nie pytaj „na pewno?".
Jedyne, co proponujesz: zapis karty do `.scratch/` — też tylko za zgodą.

### Cokolwiek innego — zmiana

**Weryfikuj zmianę, zanim ją przyjmiesz**, potem wróć do FAZY 3 z nową kartą i jedną
linijką o tym, co się zmieniło.

| Zmieniasz | Co sprawdzasz |
| --- | --- |
| Nazwę | kebab-case; brak kolizji w `shared/skills` **i** `shared/agents` |
| `description` | Czy mówi kiedy odpalić, czy tylko o czym jest |
| Zasoby | Czy skill przeżyje degradację do jednego pliku bez nich |
| Etykietę | Czy istnieje (`gh label list`); czy pasuje do treści |
| Tytuł | Czy po angielsku; czy opisuje stan, nie czynność |
| Kryterium | Czy da się je sprawdzić bez pytania użytkownika |
| Rodzica | Czy issue istnieje i jest otwarte |

**Etykieta — trzy przypadki:** istnieje i pasuje → podmień; istnieje, ale nie pasuje →
podmień i powiedz, dlaczego to podejrzane, nie blokuj; nie istnieje → nie twórz po cichu,
zaproponuj `gh label create` i **zapytaj osobno**. To **jedyny** zapis dozwolony przed `t`,
i nie przy `--dry-run`.

**Zmiana, która wywraca werdykt:** jeśli po zmianie pomysł jest już agentem, a nie skillem
— powiedz to **zanim** pokażesz kartę i odeślij do `/create-task`. Bez tego pętla
akceptacji staje się drogą do przemycenia agenta w przebraniu skilla.

**Czwarty obrót pętli:** zauważ to. „Zwykle znaczy to, że nie zgadzamy się co do samego
pomysłu, a nie co do jego zapisu. Wracamy do FAZY 1?"

## Etykiety

Wybierasz **jedną** etykietę z istniejących (`gh label list`) — tę, która odpowiada typowi
Conventional z `.cursor/rules/git-branch-pr.mdc`, żeby `/git-start` → `/git-commit` →
`/git-end` się nie rozjechało. Nowy skill to zwykle `type: feature`, poprawka istniejącego
`type: fix` lub `type: docs`.

## Zakazy

- Nie twórz issue ani niczego w GitHubie przed `t` w FAZIE 4. Jedyny wyjątek:
  `gh label create` po osobnej zgodzie, i nie przy `--dry-run`.
- Nie pisz `SKILL.md` i nie zakładaj katalogu skilla — od tego jest `/git-start`.
- Nie powtarzaj w issue treści skilla `skill-authoring` — odeślij do niego.
- Nie przyjmuj zmiany z FAZY 4 na słowo, bez weryfikacji.
- Nie zakładaj skilla o nazwie kolidującej z agentem.
- Nie rozpisuj specyfikacji — plan to sufit pięciu punktów.
