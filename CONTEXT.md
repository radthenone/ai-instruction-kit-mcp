# Instruction Kit

A central repository of project instructions, served to AI coding clients over MCP. A consuming repo records its choices in a Profile, adds an Overlay, and its agents read the resulting Bundles live — the instruction text is never copied into the consuming repo, so it cannot go stale. The one exception is the Brief Rules, which are copied into Carriers at reload (ADR-0010).

## Language

### Instruction content

**Instruction Module**:
A single Markdown file of instructions, addressed by a stable Module ID such as `infra:queue:redis`. The unit the Manifest registers and a Bundle concatenates.
_Avoid_: rule, guide, doc, instruction file

**Module ID**:
The `layer:category:variant` address of an Instruction Module. Canonical form only — an Alias is not a Module ID.
_Avoid_: key, slug, name

**Bundle**:
A named, ordered set of Instruction Modules concatenated into one Markdown document for a single kind of work — `backend`, `frontend`, `architecture`, `infra`, `devops`, `full`.
_Avoid_: pack, set, collection

**Manifest**:
The registry that gives every Instruction Module its ID, file location and title, and holds the rules that translate a Profile's choices into Module IDs.
_Avoid_: index, catalog, registry file

**Overlay**:
Instructions true of exactly one consuming repo — its paths, ports, task names — living in that repo rather than in the Kit. Appended to a Bundle, never merged into it. Delivered to the agent by `get_overlay`, never pasted into the Brief.
_Avoid_: local rules, project config, extras

**Brief**:
The short orientation an agent reads before working in a Workspace: the Brief Rules plus a pointer to `get_overlay`. Lives in the MCP instructions and in the Kit-owned section of `AGENTS.md`.
_Avoid_: prompt, system text, preamble

**Brief Rules**:
The few rules every agent must know before its first action — task classification, `get_overlay` before editing, docstring format, the VPS install restriction. Rendered from one template with the Profile's Language filled in; the only Kit instruction text copied into a Workspace.
_Avoid_: guidelines, global rules, instructions

**Host**:
The machine the agent runs on, classified as `vps` or `local`. Distinct from a Client (the AI tool) and a Workspace (the repo directory).
_Avoid_: server, environment, machine

**Carrier**:
A place where Brief Rules reach an agent: the per-turn language hook (Claude only), the MCP instructions, the Kit-owned section of `AGENTS.md` (read by every Client).
_Avoid_: channel, transport, delivery

### Configuration

**Profile**:
The full set of choices that determines which Instruction Modules a repo gets: its Language, Clients, the Stack in each Tier, Capabilities, Patterns and Decisions. Lives in the Workspace and is committed with it; the Kit ships no ready-made Profiles. A Profile that chooses nothing gets the core modules only.
_Avoid_: config, settings, preset

**Tier**:
A layer of the consuming product — `backend`, `web` or `mobile` — holding exactly one Stack or none. Distinct from a Slot: a Tier decides which family of instructions applies, a Slot picks one infrastructure technology inside it.
_Avoid_: axis, side, layer, frontend

**Decision**:
A choice of one concrete technology for one Slot, recorded in a Profile: `queue: rabbitmq`.
_Avoid_: option, setting, choice

**Slot**:
A named point of technology variation the Kit knows how to fill — `database`, `cache`, `queue`, `storage`, `tasks`, `search`, `auth`. A Slot admits a fixed set of Decisions.
_Avoid_: key, category, dimension

**Capability**:
A cross-cutting feature a product either has or hasn't — authentication, file storage, payments. Distinct from a Slot: a Capability is present or absent, a Slot is filled with one of several technologies.
_Avoid_: feature, module

**Variant**:
A more specific Instruction Module that accompanies a general one when a Decision narrows it — `capability:auth:jwt` alongside `capability:auth`. The general module stays. A Stack always carries one Variant: the bare Stack name means its current approach (`react`), an older one is named explicitly after `@` (`react@legacy`).
_Avoid_: flavour, subtype, specialisation

**Substitution**:
A Instruction Module that replaces a general one outright when a choice narrows it — `arch:api-contract:graphql` instead of `arch:api-contract`. The counterpart to a Variant: a Variant adds, a Substitution swaps.
_Avoid_: override, replacement, swap

**Stack**:
A named technology foundation chosen for one Tier — `django`, `react`, `expo` — expanding to several Instruction Modules at once.
_Avoid_: framework, platform, tech

**Pattern**:
A recurring design approach that spans Stacks and Capabilities — the capability-provider shape, gateway routing, webhook handling.
_Avoid_: convention, practice, approach

**Language**:
The language a Profile chooses for instruction and agent prose. Titles of issues, pull requests and branches, and all code identifiers, stay English regardless — only prose follows the choice.
_Avoid_: locale, i18n, translation

**Alias**:
A superseded spelling of a Module ID or of a Capability name, still accepted so existing Profiles keep resolving. Every Alias resolves to exactly one canonical Module ID.
_Avoid_: synonym, legacy name, shorthand

### Distribution

**Kit Root**:
The directory holding the Manifest and the Instruction Modules — a git clone during development, a data directory inside the installed wheel in production.
_Avoid_: repo root, source dir

**Workspace**:
The root of the consuming repo — where the Overlay and the Bootstrap Stamp live. Never the Kit Root.
_Avoid_: project dir, target, cwd

**Project Block**:
The protected section of a Kit-rendered rules file — `project:rules` in `BUGBOT.md`, `project:agents` in `AGENTS.md` — that holds the Workspace's own lines and passes through every Bootstrap unchanged while the rest of the file is refreshed from the Kit template.
_Avoid_: custom section, user block

**Uncertain Migration**:
A migration of a rules file without a Project Block that the Kit does not apply on its own — the template lines were edited, or too many lines were added — and only proposes, leaving the move into the Project Block to an explicit, accepted fix.
_Avoid_: failed migration, manual migration

**Bootstrap**:
Writing Kit files into a Workspace as its Profile dictates: client configuration, agent definitions, slash commands and Guards. Repeatable — rerun whenever the Profile or the Kit changes; never touches the Overlay. Distinct from serving instructions, which happens live over MCP and copies nothing, except the Brief Rules written into Carriers (ADR-0010).
_Avoid_: setup, deploy

**Client**:
An AI coding tool that consumes the Kit — Cursor, Claude Code, Codex, VS Code, Kiro, Kilo, Antigravity, opencode. Determines only where Bootstrap writes files; never changes Bundle content.
_Avoid_: IDE, editor, agent, tool

**Guard**:
A hook script the Bootstrap installs into a Workspace so a Client refuses or reports an agent action — a destructive git command, a write to a secret, a lint failure. One policy source in the Kit, translated per Client; a Guard either allows or denies, it never asks the human.
_Avoid_: guardrail, gate, hook, blocker

**Lock-only Form**:
A package-manager command that only resolves versions and rewrites the lockfile, with no dependency installed. It is the one way to change dependencies that the server Guard lets through on a weak server host (ADR-0009), and it can still run project code (`.pnpmfile.cjs`) or compile a backend while reading metadata.
_Avoid_: dry run, offline install, lock update

**Bootstrap Stamp**:
The record a Bootstrap leaves in a Workspace of which Kit commit produced the copied files, so drift can be detected without reading any instruction text.
_Avoid_: lockfile, manifest, version file

**Managed Worktree**:
A linked git worktree built or synced by the Kit's method, so it carries the gitignored files and dependencies it needs from the main checkout. A plain git worktree is not one until synced (ADR-0014).
_Avoid_: kit worktree, isolated workspace

### Agents

**Classification**:
The required `procedure` or `code` value in an agent template's frontmatter, saying whether the agent runs a fixed kit procedure or changes application code. A missing or unknown value fails the Bootstrap (ADR-0013).
_Avoid_: type, category, kind

**Procedure agent**:
An agent classified `procedure`: a kit workflow such as `/git-*` or `/review-*`, which the ponytail plugin must not rewrite.
_Avoid_: workflow agent, kit agent

**Code agent**:
An agent classified `code`: one that writes application code, the only kind the ponytail plugin applies to.
_Avoid_: dev agent, coding agent

**Ponytail matcher**:
The regex in `PONYTAIL_SUBAGENT_MATCHER` that matches every agent except the Procedure agents. Written by the Bootstrap to `.claude/settings.local.json` in the kit's form; a hand-written value is never overwritten (ADR-0013).
_Avoid_: filter, pattern, allowlist

**Subagent**:
An agent started by another agent for one bounded job, in its own context. It cannot talk to the human; whatever it has to say goes through a Hand-back.
_Avoid_: child agent, worker

### Night run

**Orchestrator**:
The main session driving a `/night-run`: it picks Tickets and starts a Subagent for each, and never does a Ticket's work itself.
_Avoid_: main agent, coordinator, master

**Ticket**:
One issue taken through a `/night-run`, from its branch to a merge or to Needs-human.
_Avoid_: task, job

**Hand-back**:
The final report a Subagent gives the agent that started it: the state of the work and what is left. Giving it ends the Subagent's run.
_Avoid_: handover, handoff, return value

**Needs-human**:
The outcome of a Ticket that cannot be finished without a person, stated in a report. A status, never a label: the issue itself gets `ready-for-human`, `needs-info` or `needs-local`.
_Avoid_: blocked, escalated, needs-human label

**Finding blokujący**:
A High finding on the Spec axis that is still unresolved after the fixes, re-checked by a fresh Subagent. It blocks the merge of its Ticket; a green CI does not lift it, and only the goal text can waive it.
_Avoid_: blocker, spec failure, blocking review

### Retro

**Sesja**:
Jeden zapis rozmowy agenta (plik JSONL wraz z jego subagentami) albo jeden przebieg headless lub nocny ticket, traktowany jako całość przy analizie.
_Avoid_: Transkrypt, run, rozmowa

**Sygnał**:
Pojedyncze wykrycie w logu sesji, na przykład odrzucenie przez guard albo błąd narzędzia.
_Avoid_: Błąd, event, alert

**Znalezisko**:
Sygnały o tym samym znaczeniu zgrupowane po fingerprincie, z liczbą wystąpień i dowodem po maskowaniu.
_Avoid_: Problem, issue, raport

**Fingerprint**:
Klucz deduplikacji znaleziska, stały między sesjami i maszynami dla tego samego problemu.
_Avoid_: ID, hash, sygnatura

**Propozycja**:
Sugerowana zmiana kitu, projektu albo karta do założenia, którą człowiek musi zaakceptować przed jakimkolwiek zapisem na GitHub.
_Avoid_: Zadanie, ticket, automatyczne issue
