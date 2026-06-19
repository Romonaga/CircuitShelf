# Verlyn Public CLI Agent Skill

Use the installed public `verlyn` CLI as the control path for governed
repository work. Treat the target repository's governance files as
authoritative; this reference must not override repo-local policy.

The hierarchy is strict: Public CLI first, API-backed workflow context, no
direct PostgreSQL access, no private helper scripts, no provider secret
handling, and no bypassing gates.

## Start Every Governed Session

Read the repo governance files before editing or making workflow claims:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md` when present
6. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` when present
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md` when present

After session compaction, compressed-summary recovery, or any resume where governance may be stale, reread the governed files and visibly tell the operator:

```text
Governance was reloaded and required repo rules were reread.
```

Then run the installed public CLI startup checks from the repository root:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn changes list --owner-scope all --status-scope all
verlyn runs --limit 3 --json
```

Use the JSON output to confirm auth, repo binding, current branch, visible changes, runs, and edit-route status.

These startup commands are required for normal governed sessions. Do not
replace them with direct database queries, local workflow-file inspection, or
private Verlyn maintenance scripts.

## Required Versus Optional CLI Inputs

Normal checkout-bound work should not need context overrides. The required path
is to let the installed CLI resolve auth, repository, project, and checkout
state from the current directory and saved profile:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn workflow gate <change-id> --scope delivery
```

Optional overrides are only for bootstrap, diagnostics, automation, or explicit
recovery:

| Override | Use only when |
|---|---|
| `--server` | Logging in to a new Verlyn API server or repairing saved server state. |
| `--profile` | Diagnosing or automating against a specific saved auth profile. |
| `--repo-slug` | Working outside a recognized checkout or repairing target resolution. |
| `--target` | Making a checkout path explicit for diagnostics or install/refresh. |
| `--source-ref` | Deploying an already delivered source ref instead of normal deliver-and-deploy. |
| `--commit-sha` | Verifying the expected commit for an explicit `--source-ref` deployment. |

Do not add optional overrides to routine commands just to make a command pass.
If context cannot be resolved without an override in normal repo work, treat
that as a binding or auth problem to repair through Verlyn.

## Governance Pack Installation

Use the API-backed governance commands when a repository needs Verlyn
governance files installed or refreshed:

```bash
verlyn governance install --target <repo>
verlyn governance refresh --target <repo>
verlyn governance refresh --target <repo> --dry-run --json
```

Verlyn owns files installed from the governance pack except `RULES.md`, which
is the repo-owned customization layer. Verlyn-owned files include `AGENTS.md`,
`CONTRIBUTING.md`, `CLAUDE.md`, `.verlyn/runtime_context.json`,
`.verlyn/workflow_pack.json`, `.verlyn/.gitignore`,
`Documentation/guides/VERLYN_AGENT_WORKFLOW.md`,
`Documentation/guides/VERLYN_PUBLIC_CLI.md`, this tool-neutral skill file, and
the Codex adapter at `.verlyn/.codex/skills/verlyn-public-cli/SKILL.md`.

Skill files guide AI-assisted work; they are not substitutes for the public CLI
and they must defer to `AGENTS.md`, `CONTRIBUTING.md`, and `RULES.md`.

## Respect Edit Routing

Before manual code edits, confirm `verlyn workflow assert-edit-route --json` allows editing.

If the route is blocked because no active change is bound, create or activate the applicable Verlyn change before editing:

```bash
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn work-items update <change-id> --updates-json '[{"task_id":"<starter-work-item-id>","notes":"Concrete scope, acceptance, and validation details."}]'
verlyn changes activate <change-id>
```

If repo policy allows direct work for a narrow documentation or inspection task, record the direct-work reason through the product path required by the repo. Do not treat a missing active change as permission to edit from memory.

## Work Through Verlyn Records

Use Verlyn-managed records as the durable workflow truth:

- Inspect active change details before feature, behavior, API, workflow, governance, or bug-fix work.
- Update starter work items in place with concrete scope before implementation.
- Keep work-item status current while working.
- Record review findings and dispositions in Verlyn before summarizing them in chat.
- Record skipped checks, residual risks, and handoff notes before closeout.

Common commands:

```bash
verlyn changes list
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn work-items show <change-id> <work-item-id> --json
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn reviews record <change-id> --tier 1 --disposition accepted --summary "Reviewed changed files and verification evidence."
verlyn workflow gate <change-id> --scope delivery
```

Before real source-control delivery, make sure changed-file review evidence is
durable in Verlyn. If the delivery gate reports missing `changed_file_review`,
review the changed files against the active change and work items, then record:

```bash
verlyn reviews record <change-id> --tier changed_file_review --disposition accepted --summary "Changed-file review passed."
```

## Deliver Or Deploy Through Verlyn

Use the installed Verlyn hosted closeout path when the change is ready.

- Use `deliver` for PR/source-control closeout without deployment.
- Use `deploy` for PR/source-control closeout followed by configured provider deployment.

```bash
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id> --merge-method squash
```

If local branch repair or checkout cleanup is blocked, follow the deterministic repair command reported by Verlyn instead of using raw Git or provider tools as a bypass.

Use `verlyn runs abort <run-id>` only for controlled recovery of a stuck,
mis-scoped, or superseded active run. It is not part of normal happy-path work;
record the reason on the relevant change, work item, or handoff notes.

## Avoid Unsupported Paths

Do not use private Verlyn developer commands, direct database access, direct workflow-file edits, or shell provider tools such as `gh` as substitutes for public CLI workflow paths.

Do not ask users for provider tokens. Verlyn resolves provider credentials through its product workflow.

Do not reconstruct durable workflow truth from chat summaries, generated scratch files, old local workstream files, or guessed branch names.

When the public CLI path is missing or blocked, record the blocker as workflow feedback in Verlyn and explain the blocked state to the operator.
