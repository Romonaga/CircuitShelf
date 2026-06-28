# Verlyn Agent Workflow

Use this guide when an assistant or agent is working inside this repository.
`AGENTS.md` is authoritative for policy, `CONTRIBUTING.md` is authoritative for
commit protocol, and `RULES.md` contains repo-owned guidance. Use
`Documentation/guides/VERLYN_PUBLIC_CLI.md` as the detailed command reference.

## Reload Order

Read, in order:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md`
6. this guide
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md`
8. active change details from Verlyn when work already exists

After compaction, compressed-summary recovery, or any stale-context resume,
reread the governed files and visibly tell the operator:

> Governance was reloaded and required repo rules were reread.

## Required Startup

Run these before suggesting edits or changing files:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn changes list --owner-scope all --status-scope all
verlyn runs --limit 3 --json
```

These commands verify CLI auth, repo binding, current branch, active change
route, visible work, and recent run context. If auth, target binding, or edit
routing fails, repair that public Verlyn path before editing.

Inspect `workflow_hint` first when present. It is the canonical chain-aware
resolver payload shared by `workflow assistant-startup --json`,
`workflow inbox --json`, and `changes next --json`. Use
`selected_change`, `recommended_action`, `recommended_command`, `safe_to_edit`,
`reason_code`, `chain_context`, `blocked_changes`, `ready_roots`,
`current_branch_context`, `resolver_status`, and `degraded_reason` before
guessing from flat lists. Product hints such as `recommended_next_action`,
`next_action`, `recommended_next_command`, `review_context`, `task_rollup`,
`workflow_gate`, `repair_status`, and `next_step` guide the next command but
never bypass repo policy.

## Control Path

1. Installed public `verlyn` CLI commands.
2. Web UI workflow surfaces for run creation, onboarding, and settings.
3. Stop and record a Verlyn workflow blocker when the product path is missing
   or blocked.

Do not use private Verlyn maintenance commands, direct database access, direct
workflow-record edits, provider-secret handling, or shell provider tools such
as `gh` as substitutes for Verlyn's installed product workflow.

Normal Verlyn commands are repo-scoped from the current checkout plus the saved
CLI login profile. Avoid `--profile`, `--server`, `--repo-slug`, and `--target`
unless bootstrapping, diagnosing, automating outside a checkout, or performing
explicit recovery. If normal repo work needs an override to pass, treat it as
auth, repo binding, or checkout drift to repair through Verlyn.

For vendor-specific delivery changes, query
`/api/repos/{repo_slug}/delivery/providers` before changing provider behavior.
Railway is the first concrete provider slice using Verlyn's shared provider
plugin core and manifest-backed provider contract.

## Auth And Repo Binding

Normal login:

```bash
verlyn auth login --server <verlyn-api-url> --username <user>
verlyn auth status
```

When login runs from a repository checkout, inspect any `governance_status`
payload and follow its `recommended_next_command`.

For first checkout of a repo already attached to a Verlyn project:

```bash
verlyn repos clone <repo-slug> ./local-folder --project-id <project-id>
```

CLI auth is user/profile scoped. Entity, project, repository, workflow, and
provider credential resolution stay in Verlyn's backend. Local checkout paths
are user-machine preferences, not repository identity.

## Change And Work-Item Flow

Use installed `verlyn` commands for tracked work:

```bash
verlyn changes list
verlyn changes show <change-id> --json
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes update <change-id> --proposal-summary "..." --proposal-scope "..."
verlyn changes activate <change-id>
verlyn changes refresh-branch <change-id>
verlyn work-items list <change-id>
verlyn work-items update <change-id> --creates-json '[{"title":"Add validation"}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<starter-work-item-id>","notes":"Concrete scope and acceptance for this change."}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn reviews record <change-id> --tier changed_file_review --disposition accepted --summary "Changed-file review passed."
verlyn workflow gate <change-id> --scope delivery
```

Creation and activation are separate. Draft changes are planning-only: agents
may inspect files and flesh out change/work-item records, but must not write
files, run write-formatters, generate source artifacts, or apply patches until
`verlyn changes activate <change-id>` has bound the branch and
`verlyn workflow assert-edit-route --json` returns `allowed: true` for that
change.

`verlyn changes create` seeds required starter work items. Update those
starters in place with concrete scope, acceptance, notes, and validation
guidance before implementation. `Review findings` is the required code/task
review ticket when no separate human review applies. Use it to check scope,
unrelated edits, hallucination risk, and verification before closeout.

## Governance Pack

Use API-backed governance commands:

```bash
verlyn governance install --target <repo>
verlyn governance refresh --target <repo>
verlyn governance refresh --target <repo> --dry-run --json
```

Verlyn owns installed governance pack files except repo-owned `RULES.md`.
Refresh preserves `RULES.md` and overwrites generated files so stale local
guidance returns to the current contract.

## Source Of Truth

Durable Verlyn truth is managed by Verlyn and scoped by entity, project, and
repository:

- repo binding
- changes and work items
- reviews, decisions, and handoffs
- runs and evidence records
- delivery state

Repo-local files are source code, governance policy, templates, or temporary
artifacts. Do not reconstruct durable workflow truth from local JSON, old
`workstream/` files, direct database queries, generated scratch paths, or chat
summaries.

## Closeout

Use the installed hosted closeout path:

```bash
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id> --merge-method squash
```

`deliver` creates or updates the PR, merges it, records source-control
closeout, and repairs the local checkout when safe. It does not deploy.
`deploy` runs the same closeout and then triggers or monitors the configured
provider. Pass `--source-ref` and optional `--commit-sha` only for explicit
deployment recovery of an already delivered source ref.

Use `verlyn runs abort <run-id>` only for controlled recovery of a stuck,
mis-scoped, or superseded active run, and record the reason on the relevant
change, work item, or handoff.

## Completion

Work is not complete until acceptance criteria are satisfied, applicable
verification passes, Verlyn work items and review records are current, and any
remaining risks or skipped checks are recorded.
