# Instruction Kit

A central repository of project instructions, served to AI coding clients over MCP. A consuming repo picks a Preset, adds an Overlay, and its agents read the resulting Bundles live — the instruction text is never copied into the consuming repo, so it cannot go stale.

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
Instructions true of exactly one consuming repo — its paths, ports, task names — living in that repo rather than in the Kit. Appended to a Bundle, never merged into it.
_Avoid_: local rules, project config, extras

### Configuration

**Profile**:
The full set of choices that determines which Instruction Modules a repo gets: its Stacks, Capabilities, Domains, Patterns and Decisions.
_Avoid_: config, settings

**Preset**:
A Profile shipped by the Kit as a reusable starting point — `_base` for the shared stack foundation, `shop` for e-commerce. A repo names a Preset instead of writing its own Profile.
_Avoid_: template, category, flavour

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
A more specific Instruction Module that accompanies a general one when a Decision narrows it — `capability:auth:jwt` alongside `capability:auth`. The general module stays.
_Avoid_: flavour, subtype, specialisation

**Substitution**:
A Instruction Module that replaces a general one outright when a choice narrows it — `arch:api-contract:graphql` instead of `arch:api-contract`. The counterpart to a Variant: a Variant adds, a Substitution swaps.
_Avoid_: override, replacement, swap

**Stack**:
A named technology foundation a Profile switches on — `django-drf`, `expo-router` — expanding to several Instruction Modules at once.
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

**Bootstrap**:
The one-time installation of Kit files into a Workspace: client configuration, agent definitions and slash commands. Distinct from serving instructions, which happens live over MCP and copies nothing.
_Avoid_: install, setup, sync

**Client**:
An AI coding tool that consumes the Kit — Cursor, Claude Code, Codex, VS Code, Kiro, Kilo, Antigravity, opencode. Determines only where Bootstrap writes files; never changes Bundle content.
_Avoid_: IDE, editor, agent, tool

**Bootstrap Stamp**:
The record a Bootstrap leaves in a Workspace of which Kit commit produced the copied files, so drift can be detected without reading any instruction text.
_Avoid_: lockfile, manifest, version file
