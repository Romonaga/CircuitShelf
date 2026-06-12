# Verlyn Assistant Mode

Use this guide when you are an assistant working inside the target repo.

For startup order, auth/session setup, repo slug discovery, and supported Verlyn API usage, read `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md` first. This guide covers the day-to-day session loop after startup is complete.

Terminology note: Verlyn’s operator-facing UI and helper commands now use `Workstream`, `Work item`, and `Evidence`. Some internal API route names still retain `workflow` and `task`.

## Start Here

Read `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md`, then `RULES.md`, then run:

`verlyn auth status`
`verlyn target show --json`
`verlyn changes list`

Then inspect the current workflow state before suggesting or editing anything.

## Command Priority

1. Installed `verlyn` CLI commands
2. Verlyn API routes when the installed CLI does not expose the exact operation
3. Web UI workflow surfaces for run creation, onboarding, and settings

## Source Of Truth

- Verlyn-managed DB-backed change, work-item, review, and run state
- Baseline contract specs through Verlyn's relational baseline-spec surface only; do not use repo-local `workstream/specs/` as durable truth
- Managed Verlyn artifacts in the central workspace or `.verlyn/` when explicitly configured
- Not chat summaries

Do not treat repo-local `workstream/specs/` as ambient context or a supported source of truth. Load baseline specs only through Verlyn's relational baseline-spec APIs or helpers.

## Session Loop

1. Read `AGENTS.md`, `RULES.md`, and the active change details from Verlyn.
2. Run `verlyn auth status` and `verlyn target show --json` so identity and repo binding are explicit.
3. Run `verlyn changes list`, `verlyn runs --limit 3 --json`, and `verlyn work-items list <change-id>` as needed.
4. Do not edit until the repo is authorized for the authenticated user and the applicable Verlyn change is active.
5. If no change applies, record an explicit direct-work reason in the change/review trail before editing.
6. If the work needs a new delivery record:
   `verlyn changes create --title "..."`
   For lower-level workflow mutations, use:
   `verlyn changes activate <change-id>`
   `verlyn work-items update <change-id> --creates-json '[{"title":"...","owner":"<name>"}]'` to create DB-allocated work items
   `verlyn work-items update <change-id> --updates-json '[{"task_id":"<existing-work-item-id>","title":"...","owner":"<name>"}]'` to update existing work items
7. If work already exists:
   `verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"in_progress","owner":"<name>"}]'`
8. Do the work, verification, and work-item updates.
9. When the change is actually ready to land, prefer the hosted workflow wrapper over raw git or gh:
   `verlyn changes publish <change-id> --merge-method squash`
   Use `changes publish` for the normal "close out this one approved change" path. It opens or updates the PR, merges it, records closeout, and cleans up branches according to the selected flags. Use `changes publish-pr` only when you intentionally want a PR without merge or closeout.

## Preparing Multiple Changes

When you need to scope several changes before starting implementation:

1. Create or update the change records first.
2. Prefer Verlyn API or helper flows that bind a branch without switching the current checkout.
3. Reorder or insert prep work items through the work-item API instead of patching durable records by hand.
4. Leave the current checkout on the branch you are actively implementing until you intentionally switch work.

Manual git branch creation is fallback-only when the Verlyn product path is blocked or the change is repairing that exact path.

## When To Use Raw verlyn

Use `verlyn --target "$PWD" ...` only when the current directory is not the desired repo context or you need to make target selection explicit for diagnostics.

## Requirements

- Verlyn must be installed locally so the `verlyn` command is available.
- Governance installs do not vendor Verlyn Python source into this repo. Install the standalone `verlyn` CLI once on the workstation and use it for auth, workflow, clone, review, and delivery commands. `governance` is the only supported repo install mode; changes and work items are DB-backed Verlyn product behavior.

## Expectations

- Keep the change record, work items, and review notes current while you work.
- Do not treat chat summaries as the source of truth; use Verlyn-managed workflow state.
- Do not commit or push without explicit human approval.
