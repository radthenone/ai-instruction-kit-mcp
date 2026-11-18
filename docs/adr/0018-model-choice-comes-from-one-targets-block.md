# Model choice comes from one Profile block, `targets`; the old model keys are not read

Which model each kit agent runs on, and which model and options a T3 Code delegation receives, is recorded in one block of the Workspace Profile: `targets.<client>.<model tier>`. Each entry holds `providerInstanceId`, `model` and `options`. Bootstrap reads the block when it writes agent files for Claude Code and OpenCode, and the T3 night-run card reads it when it delegates a task. The `models:` block and the `t3.targets` block are no longer read. Before this decision the same choice came from both, and the two already disagreed: the kit's standard tier ran on `sonnet`, while T3's ran on `claude-haiku-5-5`. Design discussion and implementation: #515; until that change lands, the kit still reads `models:` and `t3.targets`.

The model tiers are `light`, `standard` and `heavy`, which agent templates already set through `model-tier:`, plus `takeover`, which exists only for Claude. A tier with no entry sets no model, so the agent runs on the session model.

For Claude, bootstrap writes `model:` and `effort:` into the frontmatter of `.claude/agents/*.md`. For OpenCode, it writes `model: <provider/model>#<variant>` into `.opencode/command/*.md`, because OpenCode takes the variant as a suffix on the model name and has no separate key; without a `variant` option it writes the plain `model: <provider/model>`. Codex and Antigravity get no files; their targets are used only by T3 Code.

Options are written inline as `options: [{ id, value }]`, the shape T3 Code uses. The parser reads that without PyYAML, because bootstrap runs on the system Python.

An invalid entry (an unknown option id, a Claude `effort` outside `low`, `medium`, `high`, `xhigh`, `max`, or an unknown alias) makes reload print a notice and skip that part. The kit does not validate OpenCode `variant` values, which differ per model; T3 Code checks them at delegation time. The agent then behaves as if it had no entry. Model-tier problems do not stop reload. [ADR-0004](0004-unknown-decisions-are-reported-not-fatal.md) sets the same rule for unrecognised decisions. Old keys follow it too: reload prints a notice that `models:` and `t3.targets` are no longer read and must move to `targets:`.

[ADR-0013](0013-agent-classification-and-ponytail-matcher.md) is unchanged. It makes the agent `classification` a required field that fails bootstrap and reload when missing. Model tiers are optional, and a missing one has a safe default, the session model, so that stricter rule does not apply to them.

Takeover: the Agent tool takes `model` as an alias only, so the takeover model must be `haiku`, `sonnet`, `opus` or `fable`. Its effort is passed in the per-invocation `effort` parameter, which Claude Code supports from version 2.1.292; an older client runs takeover at the session's effort, and the README states the minimum version. Without a takeover entry, takeover uses the session model, as it does today.

`night-run.clean-slate` stays a separate, explicit override outside `targets`. If its model is unavailable, the orchestrator uses the model from `targets.<client>.standard`, where `<client>` comes from clean-slate's `provider` through the provider table in the T3 card (`claudeAgent` → `claude`, and so on); a provider missing from that table makes the ticket needs-human. It keeps the effort set in clean-slate, and records the switch in the night report. If its provider is unavailable, the ticket becomes needs-human.

Naming follows [CONTEXT.md](../../CONTEXT.md): a **model tier** is not a **Tier** (the product layer), a **model alias** is a Claude Code name and not an **Alias**, and a **provider option** in `options` is not a **Variant**.

## Considered Options

Keeping the old keys as a fallback would keep two places a choice can come from. That is the argument [ADR-0007](0007-the-workspace-profile-is-the-only-configuration.md) makes against Presets, and it applies here too.

Failing reload on an old key was rejected. It would stop bootstrap in every repo still using the old keys. The kit reports such configuration instead ([ADR-0004](0004-unknown-decisions-are-reported-not-fatal.md)).

Rewriting old keys into `targets` on reload was rejected. The README says reload leaves the model block alone, and Profile changes go through `/kit-project-edit` with a preview.

Flat option keys such as `effort: low` were rejected. The inline `options` list maps one to one onto T3 Code's option shape.

A PyYAML parser was rejected. Bootstrap runs on the system Python, which may not have it.

## Consequences

A repo that still has `models:` or `t3.targets` gets a notice on reload. Its agents run on the session model, and its T3 delegations fall back to the provider's default model, until the Profile is migrated. This is a change in behaviour, not an error. This repository's own Profile is migrated in the same change, through `/kit-project-edit`.

The standard tier moves from `sonnet` to `claude-haiku-5-5` with effort `max`. Light agents get effort `low`. The heavy agents `night-run` and `review-edge` get effort `medium`. All of them previously inherited the session's effort.

`effort:` in agent frontmatter is documented, but the environment variable `CLAUDE_CODE_EFFORT_LEVEL` overrides it. Users who set that variable get its level instead of the Profile's.
