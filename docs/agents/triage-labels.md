# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Execution Condition Labels

Execution condition labels (`needs-local`) are distinct from triage state labels. A ticket can have both `ready-for-agent` and `needs-local` simultaneously (warunek wykonania, nie stan triage).

- `needs-local`: The ticket requires execution/verification on a local machine (e.g. device tests, manual UI checks, hardware access, or dependency/lockfile updates that cannot be built/verified on VPS).
  - On `Host: vps`, `/night-run` skips this ticket (`skipped: needs-local`).
  - On `Host: local`, `/night-run` processes it normally.
  - **Removal by user / zdjęcie etykiety przez użytkownika**: The user can instruct the agent to remove `needs-local` (or run `gh issue edit <N> --remove-label needs-local`). The next run on VPS will then pick up the ticket.
