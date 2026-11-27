# Przepływ jednej zmiany

Jedna zmiana, od pomysłu do PR, z komendami kita.

## Dziesięć kroków

1. (opcjonalnie) `/grill-me`, gdy scope jest niejasny.
2. `git-start`: issue i branch w konwencji `typ/N-slug`, np. `feat/42-add-cart-coupon`.
3. (opcjonalnie) worktree metodą kita: `node .ai/worktree.mjs add …`. Zob. [Managed Worktree](managed-worktree.md).
4. `get_bundle` i `get_overlay` przed pierwszą edycją.
5. Implementacja, opcjonalnie `/tdd`.
6. (opcjonalnie) `git-check`, gdy diff rozjechał się z issue.
7. `git-commit`: Conventional Commit(s) z lokalnego diffa.
8. `review-bugbot` i minimalny stack: `review-backend` i/lub `review-frontend`.
9. `git-end`: push i PR z `Closes #N` w body.
10. (opcjonalnie) Autopilot, aż CI będzie zielone.

## Dwie wersje

Krótko:

```text
git-start → kod → [git-check] → git-commit → review-bugbot → git-end → [Autopilot]
```

Długo:

```text
[grill-me] → git-start → worktree → kod → [git-check] → git-commit → finishing | git-end → Autopilot → merge
```

## Reguły procedur

- **Przed edycją kodu** agent wywołuje `get_overlay`, a `get_bundle`, gdy zadanie wskazuje moduł.
- **Commit przez `git-commit`**, nie ręcznie. Komunikat ma format Conventional Commit i język z Profilu.
- **Review przed pushem**, nie po. `git-guard` blokuje push na `main`, `master` i `dev`.
- **Nie wszystkie review naraz.** Minimalny zestaw zależy od zmiany. Zob. [Review](../komendy/review.md).
- **Niska pewność**: auth, ACL, płatności, migracje, concurrency albo brak dowodu w repo to pytanie do użytkownika. Nie naprawiaj na ślepo.
- **Merge robi człowiek** (`gh pr merge` albo UI). `git-end` nie merguje i nie zamyka issue. Issue zamknie się po merge dzięki `Closes #N`.

## Gdy nie wiesz, od czego zacząć

- Czy warto to robić? `create-task`: karta issue bez brancha.
- Jak to zrobić dobrze? `teacher-backend`, `teacher-frontend`, `teacher-architecture`.
- Zrobić to w nocy? Zob. [Praca nocna i headless](../komendy/praca-nocna-i-headless.md).
