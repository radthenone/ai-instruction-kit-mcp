# Mappings live in the Manifest, not a separate file

The rules that translate a Profile's Slots, Capabilities, Domains, Patterns and Stacks into Module IDs used to be hardcoded as seven dictionaries in `resolver.py`, which meant adding a new Decision such as `search: elasticsearch` required editing Python even though the Kit's whole premise is that instructions extend by adding Markdown. We moved those rules into `manifest.yaml` alongside the Instruction Module registry.

## Considered Options

A separate `mappings.yaml` was the obvious alternative and it does separate two responsibilities — the registry of what exists, and the rules for what gets included. We rejected it because both halves reference the same Module IDs and change in the same commit, so splitting them buys one more loader, one more `force-include` entry in the wheel, and a second place for a Module ID to drift out of sync with the registry. A separate file becomes right only if mappings ever need their own release cycle.

## Consequences

`manifest.yaml` is now the only interface for extending the Kit: a new Instruction Module is one Markdown file plus one registry entry, and a new Slot value is one mapping entry. `resolver.py` no longer carries domain knowledge about which technologies exist.
