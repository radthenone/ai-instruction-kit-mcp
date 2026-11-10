# The Kit owns how a worktree is built, not whether one is built

A worktree stays optional: `/git-start` still ends on a branch in the main checkout, and the human, Superpowers or a Kit procedure decides when isolation is worth it. Once a worktree exists for an agent or a Kit procedure, though, it must be a Managed Worktree: created with `node .ai/worktree.mjs add`, or synced with `node .ai/worktree.mjs sync` straight after a native tool or Superpowers created it, and removed with `node .ai/worktree.mjs remove`. The `worktree:` section of the Profile (`copy`, `link`, `setup`, `venv`) is the configuration of that method, with `.ai/worktree.json` as its render (ADR-0007); it says how to build a worktree and never whether to build one.

The rules contradicted each other because they answered two different questions: `AGENTS.md` called the worktree a Superpowers option (when), and `git-branch-pr` said "always through `worktree.mjs`" (how). The method cannot be optional, because a plain worktree lacks the gitignored files: in #299 `/headless` lost `opencode.json`, fell back to a built-in model and twice finished with no change and exit code 0. The rule's claim that Superpowers `using-git-worktrees` runs `worktree.mjs` is false: the skill prefers a native tool and otherwise calls plain `git worktree add`, which is why `sync` is part of the method.

## Considered Options

- **Worktree by default in every `/git-start`.** Rejected: it changes the flow of every consumer, and a small fix would pay for the file copy and the venv overlay with no benefit.
- **A Profile switch such as `worktree.default: true`.** Rejected, against the original assumption of #342: nothing would read it. `/git-start` does not create worktrees, and `/night-run` decides for itself.
- **An interview question in `/kit-project-begin`.** Rejected: an absent section already works, so the section is documented as a commented block in the Profile template and left to an explicit request, like `server:`.
- **A Guard denying plain `git worktree add`.** Rejected: it would block step 1b of `using-git-worktrees` and a human's own git use, and the harm is not destructive, since `sync` repairs it afterwards (ADR-0006). Automating `sync` with a `WorktreeCreate` hook is left until a skipped `sync` actually causes a failure.

## Consequences

The method is enforced by a rule, not a Guard, so a skipped `sync` can still happen. Git used by hand outside the Kit stays out of scope, but documented Kit flows, including the cost measurement of `/night-run`, use the method.
