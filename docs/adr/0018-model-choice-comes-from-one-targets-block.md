# Model choice comes from one Profile block, `targets`; the old model keys are not read

Which model each kit agent runs on, and which model and options a T3 Code delegation receives, is recorded in one block of the Workspace Profile: `targets.<client>.<model tier>`. Each entry holds `providerInstanceId`, `model` and `options`. Bootstrap reads the block when it writes agent files for Claude Code, and the T3 night-run card reads it when it delegates a task. The `models:` block and the `t3.targets` block are not read. A Profile that still has either one fails reload with a message that names the migration. Before this decision the same choice came from both, and the two already disagreed: the kit's standard tier ran on `sonnet`, while T3's ran on `claude-haiku-5-5`. Design discussion and implementation: #515.

The model tiers are `light`, `standard` and `heavy`, which agent templates already set through `model-tier:`, plus `takeover`, which a client may set. Without an entry, takeover is a copy of that client's `standard` entry. A tier with no entry writes no `model:`, so Claude Code picks the model through its subagent model order: a `model` passed on the Agent call, then `CLAUDE_CODE_SUBAGENT_MODEL` when set, otherwise the model of the agent that started it (the session model for a top-level subagent). "Session model" below means this default.

For Claude, bootstrap writes `model:` and `effort:` into the frontmatter of `.claude/agents/*.md`. For OpenCode, it writes `model: <provider/model>#<variant>` into `.opencode/commands/kit-ai/*.md` (komendy kitu pod prefiksem `kit-ai`, #527), because OpenCode takes the variant as a suffix on the model name and has no separate key; without a `variant` option it writes the plain `model: <provider/model>`. Codex and Antigravity get no files; their targets are used only by T3 Code.

Options are written inline as `options: [{ id, value }]`, the shape T3 Code uses. The parser reads that without PyYAML, because bootstrap runs on the system Python.

Structural errors in the block stop reload with a message that names the entry: an unknown client or tier, a field other than `providerInstanceId`, `model` or `options`, an entry without `providerInstanceId`, an empty `model`, options written outside the inline form, a client with neither `standard` nor `takeover` (there is no `standard` to copy), and an agent in two tiers. The kit does not yet validate option values (for example the Claude `effort` level); a value is written as given. [ADR-0004](0004-unknown-decisions-are-reported-not-fatal.md) still covers unrecognised decisions elsewhere in the Profile.

[ADR-0013](0013-agent-classification-and-ponytail-matcher.md) is unchanged. It makes the agent `classification` a required field that fails bootstrap and reload when missing. Model tiers are optional, and a missing one has a safe default, the session model, so that stricter rule does not apply to them.

Takeover: the Agent tool takes `model` as an alias only. For Claude, the alias is derived from the model id of `targets.claude.takeover`: `claude-haiku-*` gives `haiku`, and likewise `sonnet`, `opus` and `fable`. An unknown id means the session model. A client may set a takeover entry in the full shape (`providerInstanceId`, `model`, `options`), which T3 Code uses when it delegates a takeover. Without a takeover entry, takeover is a copy of that client's `standard` entry. Outside T3, the Claude takeover subagent takes only the alias and inherits the session effort, as before: the Agent call passes no `effort` parameter. The effort of the takeover entry is used when T3 Code delegates the takeover, where the whole entry is passed.

`night-run.clean-slate` stays a separate, explicit override outside `targets`. If its model is unavailable, the orchestrator uses the model from `targets.<client>.standard`, where `<client>` comes from clean-slate's `provider` through the provider table in the T3 card (`claudeAgent` → `claude`, and so on); a provider missing from that table makes the ticket needs-human. It keeps the effort set in clean-slate, and records the switch in the night report. If its provider is unavailable, the ticket becomes needs-human.

Naming follows [CONTEXT.md](../../CONTEXT.md): a **model tier** is not a **Tier** (the product layer), a **model alias** is a Claude Code name and not an **Alias**, and a **provider option** in `options` is not a **Variant**.

## Considered Options

Keeping the old keys as a fallback would keep two places a choice can come from. That is the argument [ADR-0007](0007-the-workspace-profile-is-the-only-configuration.md) makes against Presets, and it applies here too.

Reporting an old key as a notice and reading nothing from it was the first choice, and it was replaced. A repo could then run silently on the session model, or on a provider default, without anyone noticing. Reload now fails on an old key, with a message that names the migration. It fails in that one repo only, and it does not rewrite the Profile.

Rewriting old keys into `targets` on reload was rejected. The README says reload leaves the model block alone, and Profile changes go through `/kit-project-edit` with a preview.

Flat option keys such as `effort: low` were rejected. The inline `options` list maps one to one onto T3 Code's option shape.

A PyYAML parser was rejected. Bootstrap runs on the system Python, which may not have it.

## Consequences

A repo that still has `models:` or `t3.targets` fails reload until its Profile is migrated to `targets:` through `/kit-project-edit`. This is a visible change in behaviour, not a silent one. The kit's own repository is such a repo. Its Profile is migrated in the same change, through `/kit-project-edit`, so reload there does not fail.

The standard tier moves from `sonnet` to `claude-haiku-5-5` with effort `max`. Light agents get effort `low`. In the template defaults, the heavy agents, all `review-*` since #516, get effort `medium`, and `night-run` moved to the standard tier in #516. Existing Profiles with an `agents:` block keep their own assignments, so their `review-*` agents may still run on `standard` and their `night-run` on `heavy`. All of them previously inherited the session's effort.

`effort:` in agent frontmatter is documented, but the environment variable `CLAUDE_CODE_EFFORT_LEVEL` overrides it. Users who set that variable get its level instead of the Profile's.

The headless checker (#397) reads `targets.claude.light.model` from the Profile. Without that entry it is disabled, and the night report says so.
