# Git: start, check, commit, end

Cztery komendy prowadzą jedną zmianę od issue do PR. Wymagają `gh` i `git`. Konwencja nazwy brancha to `typ/N-slug`, np. `feat/42-add-cart-coupon`.

## `git-start`

Tworzy issue i branch od gałęzi bazowej (z overlayu, zwykle `dev`).

```text
/kit-ai:git-start feat add cart coupon          # opis: tworzy issue i branch
/kit-ai:git-start fix #108 login returns 500    # istniejące issue
/kit-ai:git-start                               # bez argumentów: auto z lokalnego diffa
/kit-ai:git-start --help
```

Ręczny odpowiednik:

```bash title="Git Bash · bash"
gh issue create --title "Add cart coupon" --body "…"
gh issue develop 42 --name feat/42-add-cart-coupon --base dev --checkout
```

Branch możesz też założyć w UI GitHuba: Issue, Development, **Create a branch**. Nazwij go wtedy spójnie z `typ/N-slug`.

## `git-check`

Gdy praca poszła w inną stronę, tytuł i body issue przestają pasować do diffa. `git-check` dopasowuje je do realnych zmian. Tytuł pisze po angielsku, body w języku z Profilu. Opcja `--dry-run` pokazuje plan bez zapisu.

## `git-commit`

Tworzy Conventional Commit albo kilka commitów z lokalnego diffa.

| Flaga | Efekt |
|---|---|
| `--one` | jeden commit |
| `--split` | rozbija zmianę na logiczne commity |
| `--dry-run` | pokazuje plan bez commitowania |

Komenda odpala pre-commit, jeśli repo go ma. Treść commitu idzie w języku z Profilu.

## `git-end`

Robi push brancha i otwiera PR z `Closes #N` w body. PR idzie na gałąź bazową.

```text
/kit-ai:git-end --help
/kit-ai:git-end
```

Ręczny odpowiednik:

```bash title="Git Bash · bash"
git push -u origin HEAD
gh pr create --base dev --title "feat: add cart coupon" --body "Closes #42"
```

Czego `git-end` **nie** robi:

- nie merguje PR,
- nie zamyka issue od razu. Issue zamknie się po merge dzięki `Closes #N`.

Gdy drzewo jest brudne, najpierw uruchom `git-commit`.

## Ochrona gałęzi

`git-guard` blokuje force push i zwykły push na `main`, `master` i `dev`. Pracujesz na branchu roboczym. Zob. [Guardy: przegląd](../guardy/przeglad.md).

## Co dalej

Po PR możesz uruchomić Autopilot (w Cursorze). Dociąga CI i komentarze do zielonego stanu, bez auto-merge. Alternatywą dla `git-end` jest Superpowers `finishing-a-development-branch`. Wybierz jedno z dwóch.

Zob. też [Przepływ zmiany](../koncepcja/przeplyw-zmiany.md).
