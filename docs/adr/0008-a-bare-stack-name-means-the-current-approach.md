# A bare Stack name means its current approach, not a pinned version

`react` in a Profile means the current way of writing React (19+: actions, `use()`, the compiler) and `angular` means standalone components, signals and the new control flow. An older approach must be named explicitly as a Variant: `react@legacy`, `angular@rxjs`. Each Stack keeps its shared instructions in `overview.md` and the approach-specific ones in `modern.md` and `legacy.md`.

This is surprising on purpose. A committed Profile that says `react` will silently get different instructions when React 20 lands and `modern.md` is rewritten. That is the intent: a repo that wrote `react` without qualification is a repo being kept current, and the Kit's whole premise is instructions read live so they never go stale.

## Considered Options

Pinning versions (`react@19`, `angular@17`) makes a Profile reproducible and was the obvious alternative. We rejected it because every release would add a Variant, old ones would never be removable (ADR-0003 reasoning: the Kit cannot enumerate its consumers), and most repos would be pinned to a version nobody remembers choosing. Two named approaches per Stack is a set the Kit can actually maintain.

## Consequences

When a framework changes approach, the old `modern.md` becomes the new `legacy.md` — a repo that needs the old instructions has to say so. Detection signals (for example `react` below 19 in `package.json`) let `/kit-project-begin` suggest the `@legacy` Variant for an existing codebase instead of leaving it on the current one by default.
