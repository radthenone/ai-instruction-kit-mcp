# The Workspace Profile is the only configuration; the Kit ships no Presets

A consuming repo's choices — Language, Clients, the Stack in each Tier, Capabilities, Patterns, Decisions — live in one committed file in its Workspace, `.ai/project.profile.yaml`. The MCP server reads it from `--workspace`; the client configuration carries no other choice. `--preset`, `--profile`, `profiles/_base.yaml` and `profiles/shop.yaml` are removed, and so are the hardcoded `default_bundles`: a Bundle is computed from the Profile, and a Profile that chooses nothing yields the core modules only.

The trigger was a repo whose stack was not decided yet. The default Preset `_base` switched on Django and Expo, so the only way to get a neutral setup was to hand-write a Profile with `stacks: {}` and point `--profile` at it — and Bootstrap still installed Django and Expo reviewers. A Preset is a bet that many repos share a whole stack; in practice they share the core and differ in every Tier.

## Considered Options

Keeping Presets as shorthands for a set of Tier choices would have spared existing repos a migration. We rejected it because it keeps two places a choice can come from (the Preset and the Profile override), and because the e-commerce Preset `shop` mixed a product domain into the Kit — the domain of a product belongs in that product's own glossary, not in shared instructions.

## Consequences

The client configuration is identical for every repo, so changing a Tier never requires reloading the client's MCP setup — only rerunning Bootstrap. A repo still configured the old way is not a startup failure (ADR-0004): the server starts with the core modules and every Bundle opens with a notice to migrate through `kit-ai reload`, which writes a Profile with every Tier set to `none`. Existing repos therefore lose their Stack instructions until they choose their Tiers again — accepted, because a guessed Stack is worse than an explicit gap.
