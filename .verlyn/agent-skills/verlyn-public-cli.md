# Verlyn Public CLI Agent Skill

Use the installed public `verlyn` CLI as the control path for governed
repository work. Repo-local `AGENTS.md`, `CONTRIBUTING.md`, and `RULES.md`
remain authoritative.

Core rule: public CLI first, API-backed workflow context, no direct PostgreSQL
access, no private helper scripts, no provider-secret handling, no raw provider
tool bypasses, and no delivery-gate bypasses.

## Session Start

Read, in order:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md` when present
6. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` when present
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md` when present

After compaction, compressed-summary recovery, or any stale-context resume,
reread those files and visibly tell the operator:

```text
Governance was reloaded and required repo rules were reread.
```

Then run from the repository root:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn changes list --owner-scope all --status-scope all
verlyn runs --limit 3 --json
```

Inspect `workflow_hint` first when present. Use `selected_change`,
`recommended_action`, `recommended_command`, `safe_to_edit`, `reason_code`,
`chain_context`, `blocked_changes`, `ready_roots`, `current_branch_context`,
`resolver_status`, and `degraded_reason` before guessing from flat lists.
Other hints such as `recommended_next_action`, `next_action`,
`recommended_next_command`, `review_context`, `task_rollup`, `workflow_gate`,
`repair_status`, and `next_step` are still useful, but they do not bypass repo
policy.

## Context And Overrides

Normal Verlyn commands are repo-scoped from the current checkout plus the saved
CLI login profile. Let the installed CLI resolve user, entity, project,
repository, branch, and active change.

Use overrides only for bootstrap, diagnostics, automation outside a checkout,
or explicit recovery:

| Override | Use only when |
|---|---|
| `--server` | Logging in to or repairing a saved API server. |
| `--profile` | Diagnosing or automating a specific saved auth profile. |
| `--repo-slug` | Working outside a recognized checkout or repairing target resolution. |
| `--target` | Making checkout selection explicit for diagnostics, install, or refresh. |
| `--source-ref` | Deploying an already delivered source ref. |
| `--commit-sha` | Verifying an explicit deployment source ref. |

If routine repo work needs an override to pass, treat that as auth, target, or
binding drift to repair through Verlyn.

## Edit Routing

Before any file write, generated source artifact, formatter write, patch, or
manual code edit, confirm:

```bash
verlyn workflow assert-edit-route --json
```

Draft changes are planning-only. Activate the applicable change first:

```bash
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn changes activate <change-id>
```

Editing is allowed only when the change is active, the branch is bound, and
`assert-edit-route` reports `allowed: true` for that change. If the route is
blocked, repair it through Verlyn instead of continuing on `main` or an
unbound branch.

## Work Records

Use Verlyn-managed records as durable workflow truth:

- inspect active change details before feature, behavior, API, workflow,
  governance, or bug-fix work
- flesh out seeded starter work items before implementation
- keep work-item status current while working
- record skipped checks, residual risks, review findings, and dispositions in
  Verlyn before summarizing them in chat

Common commands:

```bash
verlyn changes list
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn work-items show <change-id> <work-item-id> --json
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn reviews record <change-id> --tier changed_file_review --disposition accepted --summary "Changed-file review passed."
verlyn workflow gate <change-id> --scope delivery
```

## Governance Pack

Use API-backed governance commands:

```bash
verlyn governance install --target <repo>
verlyn governance refresh --target <repo>
verlyn governance refresh --target <repo> --dry-run --json
```

Verlyn owns generated pack files except repo-owned `RULES.md`. Refresh
preserves `RULES.md` and overwrites generated files such as `AGENTS.md`,
`CONTRIBUTING.md`, `CLAUDE.md`, `.verlyn/runtime_context.json`,
`.verlyn/workflow_pack.json`, `.verlyn/.gitignore`,
`Documentation/guides/VERLYN_AGENT_WORKFLOW.md`,
`Documentation/guides/VERLYN_PUBLIC_CLI.md`, this skill file, and the Codex
adapter at `.verlyn/.codex/skills/verlyn-public-cli/SKILL.md`.

## Closeout

Use Verlyn hosted closeout:

```bash
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id> --merge-method squash
```

Use `deliver` for PR/source-control closeout only. Use `deploy` for that same
closeout plus provider deployment. If checkout cleanup or hosted delivery is
blocked, follow Verlyn's reported repair path and record the blocker as
workflow feedback.

`verlyn runs abort <run-id>` is controlled recovery for stuck, mis-scoped, or
superseded active runs, not normal happy-path work. Record the reason on the
relevant change, work item, or handoff.
