# Commands take each client's native form, and flat command files are pruned by name

Bootstrap writes kit commands only in the form each Client reads natively. For Claude Code that is the `kit-ai` plugin in `.claude/skills/kit-ai/`, invoked as `/kit-ai:<name>`. For opencode it is `.opencode/commands/kit-ai/`, invoked as `/kit-ai/<name>`. Before #526 and #527 both clients got flat files instead, `.claude/commands/<name>.md` and `.opencode/command/<name>.md`, invoked as `/<name>`. This decision closes the contract step of #517 (#533). No alias keeps the old spelling, and the flat files that earlier versions left in installed repos are removed on reload. Design discussion and the chosen variant, A (native form per client, name whitelists, and the `--skip-agents` boundary): #517.

Reload removes a flat file when its name matches a kit Command. The names come from the agent templates in `templates/shared/agents/`, from `LEGACY_COMMAND_NAMES` in `scripts/bootstrap-project.sh` (commands the kit shipped under older names), and, for opencode, from the names of the shared skills. A skill renamed since, `retro` now `kit-retro` (#422), is removed only when its file carries the kit's marker, as `prune-renamed` already does. The rule is the one `prune_tier_agents` uses. It matches by name, deletes only that file, and leaves the directory and every other file in place. A flat file carries no marker, so the kit cannot tell its own copy from a user's file with the same name, and reload removes both.

The rule runs for a selected client on every reload, and for a deselected client in the same pass that removes that client's other kit files. `--keep-unselected-clients` keeps deselected clients untouched, as before.

`--skip-agents` is the boundary of the command forms. With it, install renders no commands, and reload of a selected client neither renders nor prunes them, so a repo installed that way keeps its command files as they are. A deselected client is pruned as before, `--skip-agents` or not, unless `--keep-unselected-clients` is given.

`/goal` and `/loop` were the exception. They stayed flat in `.opencode/command/` while opencode was selected, because the kit-loop plugin implemented those two commands under those names. The owner of #533 accepted this exception in a comment on that issue, which is the written change of its criterion. Since #567 they take the native form too: `.opencode/commands/kit-ai/{goal,loop}.md`, invoked `/kit-ai/goal` and `/kit-ai/loop`, and the plugin recognizes only those forms. Reload removes the flat `goal.md` and `loop.md`.

## Considered Options

Keeping the flat files beside the native ones, or aliasing the old spelling, would give each command two invocations to keep in step. Rejected, because the contract is one form per client.

Deleting only the flat files whose content still matches the kit's output would leave a customised copy under a stale name, and would need a second rule to maintain. Rejected. The kit already overwrote these files by name before the move, through `copy_claude_commands` for Claude and the renderer for opencode, so a name rule adds no risk that was not there.

Marking kit-written flat files would need a marker in files that have none, and those files already sit in users' repos. Rejected.

## Consequences

A user who typed `/git-start` in Claude Code types `/kit-ai:git-start` instead, and in opencode `/kit-ai/git-start`. A file in `.claude/commands/` or `.opencode/command/` whose name matches a kit Command is deleted on reload, including one the user wrote.

`tests/test_flat_command_prune.py` covers removal for selected and deselected clients and checks that foreign files stay. `tests/test_reload_snapshot.py` pins the reload output of all clients to `tests/fixtures/reload_snapshot.json`. The one part it leaves out is the mapping table in the `kit:brief` block of `AGENTS.md`, which changes with the client mapping.

Checks the tests do not run, left for a person before merge: T3 Code shows `kit-ai:git-start` among the skills, `claude plugin validate` passes on `.claude/skills/kit-ai`, and `/kit-ai/git-start` runs in opencode.

Naming follows [CONTEXT.md](../../CONTEXT.md): a **Command** is the slash-command form of a kit agent template, the **Command prefix** is what a native form adds to its name, the **Kit-ai plugin** is the Claude form, and a **Flat command file** is the retired form.
