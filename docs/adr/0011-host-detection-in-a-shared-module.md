# Host detection lives in one shared module, not behind `kit-ai host`

The VPS/local classification of a Host is implemented once in JavaScript as a shared module that both hooks (`language-reminder.mjs`, `server-guard.mjs`) import, and once in `host_profile.py` for `kit-ai host` and the night-run watchdog. A parity test runs both implementations on the same table of `GUARD_*` inputs. Where an input is empty or unparseable, the rule is the same in both: it is treated as absent and the real measurement of the machine is used. The on/off switch of the server guard (`config.guard`) is not a property of the Host and stays outside the detection in `server-guard.mjs`.

Hooks do not call `kit-ai host`. Bootstrap copies the shared module next to the hooks it serves; the module lives in `templates/shared/` and is installed by the same steps that install the guards.

## Considered Options

- Hooks call `kit-ai host` as a subprocess. Rejected: the consuming repo does not guarantee `kit-ai` on PATH, and `language-reminder` runs on every prompt, so each call would pay a process start and fail whenever PATH is wrong.
- Keep three copies and extend the parity test. Rejected: it keeps the drift the issue set out to remove, and the existing copies already disagree on empty and non-integer values.

## Consequences

- The single source is the shared JavaScript module for the hooks, with the Python implementation kept in step by the parity test. The rule has two implementations, not one.
- Bootstrap copies one more file per consuming repo. The copy list is part of the install steps and is checked by tests.
- The watchdog keeps comparing the header with `kit-ai host`, which is safe because both sides now apply the same rule for empty values.
