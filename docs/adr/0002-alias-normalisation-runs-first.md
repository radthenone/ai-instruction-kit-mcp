# Alias normalisation runs first in the Module ID pipeline

Resolving a Profile applies four transformations to a list of Module IDs: Alias normalisation, language module selection, Codegen substitution, and Variant insertion. The canonical order is **Alias normalisation first**, then the rest.

This is worth recording because the code did the opposite for a long time and got away with it. The three later transformations act on disjoint Module IDs — `core:language-*`, `arch:api-contract`, `capability:auth` — so they commute, and Alias normalisation running last was harmless only because the single Alias in existence (`capability:files-storage`) pointed at none of them. The moment an Alias points at a Module ID that a later transformation matches on, running normalisation last silently drops the Variant: an Alias `capability:authentication → capability:auth` resolves to `capability:auth` with no `capability:auth:jwt` beside it, and nothing errors.

Normalisation first makes the order correct by construction rather than accidentally harmless. It costs nothing today — verified across every combination of Codegen, auth Variant and language — so there was no reason to defer it until a colliding Alias actually shipped.
