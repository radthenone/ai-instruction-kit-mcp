<!-- lang:pl -->
## Klasyfikacja zadań i reguły MCP (#307, #324)

- **Zadanie kodowe:** tworzenie, edycja lub debug plików w `src/`, `tests/`, `templates/`, `modules/`; implementacja, testy, refactor, pytanie o zachowanie kodu do zmiany.
- **Zadanie proceduralne:** każdy slash command z procedury kita (`/git-*`, `/review-*`, `/create-task`, `/create-skill`, `/night-run`, `/headless`, `/tdd`, `/kit-project-*`) oraz każda czynność zapisu na GitHub.
- **Wymóg wywołania:** przed pierwszą edycją przy zadaniu kodowym lub proceduralnym wywołaj `get_overlay`, a `get_bundle` gdy brief wskazuje moduł. W wątpliwości wywołaj `get_overlay` (koszt mały, błędny fix bez overlay kosztuje dużo).
- **Bez wywołań MCP:** pytania o język, bazę lub Tiery (są w briefie), rozmowa, wyjaśnienie, odpowiedź tekstowa bez zmiany plików.
- **Docstringi:** format repo (Args/Returns, {{docstring_language|po polsku}}).
- **VPS (#317):** na hoście VPS zakaz instalacji pakietów i buildów poza lockfile-only (`uv lock --no-build`, `npm install --package-lock-only --ignore-scripts`).
<!-- /lang:pl -->

<!-- lang:en -->
## Task classification and MCP rules (#307, #324)

- **Coding task:** create, edit or debug files in `src/`, `tests/`, `templates/`, `modules/`; implementation, tests, refactor, questions on code behavior to change.
- **Procedural task:** any kit slash command (`/git-*`, `/review-*`, `/create-task`, `/create-skill`, `/night-run`, `/headless`, `/tdd`, `/kit-project-*`) and any GitHub write action.
- **Require calling:** require calling `get_overlay` before first edit (and `get_bundle` when brief points to module); when in doubt call `get_overlay` (small cost, wrong fix without overlay costs a lot).
- **No MCP calls:** questions about language, base or Tiers (are in the brief), conversation, explanation, text response without file edits.
- **Docstrings:** repo format (Args/Returns, {{docstring_language|in English}}).
- **VPS (#317):** on VPS host package installs and builds are denied except lockfile-only (`uv lock --no-build`, `npm install --package-lock-only --ignore-scripts`).
<!-- /lang:en -->

<!-- hook:pl -->
Klasyfikacja zadań i reguły MCP (#307, #324): Zadanie kodowe (tworzenie, edycja lub debug plików w src/, tests/, templates/, modules/; implementacja, testy, refactor, pytanie o zachowanie kodu do zmiany) lub proceduralne (każdy slash command kita: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, oraz każda czynność zapisu na GitHub): wymóg wywołania get_overlay przed pierwszą edycją (a get_bundle gdy brief wskazuje moduł); w wątpliwości wywołaj get_overlay (koszt mały, błędny fix bez overlay kosztuje dużo). Pytania o język, bazę, Tiery i rozmowa bez zmian plików — bez wywołań MCP (#307). Docstringi w formacie repo (Args/Returns, {{docstring_language|po polsku}}). Na hoście VPS zakaz instalacji pakietów i buildów poza lockfile-only (#317, np. uv lock --no-build, npm install --package-lock-only --ignore-scripts).
<!-- /hook:pl -->

<!-- hook:en -->
Task classification and MCP rules (#307, #324): Coding task (create, edit or debug files in src/, tests/, templates/, modules/; implementation, tests, refactor, questions on code behavior to change) or procedural task (any kit slash command: /git-*, /review-*, /create-task, /create-skill, /night-run, /headless, /tdd, /kit-project-*, and any GitHub write action): require calling get_overlay before first edit (and get_bundle when brief points to module); when in doubt call get_overlay (small cost, wrong fix without overlay costs a lot). Questions about language, base, Tiers and conversation without file edits — no MCP calls (#307). Docstrings in repo format (Args/Returns, {{docstring_language|in English}}). On VPS host package installs and builds are denied except lockfile-only (#317, e.g. uv lock --no-build, npm install --package-lock-only --ignore-scripts).
<!-- /hook:en -->
