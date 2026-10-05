---
mode: "agent"
description: "Jak napisać skill do instruction-kit: frontmatter, opis który faktycznie odpala, sufit długości, zasoby obok SKILL.md i degradacja u klientów bez natywnych skilli. Użyj tego zawsze, gdy piszesz albo poprawiasz SKILL.md, realizujesz issue założone przez /create-skill, zastanawiasz się czy coś ma być skillem czy agentem, albo gdy skill nie odpala się mimo że powinien."
---

# Pisanie skilla w instruction-kit

Skill to wiedza, którą model **sam** ładuje, gdy rozpozna, że pasuje do sytuacji.
Agent (`templates/shared/agents/*.md`) to przeciwieństwo: jeden przebieg, odpalany
ręcznie przez `/nazwa`, z wynikiem tu i teraz. Jeśli twoja treść ma sens tylko wtedy,
gdy ktoś ją wywoła — to agent, nie skill.

## Gdzie to mieszka

```text
templates/shared/skills/<nazwa>/
├── SKILL.md          wymagany
├── references/       dokumenty czytane na żądanie
├── scripts/          kod do odpalenia, nie do wczytania
└── assets/           pliki lądujące w wyniku (szablony, ikony)
```

`<nazwa>` jest kebab-case i to **ona** nazywa komendę u klientów bez natywnych
skilli — nie pole `name:` z frontmatter. Trzymaj oba zgodne, żeby skill nazywał
się tak samo wszędzie.

Nazwa nie może kolidować z agentem z `templates/shared/agents/` — u pięciu klientów
obie rzeczy lądują w tym samym katalogu komend i druga nadpisze pierwszą.

## Frontmatter

```yaml
---
name: <kebab-case, ten sam co katalog>
description: >-
  <co robi> + <kiedy to odpalić>
disable-model-invocation: true   # opcjonalnie
---
```

`description` to **jedyny** mechanizm odpalania. Model widzi zawsze tylko `name`
i `description`; treść czyta dopiero, gdy zdecyduje, że skill pasuje. Cała
informacja „kiedy tego użyć" musi więc być tutaj, nie w treści.

Modele mają skłonność do **niedoodpalania** skilli — pomijają je w sytuacjach,
w których byłyby przydatne. Dlatego opis pisz napastliwie: wymień konkretne
zdania i konteksty, nie tylko temat. Zamiast „Konwencje migracji bazy" napisz
„Konwencje migracji bazy. Użyj zawsze, gdy pojawia się migracja, zmiana schematu,
`alembic`, `makemigrations` albo pytanie o kolejność wdrożenia — także wtedy, gdy
użytkownik nie użyje słowa »migracja«."

`disable-model-invocation: true` wyłącza automatyczne odpalanie i zostawia tylko
wywołanie ręczne. Ustaw to wyłącznie wtedy, gdy skill jest związany z jednym
klientem albo jego przypadkowe odpalenie byłoby szkodliwe — jak
`templates/cursor/skills/compact/`, który dotyczy tylko Cursora.

## Trzy poziomy ładowania

| Poziom | Co | Kiedy w kontekście |
| --- | --- | --- |
| Metadane | `name` + `description` | zawsze |
| Treść `SKILL.md` | całe ciało pliku | gdy skill odpali |
| Zasoby | `references/`, `scripts/`, `assets/` | gdy treść po nie odeśle |

Z tego wynika cała ekonomia pisania: metadane płacisz zawsze, więc mają być krótkie
i celne; treść płacisz przy każdym odpaleniu, więc trzymaj ją poniżej ~500 linii;
zasoby nie kosztują nic, dopóki nikt po nie nie sięgnie.

Gdy `SKILL.md` puchnie ponad ten sufit, nie tnij treści — przenieś ją do
`references/` i zostaw w `SKILL.md` jedno zdanie o tym, **kiedy** tam zajrzeć.
Plik referencyjny powyżej 300 linii zaczynaj spisem treści, inaczej model wczyta
całość, żeby znaleźć jeden akapit.

Przy wielu wariantach jednej rzeczy organizuj przez katalog, nie przez rozrost
treści:

```text
cloud-deploy/
├── SKILL.md          wybór wariantu + wspólny przebieg
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

## Jak pisać treść

Tryb rozkazujący, adresowany do modelu, który już zdecydował, że skill pasuje.
Nie powtarzaj w treści warunków odpalenia — to robota `description`.

Wyjaśniaj **dlaczego**, nie tylko **co**. Reguła z uzasadnieniem przeżywa kontakt
z sytuacją, której nie przewidziałeś; sama komenda nie. Stosy wielkich liter
i „MUSISZ" nie zastępują powodu.

Gdy skill ma produkować konkretny kształt wyniku, pokaż go dosłownie:

```markdown
## Struktura raportu
Zawsze dokładnie ten szablon:
# [Tytuł]
## Podsumowanie
## Ustalenia
## Rekomendacje
```

Przykłady wpisuj jako pary wejście/wyjście — jedna para konkretna warta jest
trzech akapitów opisu.

Pisz ogólnie na tyle, żeby skill przeżył zmianę przykładu. Skill zbudowany wokół
jednego pliku z repo umiera przy pierwszym refaktorze.

## Zasada braku zaskoczenia

Skill nie może robić niczego, czego nie zapowiada jego opis. Żadnego kodu, który
sięga poza zadeklarowany zakres, wysyła dane na zewnątrz albo obchodzi bramki
projektu. Skill opisany zdaniem musi dać się z tego zdania w całości przewidzieć.

## Co się stanie z twoim skillem u innych klientów

`scripts/install_shared_skills.py` rozkłada `templates/shared/skills/` na osiem
klientów. Cztery czytają skille natywnie, cztery nie mają takiego formatu:

| Klient | Gdzie ląduje | Jak działa |
| --- | --- | --- |
| claude | `.claude/skills/` | natywnie, z zasobami |
| cursor | `.cursor/skills/` | natywnie, z zasobami |
| antigravity | `.agents/skills/` | natywnie, z zasobami |
| codex | `.codex/skills/` | natywnie, z zasobami |
| vscode | `.github/prompts/` | degradacja: komenda `/nazwa` |
| kiro | `.kiro/agents/` | degradacja: komenda `/nazwa` |
| kilo | `.kilocode/workflows/` | degradacja: komenda `/nazwa` |
| opencode | `.opencode/command/` | degradacja: komenda `/nazwa` |

Degradacja ma dwa skutki, z którymi trzeba pisać: skill przestaje odpalać się sam
(ktoś musi wpisać `/nazwa`) i **gubi wszystko poza `SKILL.md`** — komenda to jeden
plik. Skill, którego sens leży w `scripts/`, będzie w połowie klientów wydmuszką.
Jeśli tak wychodzi, przemyśl, czy to nie powinien być agent.

Instalator ostrzega o gubionych katalogach na stderr. Traktuj to ostrzeżenie jako
sygnał projektowy, nie szum.

## Zanim uznasz skill za skończony

- `description` mówi **kiedy** odpalić, konkretnymi zdaniami użytkownika
- `name` == nazwa katalogu i nie koliduje z agentem
- `SKILL.md` poniżej ~500 linii, nadmiar w `references/`
- treść nie powtarza warunków odpalenia
- skill przeżywa degradację do jednego pliku, albo świadomie z niej rezygnuje
- `bootstrap-project.sh --clients all` instaluje go u wszystkich ośmiu klientów
