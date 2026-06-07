# Verlyn Assistant Mode

Use this guide when you are an assistant working inside the target repo.

For startup order, auth/session setup, repo slug discovery, and supported Verlyn API usage, read `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md` first. This guide covers the day-to-day session loop after startup is complete.

Terminology note: Verlyn’s operator-facing UI and helper commands now use `Workstream`, `Work item`, and `Evidence`. Some internal API route names still retain `workflow` and `task`.

## Start Here

Read `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md`, then `RULES.md`, then run:

`python scripts/verlyn_workflow.py assistant-startup --json`
`python scripts/verlyn_workflow.py context --json`
`python scripts/verlyn_workflow.py assert-edit-route`

Then inspect the current workflow state before suggesting or editing anything.

## Command Priority

1. `python scripts/verlyn_workflow.py ...`
2. Other repo-local helper scripts in `scripts/` or `scripts/repo_helpers/workflow/`
3. Raw `verlyn --target "$PWD" ...` only when the helper does not wrap what you need yet

## Source Of Truth

- Verlyn-managed DB-backed change, work-item, review, and run state
- Baseline contract specs through Verlyn's relational baseline-spec surface only; do not use repo-local `workstream/specs/` as durable truth
- Managed Verlyn artifacts in the central workspace or `.verlyn/` when explicitly configured
- Not chat summaries

Do not treat repo-local `workstream/specs/` as ambient context or a supported source of truth. Load baseline specs only through Verlyn's relational baseline-spec APIs or helpers.

## Session Loop

1. Read `AGENTS.md`, `RULES.md`, and the active change details from Verlyn.
2. Run `python scripts/verlyn_workflow.py assistant-startup --json` so the governed startup contract is reloaded and the visible receipt is refreshed.
3. Run `python scripts/verlyn_workflow.py context --json`.
4. Run `python scripts/verlyn_workflow.py assert-edit-route` before code edits. If it fails, use `python scripts/verlyn_workflow.py use-change <change-id>` or record an explicit exception with `python scripts/verlyn_workflow.py direct-work --reason "..."`.
5. If needed, inspect `python scripts/verlyn_workflow.py status` and `python scripts/verlyn_workflow.py inbox`.
6. If the work needs a new delivery record:
   `python scripts/verlyn_workflow.py start-change <label-or-title-hint> --title "..."`
   For lower-level workflow mutations, use:
   `python scripts/verlyn_workflow.py change <change-id> --status active`
   `python scripts/verlyn_workflow.py changes create <label-or-title-hint> --title "..."`
   `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"...","owner":"<name>"}'` to create DB-allocated work items
   `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"...","owner":"<name>"}'` to update existing work items
7. If work already exists:
   `python scripts/verlyn_workflow.py pickup-work-item <change-id> <work-item-id> --owner "<name>"`
8. Do the work, verification, and work-item updates.
9. Prepare review and PR artifacts:
   `python scripts/verlyn_workflow.py handoff-review <change-id>`
   `python scripts/verlyn_workflow.py prepare-pr <change-id>`
10. When the change is actually ready to land, prefer the hosted workflow wrapper over raw git or gh:
   `python scripts/verlyn_workflow.py deliver-change <change-id>`
   Use `deliver-change` for the normal "close out this one approved change" path. Reach for the batch commands only when you are intentionally working the repo-level queue or testing automation behavior across multiple changes.

## Preparing Multiple Changes

When you need to scope several changes before starting implementation:

1. Create or update the change records first.
2. Prefer Verlyn API or helper flows that bind a branch without switching the current checkout.
3. Reorder or insert prep work items through the work-item API instead of patching durable records by hand.
4. Leave the current checkout on the branch you are actively implementing until you intentionally switch work.

Manual git branch creation is fallback-only when the Verlyn product path is blocked or the change is repairing that exact path.

## When To Use Raw verlyn

Use raw `verlyn --target "$PWD" ...` only when:
- the repo-local wrapper does not expose the command yet
- you need a lower-level engine or diagnostics path
- you are debugging Verlyn itself

The helper automatically points Verlyn at this repo as the target.

## Requirements

- Verlyn must be installed locally so the `verlyn` command is available.
- Fresh governance installs now seed the central Verlyn checkout path into `.verlyn/workflow_pack.json`, so generated repo-local helpers should normally work without extra shell setup. If the central checkout moved or an older generated repo predates that metadata, repair it from the central Verlyn checkout with `python3 cli.py --target /path/to/repo install --mode governance --force`. `governance` is the only supported repo install mode; changes and work items are DB-backed Verlyn product behavior.

## Expectations

- Keep the change record, work items, and review notes current while you work.
- Do not treat chat summaries as the source of truth; use Verlyn-managed workflow state.
- Do not commit or push without explicit human approval.
