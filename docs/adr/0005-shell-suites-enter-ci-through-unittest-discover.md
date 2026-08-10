# Shell suites enter CI through unittest discover, not their own workflow step

`tests/*.sh` and standalone `tests/test_*.py` scripts run as subprocesses driven by `tests/test_shell_suites.py`, which `unittest discover` collects like any other test. CI keeps a single test command.

The obvious alternative — a second workflow step running `bash tests/*.sh` — is what a reader will suggest on seeing this, so: it recreates the failure it fixes. These suites went unrun for months precisely because the set of things CI executes was maintained separately from the set of things that exist. A YAML step is a second list to keep in sync; the adapter derives the run from the filesystem and fails when a suite is not declared.

Two properties are load-bearing and easy to break while "simplifying" this. A suite that skips must not be indistinguishable from a suite that passed, so `is_ci()` turns a missing `bash` or `node` into a failure on CI while keeping the local skip on a bare Windows machine. And the declaration guards cover both shapes of orphan — a new `.sh`, and a new `test_*.py` that defines no `TestCase` — because the second shape is what hid `test_bash_hook_launcher.py` from CI in the first place.
