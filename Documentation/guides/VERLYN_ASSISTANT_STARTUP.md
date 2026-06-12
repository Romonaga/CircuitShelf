# Verlyn Assistant Startup and API Guide

Use this guide when you are an assistant working inside this repository.

`AGENTS.md` remains authoritative for policy. This guide explains the minimum
Verlyn startup path for a governed client repository. The governance pack does
not vendor Verlyn Python helper source into this repo; use the installed
`verlyn` CLI and backend API.

## Read In This Order

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md`
6. This guide
7. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`
8. Active change details from Verlyn when work already exists

After session compaction, compressed-summary recovery, or any resume where the
operator may question whether rules were reloaded, reread the governed files
and visibly tell the operator:

> Governance was reloaded and required repo rules were reread.

## Required Startup Commands

Run these before suggesting or editing anything:

```bash
verlyn auth status
verlyn target show --json
verlyn changes list
verlyn runs --limit 3 --json
```

These commands confirm that the installed CLI is authenticated, the current
checkout is authorized through the backend, and current workflow state is
visible. If auth, target binding, or repo authorization fails, stop and repair
that path before editing.

## Auth And Repo Binding

Normal login:

```bash
verlyn auth login --server <verlyn-api-url> --username <user>
verlyn auth status
```

For first checkout of a repo already attached to a Verlyn project:

```bash
verlyn repos clone <repo-slug> ./local-folder --project-id <project-id>
```

Rules:

- CLI auth is user/profile scoped and separate from durable repo identity.
- The backend owns project/repo authorization and provider-token resolution.
- The CLI must not connect directly to PostgreSQL or ask users for provider tokens.
- Local paths are user-machine preferences; entity, project, and repository
  bindings remain the source of truth.

## Workflow Commands

Use installed `verlyn` commands for normal developer workflow:

```bash
verlyn changes list
verlyn changes show <change-id>
verlyn changes activate <change-id>
verlyn changes refresh-branch <change-id>
verlyn work-items list <change-id>
verlyn work-items update <change-id> --creates-json '[{"title":"Add validation"}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn changes publish <change-id> --merge-method squash
verlyn changes close-change <change-id> --status merged --summary "Delivered."
```

`verlyn changes publish` is the normal hosted closeout command. It commits
local dirty work when `--commit-message` is supplied, pushes with Verlyn-managed
provider credentials, opens or updates the PR, merges it, switches the local
checkout back to the delivery base branch when local checkout context exists,
and records closeout.
Use `verlyn changes publish-pr` only when you intentionally want to stop at an
open PR without merging or closing the Verlyn change.

Creation and activation are separate. A new change starts as draft. Activate it
before implementation so Verlyn can bind the work branch and enforce the normal
workflow trail.

Use the batchable work-item update command for one or many work-item mutations.
Do not create ad hoc local workflow files as durable truth.

## Source Of Truth

Durable Verlyn truth is backend-backed and scoped by entity, project, and
repository:

- changes
- work items
- reviews
- decisions
- runs
- report/evidence records

Repo-local files are source code, governance policy, templates, or temporary
scratch artifacts. Do not reconstruct durable workflow truth from old
`workstream/` files, workspace-local JSON, generated scratch paths, or chat
summaries.

## Completion

Work is not complete until:

- acceptance criteria are satisfied
- applicable verification passes
- change/work-item state is updated through Verlyn
- remaining risks are recorded
- PR/delivery state is handled through the Verlyn workflow path
