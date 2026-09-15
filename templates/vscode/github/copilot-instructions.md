# Copilot project instructions (from instruction-kit).
# Canonical prose: repo AGENTS.md + MCP project-guides (`get_bundle` / `get_overlay` / `get_clients`).

Follow AGENTS.md in the repository root.

Before feature work: use MCP `project-guides` → `get_bundle` for the area you touch, and `get_overlay` for this repo.

Git: protected `main` / `master` / `dev` — work on a feature branch, push, then PR. Prefer Conventional Commits.

Before push: run local review (`/review-bugbot` in Cursor, or equivalent review agents). Do not force-push to protected branches.

Shell: `.github/hooks/rtk-rewrite.json` rewrites bash commands to `rtk <cmd>` automatically when `rtk` is in PATH — do not add the prefix yourself, do not treat a missing `rtk` as an error. Meta commands stay direct: `rtk gain`, `rtk discover`, `rtk proxy <cmd>`.
