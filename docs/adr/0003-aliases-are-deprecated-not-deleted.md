# Aliases are deprecated with a warning, not deleted

An Alias is kept working indefinitely once shipped, and is surfaced as a deprecation note in the instruction index rather than removed.

The constraint is not visible in the code: the Kit is consumed over `uvx --from git+…`, so we cannot enumerate the repos whose Profiles still spell a Capability the old way. Deleting an Alias does not fail loudly for them — an unrecognised Module ID is filtered out at the end of resolution, so the consuming repo silently loses a whole Instruction Module from its Bundles and only notices when an agent starts giving advice that ignores, say, file storage entirely.

Surfacing the Alias in the index gives those repos a way to notice and migrate. Removal is a separate, later decision, taken only once the warning has shipped for a cycle.
