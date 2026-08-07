# Language and code conventions (EN)

## Communication

- ALWAYS reply in English unless the user explicitly asks for another language.
- Applies to short in-progress status/narration lines too (e.g. "Now checking X", "Adding Y") — not only the final answer. File names, commands, code, and identifiers stay as-is.
- Be concrete, technical, and project-focused — no fluff.
- If something cannot be verified, say so plainly.

## Code

- Technical names in code are English: variables, functions, classes, types, files, endpoints, migrations, tests.
- Public docstrings (functions, classes, endpoints) — English (Google style, PEP 257).
- Logical comments — English, only when they explain non-trivial business logic.
- Type hints — required in new Python and TypeScript code.

## GitHub / git prose

- **Titles always English**: issue title, PR title, branch slug (`feat/42-add-cart-coupon`).
- Issue body, PR body, review comments, commit messages — English (this language setting).

## Change rules

- Prefer the smallest sensible local change over a large refactor.
- Keep separation of concerns and strong typing.
- Do not add abstractions without a real need.
- Watch testability, naming, performance, security, and regression risk.
