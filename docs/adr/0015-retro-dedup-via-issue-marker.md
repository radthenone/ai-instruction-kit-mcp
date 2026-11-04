# Retro deduplicates findings against open issues through a marker in the issue body

`kit-ai retro report` must not re-propose a finding that already has an issue, and the check has to work across sessions and machines. We decided to store the `fingerprint` as a hidden marker (`<!-- retro-fingerprint: ... -->`) in the body of the issue created from the proposal, and to search open issues with `gh` for that marker. A local database would have been simpler to query, but it cannot see issues opened from another machine, and the dedup key would then drift between caches.
