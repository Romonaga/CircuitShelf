# Verlyn Public CLI Guide

This guide explains the installed public `verlyn` CLI used by contributors and
assistants inside a governed repository. It documents the product workflow only:
do not use private Verlyn developer commands, direct database access, or shell
provider tools as substitutes for these commands.

## Context Resolution

Most commands resolve the current user, server, project, and repository from
saved CLI login state plus the current checkout. In normal daily work, after you
are logged in and working inside a known repo, you should not need to pass
`--profile`, `--server`, `--repo-slug`, or `--target`.

Required daily workflow commands should resolve context from login state and
the current checkout. Optional context arguments are overrides; use them only
when you are bootstrapping, diagnosing, or performing explicit recovery:

| Argument | Meaning | Normal use |
|---|---|---|
| `--server` | Verlyn API base URL for `verlyn auth login`; omitted login reuses saved server state when available. | First login, changing servers, or repairing a bad saved server. |
| `--username` | Username for `verlyn auth login`; omitted login prompts for it. | Automation or when avoiding an interactive username prompt. |
| `--profile` | Saved CLI auth profile override. | Diagnostics or automation; avoid for normal repo work. |
| `--repo-slug` | Repository identity override when the current checkout cannot determine the repo. | Diagnostics, automation, or working outside a saved checkout. |
| `--target` | Local checkout path override on commands that expose it. | Diagnostics or explicit checkout selection; not normal workflow. |
| `--json` | Machine-readable output. | Agents, scripts, and tests. Humans can omit it for readable output. |

If a command cannot resolve the repo without an override, treat that as a
target/login/binding issue to repair, not as a reason to hard-code overrides in
normal workflow.

For managed checkout commands, the CLI uses the local target path only to
validate that the checkout maps to an authorized Verlyn repository. Server
workflow mutations bind runs, changes, and work items by the canonical Verlyn
repository identity, not by the developer filesystem path.

## Local Install Command

Downloaded standalone artifacts can install themselves from wherever the user
extracted them:

```bash
./verlyn install
```

On Windows, run the executable from the extracted artifact folder:

```powershell
.\verlyn.exe install
```

The command copies the running executable into the per-user install directory
and persists that directory on PATH unless `--no-update-path` is supplied. It
does not require administrator rights. On Windows, PATH changes made with
`setx` apply to new terminals, so open a new PowerShell or Command Prompt and
verify from another directory:

```bash
verlyn --version
```

Use `--dry-run --json` to inspect the planned source executable, destination,
and PATH entry without changing the machine.

## Governance Pack Commands

Use these when a local repository needs Verlyn governance files
installed or refreshed from the Verlyn API:

```bash
verlyn governance install --target /path/to/repo
verlyn governance refresh --target /path/to/repo
verlyn governance refresh --target /path/to/repo --dry-run --json
```

The CLI fetches the canonical governance pack from Verlyn before
writing local files. Verlyn owns files installed from that pack
except `RULES.md`, which is the repo-owned customization layer. Refresh creates
`RULES.md` when it is missing, preserves it when it exists, and reports
conflicts for locally edited Verlyn-owned files unless `--force` is
supplied.

Verlyn-owned governance files include `AGENTS.md`, `CONTRIBUTING.md`,
`CLAUDE.md`, `.verlyn/runtime_context.json`, `.verlyn/workflow_pack.json`,
`.verlyn/.gitignore`, `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`,
`Documentation/guides/VERLYN_PUBLIC_CLI.md`, the tool-neutral
`.verlyn/agent-skills/verlyn-public-cli.md`, and the Codex adapter at
`.verlyn/.codex/skills/verlyn-public-cli/SKILL.md`. `RULES.md` is intentionally
repo-owned so the repository owner can add project-specific guidance without
forking the Verlyn pack.

Agent and Codex skill files are guidance, not an alternate workflow engine.
They tell AI-assisted tools how to use the installed public CLI, how to reload
governance after compaction, and which commands are required versus optional.
They must defer to `AGENTS.md`, `CONTRIBUTING.md`, and `RULES.md`.

For local-folder onboarding that creates a hosted repository, ask whether the
new hosted repo should be `private` or `public` before creation. Do not infer
visibility from the folder name or local Git state.

## Startup Commands

Use these at the beginning of an assistant session:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn runs --limit 3 --json
```

- `auth status` confirms the saved session, user, API server, expiry, and idle
  state.
- `workflow assistant-startup --json` returns the current repo state, visible
  workflow state, and recommended next action after context compaction or a new
  session.
- `workflow assert-edit-route --json` fails closed when the current checkout is
  not authorized for edits or no active route exists.
- `target show --json` confirms which repo this checkout is bound to.
- `changes list` shows your working changes by default.
- `runs --limit 3 --json` shows recent API-backed analysis/run context.

For diagnostics across visible owners and statuses:

```bash
verlyn changes list --owner-scope all --status-scope all
```

Do not use undocumented shortcuts for all-scope diagnostics.

## Change Workflow

Common change commands:

```bash
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes show <change-id>
verlyn changes update <change-id> --proposal-summary "..." --proposal-scope "..."
verlyn changes activate <change-id>
verlyn changes refresh-branch <change-id>
verlyn changes next
```

- `changes create` creates a draft change. `--change-type` and
  `--effort-band` are required so the change can be categorized and planned.
  It also creates required starter work items for the change.
- `changes show` reads the current durable change record and prints review
  context: description, proposal sections, acceptance criteria, work items,
  review/delivery posture, chain/dependency context, and a next action. With
  `--json`, it returns the sanitized change record plus a structured
  `review_context` object so agents do not have to scrape prose. When the
  command runs from a managed checkout, JSON also includes `client_checkout`
  and preserves the server record as `recorded_branch`; the displayed `branch`
  object is refreshed with current client head data when it can be matched
  safely.
- `changes update` changes metadata such as proposal sections, acceptance
  criteria, priority, dependencies, and owner.
- `changes activate` starts implementation and binds or creates the governed
  work branch. Do this before editing code for a change.
- `changes refresh-branch` repairs or refreshes the bound local work branch.
- `changes next` asks Verlyn for the next unblocked change in the current chain.

Starter work items are required workflow tickets, but they are only a starting
point. After creating a change, run `verlyn work-items list <change-id>` and
flesh out the seeded tasks for the actual scope before implementation,
validation, review, or handoff. Verlyn always includes `Review findings` and
`Finalize handoff`; the first two work items vary by `--change-type`.
`Review findings` is the required code/task review ticket when no separate
mandatory human review applies. Use it to check for hallucinated behavior,
scope drift, unrelated edits, and mismatches between the implementation and
the change ticket/work items before delivery:

| Change type | Seeded first work items |
|---|---|
| `feature` or default | `Implement <title>`; `Validate acceptance for <title>` |
| `bugfix` | `Reproduce and fix <title>`; `Add regression coverage for <title>` |
| `workflow` | `Implement workflow change for <title>`; `Validate workflow behavior for <title>` |
| `api` | `Implement API change for <title>`; `Validate contract and acceptance for <title>` |
| `performance` | `Profile and optimize <title>`; `Validate <title> responsiveness and load behavior` |
| `refactor` | `Refactor <title>`; `Validate <title> behavior parity` |
| `architecture` | `Shape architecture change for <title>`; `Validate dependency and workflow impact for <title>` |
| `security` or `compliance` | `Implement remediation for <title>`; `Validate <title> security posture` |

Work-item commands use JSON arrays so one call can update one or many items:

```bash
verlyn work-items list <change-id>
verlyn work-items update <change-id> --creates-json '[{"title":"Add validation"}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<starter-work-item-id>","notes":"Concrete scope and acceptance for this change."}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
```

Use `--creates-json` for new work items and `--updates-json` for changes to
existing work items. Each item in the JSON array is one work-item mutation.
When seeded implementation and validation items are too generic, update those
existing starter work item IDs in place with concrete scope, acceptance, notes,
and validation guidance before implementation. Do not add duplicates and do
not replace the required starter tickets as the normal path.
`verlyn work-items list <change-id>` and
`verlyn work-items show <change-id> <work-item-id>` are the review surfaces for
task planning. They include parent change context, dependency/chain context,
purpose, blockers, evidence expectations, and next-action guidance where the
backend record supplies it. Their `--json` output exposes the same context in
structured, sanitized fields. `changes show --json` and
`work-items show --json` also place enriched task descriptions and planning
fields on the top-level `tasks`, `work_items`, or `work_item` entries so
consumers do not have to know that `review_context` is the richer source.

## Controlled Run Recovery

Use run abort only when an active run is stuck, mis-scoped, superseded, or
needs operator-controlled recovery:

```bash
verlyn runs abort <run-id>
```

`verlyn runs abort <run-id>` is not part of the normal happy path. Prefer a
properly scoped run, tracked change, and normal gate/deliver/deploy workflow.
When abort is necessary, record the reason in the relevant change, work item,
or handoff notes so later reviewers know why the run was stopped.

## Delivery Versus Deployment

Use the command that matches the outcome you want:

Important: `verlyn changes deliver` and `verlyn changes deploy` both run the
PR step. Both commands create or update the pull request, merge it, and record
source-control closeout. Use `deliver` when you want PR closeout only. Use
`deploy` when you want that same PR closeout followed by provider deployment.

| Command | Outcome |
|---|---|
| `verlyn changes deliver <change-id>` | PR closeout only. It commits local dirty work when `--commit-message` is supplied, pushes with Verlyn-managed provider credentials, opens or updates the pull request, merges it, records closeout, and returns the local checkout to the base branch when safe. It does not deploy. |
| `verlyn changes deploy <change-id>` | PR closeout plus deployment. It runs the same source-control closeout path as `deliver`, then triggers or monitors the configured deployment provider and records deployment evidence. |

When the CLI safely deletes the client-local work branch, it records that
cleanup back to Verlyn so change branch metadata and delivery metrics do not
show stale local branch state.

In human-readable mode, `deliver` and `deploy` print lightweight phase progress
while long hosted operations run, such as PR package preparation, delivery gate
checking, source-control closeout, deployment handoff, provider wait, and
transient deployment recovery. Before PR package work starts, `deliver` prints
that it will create or update the pull request, merge it, and record
source-control closeout without deploying. `deploy` prints that it will run
that same PR closeout first and then deploy. `--json` output remains
machine-readable and does not include progress chatter.

Examples:

```bash
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id> --merge-method squash
```

Delivery options:

| Argument | Meaning |
|---|---|
| `--commit-message` | Commit dirty local changes before hosted delivery. Use it when the local worktree has the intended implementation changes. |
| `--merge-method` | Provider merge strategy: `merge`, `squash`, or `rebase`. The common default in Verlyn workflows is squash. |
| `--keep-remote-branch` | Do not delete the remote work branch after merge. Use only when you intentionally need to preserve it. |
| `--keep-local-branch` | Do not delete the local work branch after merge. The CLI still tries to return to the base branch when safe. |

Deployment-only options:

| Argument | Meaning |
|---|---|
| `--source-ref` | Deploy an already delivered source ref instead of running delivery first. Omit it for normal deliver-and-deploy. |
| `--commit-sha` | Expected commit for an already delivered source ref. Use with `--source-ref` when you need commit verification. |

`--source-ref` and `--commit-sha` are recovery or explicit deployment controls.
They are not required for normal `verlyn changes deploy <change-id>` usage.

If a change explicitly has no governed work branch, `deliver` performs a
no-code closeout. It closes the workflow item without opening a pull request
because no source branch exists to merge.
If an activated governed work branch has no remaining diff against the base
branch, `deliver` records a no-diff/no-code closeout instead of opening a pull
request, then safely removes local and remote work branches when the branch is
tree-equivalent or already contained in the base branch. To repair cleanup
metadata for an old no-PR closeout, use
`verlyn changes recover-delivery <change-id> --no-code --work-branch <branch>`
with the applicable branch-deleted flags.

## Repositories

Use Verlyn to clone repos so the checkout, auth profile, provider credentials,
and repo binding are aligned:

```bash
verlyn repos clone
verlyn repos clone <repo-slug> ./local-folder --project-id <project-id>
```

- Omit `repo_slug` to use interactive project/repo selection when available.
- `destination` defaults to the repository name.
- `--project-id` selects the project binding used for provider credential
  resolution.
- `--branch` selects a branch to clone; omitted clone uses the repository
  default branch.
- `--no-save-checkout` prevents the clone from becoming the saved local checkout
  mapping.
- After cloning, the CLI inspects the checkout for installed Verlyn agent
  guidance and reports local Codex/Claude tool detection. Governed repos may
  include the tool-neutral `.verlyn/agent-skills/verlyn-public-cli.md` and a
  Codex adapter at `.verlyn/.codex/skills/verlyn-public-cli/SKILL.md`. Claude
  continues to use the normal `CLAUDE.md` wrapper and repo governance files; no
  separate Claude skill adapter is installed. The clone command reports these
  paths but does not create untracked adapter files in the checkout.

## Reviews And Gates

Use review and gate commands to keep evidence in Verlyn:

```bash
verlyn workflow gate <change-id> --scope delivery
verlyn reviews record <change-id> --tier changed_file_review --disposition accepted --summary "Changed-file review passed."
```

- `workflow gate` inspects whether a change is ready for a named scope such as
  delivery.
- `reviews record` writes review evidence to the durable Verlyn workflow record.
- Changed-file review evidence is required before real source-control delivery
  unless Verlyn records a no-diff exemption.

When a command fails because the current user cannot see a repo, project, or
change, treat that as a scope or authorization issue. Do not switch to private
developer commands or direct provider tools to bypass Verlyn.
