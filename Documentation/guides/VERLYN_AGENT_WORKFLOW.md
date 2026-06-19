# Verlyn Agent Workflow

Use this guide when an assistant or agent is working inside this repository.
It is the single assistant-facing workflow guide installed by the governance
pack. `AGENTS.md` remains authoritative for policy, and `RULES.md` may contain
project-owned guidance for this repo.

Use `Documentation/guides/VERLYN_PUBLIC_CLI.md` as the command reference for
public CLI intent, optional arguments, and deliver-versus-deploy behavior.

## Read In This Order

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md`
6. This guide
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md`
8. Active change details from Verlyn when work already exists

After session compaction, compressed-summary recovery, or any resume where the
operator may question whether rules were reloaded, reread the governed files
and visibly tell the operator:

> Governance was reloaded and required repo rules were reread.

## Required Startup Commands

Run these before suggesting or editing anything:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn runs --limit 3 --json
```

These commands confirm that the installed CLI is authenticated, the current
checkout is authorized by Verlyn, and current workflow state is visible. If
auth, target binding, or repo authorization fails, stop and repair that path
before editing.

`verlyn workflow assistant-startup --json` is the canonical machine-readable
assistant reload command after context compaction. It returns repo state, edit
route state, visible working changes, latest run context, and the recommended
next action. `verlyn workflow assert-edit-route --json` fails closed when the
current checkout is not authorized for editing.

`verlyn changes list` defaults to the current user's working changes. For a
diagnostic view across all visible owners and statuses, use:

```bash
verlyn changes list --owner-scope all --status-scope all
```

## Command Priority

1. Installed public `verlyn` CLI commands
2. Web UI workflow surfaces for run creation, onboarding, and settings
3. Stop and record a Verlyn workflow blocker when the installed product path is missing or blocked

Do not use private Verlyn maintenance commands, direct database access, direct
workflow record edits, or shell tools such as `gh` as a substitute for Verlyn's
installed product workflow.

The hierarchy is strict for AI-assisted work: Public CLI first, API-backed
workflow context, no direct PostgreSQL access, no private helper scripts, no
provider secret handling, and no bypassing gates.

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
- Verlyn owns project/repo authorization and provider-token resolution.
- The CLI must not connect directly to PostgreSQL or ask users for provider tokens.
- Local paths are user-machine preferences; entity, project, and repository
  bindings remain the source of truth.
- Use `--target` only when you need to make local checkout selection explicit
  for diagnostics.

## Workflow Commands

Use installed `verlyn` commands for normal repository workflow:

```bash
verlyn changes list
verlyn changes show <change-id>
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes update <change-id> --proposal-summary "..." --proposal-scope "..."
verlyn changes activate <change-id>
verlyn changes refresh-branch <change-id>
verlyn work-items list <change-id>
verlyn work-items update <change-id> --creates-json '[{"title":"Add validation"}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<starter-work-item-id>","notes":"Concrete scope and acceptance for this change."}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn reviews record <change-id> --tier 1 --disposition accepted --summary "Reviewed."
verlyn workflow gate <change-id> --scope delivery
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id>
```

Creation and activation are separate. A new change starts as draft. Activate it
before implementation so Verlyn can bind the work branch and enforce the normal
workflow trail.

`verlyn changes create` also seeds required starter work items. These are
workflow tickets, not finished task plans. Read them with
`verlyn work-items list <change-id>`, then flesh them out for the specific
change before starting work. The first two starter items are tailored to the
change type, and `Review findings` plus `Finalize handoff` are always included.
`Review findings` is the required code/task review ticket when no separate
mandatory human review applies. Use it to confirm the implementation matches
the change ticket and work items, did not hallucinate behavior, and did not
make unrelated edits before delivery. Common seeds are:

| Change type | Starter work items |
|---|---|
| `feature` or default | `Implement <title>`, `Validate acceptance for <title>`, `Review findings` code/task review, `Finalize handoff` |
| `bugfix` | `Reproduce and fix <title>`, `Add regression coverage for <title>`, `Review findings` code/task review, `Finalize handoff` |
| `workflow` | `Implement workflow change for <title>`, `Validate workflow behavior for <title>`, `Review findings` code/task review, `Finalize handoff` |
| `api` | `Implement API change for <title>`, `Validate contract and acceptance for <title>`, `Review findings` code/task review, `Finalize handoff` |
| `performance` | `Profile and optimize <title>`, `Validate <title> responsiveness and load behavior`, `Review findings` code/task review, `Finalize handoff` |
| `refactor` | `Refactor <title>`, `Validate <title> behavior parity`, `Review findings` code/task review, `Finalize handoff` |
| `architecture` | `Shape architecture change for <title>`, `Validate dependency and workflow impact for <title>`, `Review findings` code/task review, `Finalize handoff` |
| `security` or `compliance` | `Implement remediation for <title>`, `Validate <title> security posture`, `Review findings` code/task review, `Finalize handoff` |

Use the batchable work-item update command for one or many work-item mutations.
When seeded starter implementation and validation items are too generic, update
those existing starter work item IDs in place with concrete scope, acceptance,
notes, and validation guidance before implementation. Do not add duplicates and
do not replace the required starter tickets as the normal path.
Do not create ad hoc local workflow files as durable truth.

For command intent and optional argument meanings, read
`Documentation/guides/VERLYN_PUBLIC_CLI.md`. In normal logged-in repo work,
avoid adding `--profile`, `--server`, `--repo-slug`, or `--target` unless you
are intentionally bootstrapping or overriding context.

Optional overrides such as `--profile`, `--server`, `--repo-slug`, `--target`,
`--source-ref`, and `--commit-sha` are diagnostics, bootstrap, or recovery
controls. They are not required in the normal checkout-bound workflow.

## Governance Pack And Skills

Use these when a repository needs the installable governance pack:

```bash
verlyn governance install --target <repo>
verlyn governance refresh --target <repo>
```

Verlyn owns files installed from the governance pack except
`RULES.md`, which is the repo-owned customization layer. Installed agent skill
files such as `.verlyn/agent-skills/verlyn-public-cli.md` and
`.verlyn/.codex/skills/verlyn-public-cli/SKILL.md` guide AI-assisted tools to
use the public CLI and defer to `AGENTS.md`, `CONTRIBUTING.md`, and `RULES.md`.
They are not permission to use direct DB access, private helper scripts,
provider tokens, or delivery gate bypasses.

## Session Loop

1. Read the governed files and inspect active change details from Verlyn.
2. Run the required startup commands.
3. Do not edit until the repo is authorized for the authenticated user and the applicable Verlyn change is active.
4. If no change applies, record an explicit direct-work reason before editing.
5. Create or update change and work-item records through the installed `verlyn` CLI.
6. Do the implementation and verification.
7. Update work items, review notes, and risks through Verlyn.
8. When the change is ready to land without deployment, use `verlyn changes deliver <change-id> --merge-method squash`.
9. When the change should land and deploy to the configured provider, use `verlyn changes deploy <change-id>`.

Use `verlyn runs abort <run-id>` only as controlled recovery for a stuck,
mis-scoped, or superseded active run. It is not a normal happy-path workflow
step, and the reason should be recorded on the relevant change, work item, or
handoff notes.

Important: `verlyn changes deliver` and `verlyn changes deploy` both run the
PR step. Both commands create or update the pull request, merge it, and record
source-control closeout. Use `deliver` when you want PR closeout only. Use
`deploy` when you want that same PR closeout followed by provider deployment.

`verlyn changes deliver` is the normal hosted source-control closeout command. It commits local
dirty work when `--commit-message` is supplied, pushes with Verlyn-managed
provider credentials, opens or updates the PR, merges it, switches the local
checkout back to the delivery base branch when local checkout context exists,
records closeout, and reconciles safe client-local branch deletion back into
the change metadata. It does not deploy. `verlyn changes deploy <change-id>`
runs the same hosted source-control closeout path and then triggers or monitors
the configured provider. When an already delivered source ref must be deployed,
pass `--source-ref` and optional `--commit-sha`; Verlyn then resolves that
delivered point and records deployment evidence. Credential issuance is gated
by Verlyn repo write access, release operations entitlement, exact client-remote
matching, and redacted audit recording; the CLI must not print provider tokens
in JSON output.

If local checkout cleanup is blocked or unsafe, the hosted merge remains
complete and the CLI reports the blocker, `repair_status`, `unsafe`,
`next_step`, and deterministic repair options instead of rewriting local
history.

## Preparing Multiple Changes

When you need to scope several changes before starting implementation:

1. Create or update the change records first.
2. Use `verlyn changes activate <change-id> --no-checkout` when you need to bind or create a branch without switching the current checkout.
3. Reorder or insert prep work items through `verlyn work-items update`.
4. Leave the current checkout on the branch you are actively implementing until you intentionally switch work.

## Source Of Truth

Durable Verlyn truth is managed by Verlyn and scoped by entity, project, and
repository:

- repo binding
- changes
- work items
- reviews
- decisions
- runs
- report/evidence records
- delivery state

Repo-local files are source code, governance policy, templates, or temporary
scratch artifacts. Do not reconstruct durable workflow truth from old
`workstream/` files, workspace-local JSON, generated scratch paths, direct
database queries, or chat summaries.

## Completion

Work is not complete until:

- acceptance criteria are satisfied
- applicable verification passes
- change/work-item state is updated through Verlyn
- review notes and remaining risks are recorded
- PR/delivery state is handled through the Verlyn workflow path
- the operator explicitly approves any commit or delivery action that requires approval
