# `/review-tests` — weryfikator dowodu

> Prywatne notatki z użycia. Źródło: `.claude/commands/review-tests.md`.
> Format wspólny i ściąga kogo wołać: [review-bugbot](review-bugbot.md).

**Weryfikator dowodu, nie drugi stylista.** Jedyny, który sprawdza, czy zdanie
„zrobione i przetestowane" jest prawdziwe.

Procedura: ustal co uznano za zrobione → z `get_overlay()`/Taskfile wypisz
**konkretne** komendy → uruchom je → sprawdź, czy nowe zachowanie ma test **na
publicznym seamie**, a nie tylko czy plik `test_*.py` istnieje.

Zwraca dodatkowo krótką sekcję:

```text
Zweryfikowano: ...
Nieudowodnione / czerwone: ...
```

**Najważniejsza jego cecha:** jak nie może uruchomić komendy, **mówi to wprost**
zamiast napisać „pewnie przechodzi". To jedyny reviewer, który pilnuje, żebym
nie uwierzył we własną deklarację.

**Pułapka:** traktowanie `/review-tests` jak stylisty. On nie ocenia nazw ani
layoutu. Pytam go o dowód, nie o opinię.

**Kiedy:** po każdym „zrobione", przed [git-end](git-end.md).
