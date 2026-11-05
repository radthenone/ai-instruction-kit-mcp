# The brief is a rendered artifact; its rules are copied from one template

The rules of the Brief (task classification, `get_overlay` before editing, docstring format, the no-install rule on VPS) live in one template under `templates/shared/rules/`, with the Profile's `language` filled in. `kit-ai reload` renders that template into the per-turn language hook (`language-reminder.mjs`, for every language, Claude only) and the Kit-owned section of the committed `AGENTS.md` (`<!-- kit:brief-rules -->`), which every Client reads. For the MCP carrier (`_INSTRUCTIONS_RULES`), because the server lives in the Kit package shared across workspaces, the rules are rendered at Kit build time into a generated module (`src/guides/brief_rules.py`) with `pl` and `en` variants, and at runtime the server selects the variant matching the workspace Profile's `language` (ADR-0010 variant a, #355). The Overlay is never pasted into any of them: it stays in `.ai/project.md` and reaches the agent through `get_overlay`. The runtime does not read the template; the hook and the server carry only pre-rendered text, so a missing template path in a consuming repo cannot break them.

This is a deliberate exception to the rule that instruction text is never copied into a consuming repo (see `CONTEXT.md`). The rules are short and versioned, and copying them is the only way a hook and `AGENTS.md` can carry them to Clients that run without the MCP server. We rejected the alternative — the hook and `AGENTS.md` hold only a pointer to the MCP — because a hook without rule text cannot remind the agent of anything, and the language rule was being skipped when it lived only in one-time session context.

## Considered Options

- Keep copies in four places and check parity with a test. Rejected: the copies already drifted (docstrings, the priority paragraph exists only in the hook), and a parity test reports the drift after it happens instead of preventing it.
- Read the template at runtime from the hook and the server. Rejected: it makes the hook depend on a path inside the consuming repo, and the Kit does not own that path.
- Paste the full Overlay into the Brief. Rejected: it duplicates `.ai/project.md` and goes stale after an edit until the next reload.
- Render MCP instructions during consuming repo's `kit-ai reload`. Rejected: `src/guides/server.py` is in the installed Kit package and cannot be rewritten by a consumer reload. Instead, a generated module with `pl` and `en` variants is baked into the package, selected by the Profile's `language`.

## Consequences

- A freshness test renders the template and compares it with the generated files; a hand edit in a generated file fails CI.
- The Bootstrap Stamp records the Kit commit that produced the copied rules, so drift is visible without reading instruction text.
- The `language: en` hook is kept and rendered with English rules. The Bootstrap step that deletes the hook for `en` goes away.
- `get_language` stays as a read tool but is no longer an instructed step; the language arrives in the rendered rules.
