# Repo Collaboration Workflow

Use this when you are a person working inside the target repo.
If you are an assistant, switch to `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md`, then `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`.

## Session-Start Checklist

Before editing anything on an in-progress branch:

1. Identify the applicable DB-backed Verlyn change, or state explicitly that none applies.
2. Read `RULES.md`.
3. For feature or behavior-changing work, read the change details and proposal through the Verlyn helper or UI first.
4. Read the DB-backed work items for the change and note what is next.
5. Run the codebase health baseline for your stack.
6. Identify the next incomplete acceptance-bearing work item before making edits.

Use Verlyn-managed changes and work items as the live workflow source of truth.

## Repo-Local Mode

When you are working inside the target repo, use the repo-local Verlyn wrapper instead of inventing workflow steps by hand:

```bash
python3 scripts/verlyn_workflow.py context --json
python3 scripts/verlyn_workflow.py assert-edit-route
python3 scripts/verlyn_workflow.py status
python3 scripts/verlyn_workflow.py inbox
python3 scripts/verlyn_workflow.py start-change <label-or-title-hint> --title "Short title"
python3 scripts/verlyn_workflow.py use-change <change-id>
python3 scripts/verlyn_workflow.py direct-work --reason "policy/doc-only maintenance"
python3 scripts/verlyn_workflow.py change <change-id> --status active
python3 scripts/verlyn_workflow.py changes create <label-or-title-hint> --title "Short title"
python3 scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"New work item title"}'
python3 scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"Updated work item title"}'
python3 scripts/verlyn_workflow.py pickup-work-item <change-id> <work-item-id> --owner "<name>"
python3 scripts/verlyn_workflow.py prepare-pr <change-id> --style all
python3 scripts/verlyn_workflow.py deliver-change <change-id>
python3 scripts/verlyn_workflow.py context --change-id <change-id> --json
```

Those commands pin the current repo automatically and keep the change, work-item, review, and PR artifacts aligned with Verlyn workflow state. Durable workflow truth is DB-backed; repo-local files are helper scripts, docs, templates, or temporary scratch artifacts rather than the work-item/change source of truth.
`assert-edit-route` is the helper-side guard: if it fails, do not continue into manual code edits until the repo-local route is tied to an active change or an explicit direct-work exception.

## Verlyn Helper Commands

When working from a terminal or agent session, prefer the repo-local helper wrapper:

- `python scripts/verlyn_workflow.py context --json`
- `python scripts/verlyn_workflow.py assert-edit-route`
- `python scripts/verlyn_workflow.py status`
- `python scripts/verlyn_workflow.py inbox`
- `python scripts/verlyn_workflow.py start-change <label-or-title-hint> --title "..."`
- `python scripts/verlyn_workflow.py use-change <change-id>`
- `python scripts/verlyn_workflow.py direct-work --reason "policy/doc-only maintenance"`
- `python scripts/verlyn_workflow.py clear-route`
- `python scripts/verlyn_workflow.py change <change-id> --status active`
- `python scripts/verlyn_workflow.py changes create <label-or-title-hint> --title "..."`
- `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"..."}'` to create DB-allocated work items
- `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"..."}'` to update existing work items
- `python scripts/verlyn_workflow.py pickup-work-item <change-id> <work-item-id> --owner "<name>"`
- `python scripts/verlyn_workflow.py handoff-review <change-id>`
- `python scripts/verlyn_workflow.py prepare-pr <change-id>`
- `python scripts/verlyn_workflow.py deliver-change <change-id>`

The helper keeps the repo root and target wiring consistent. Use `changes ...` for lower-level repo-native change and work-item mutations, and use raw `verlyn --target ...` commands only when you need something the helper still does not wrap.

## Preparing Multiple Changes

When you need to prep several changes before starting code:

1. Create or update each change in Verlyn first.
2. Use Verlyn branch binding to create a work branch without switching away from the branch you are actively using.
3. Reorder prep work items through Verlyn work-item updates instead of editing workflow JSON by hand.
4. Switch branches only when you are ready to start implementation on that specific change.

Manual git branching and direct workflow-file edits remain escape hatches for blocked product paths, not the normal operating model.

## Local-Git Closeout

When Verlyn is running in `local_git` mode, use the app closeout flow instead of treating the change as merged by hand:

1. Use `Workflow -> Change workspace -> Overview -> Local-git closeout`.
2. Let Verlyn checkpoint the work branch first if the branch is still dirty.
3. Merge the assigned work branch into `main`.
4. Choose whether to delete the merged branch immediately or keep it for later cleanup.
5. If you keep it, use `Repo host -> Delete merged branch` later.

Verlyn blocks branch deletion when the branch is current, is the base branch, or is not yet merged into `main`.

Fresh governance installs seed the central Verlyn checkout path into `.verlyn/workflow_pack.json`, so generated repo-local wrappers should resolve Verlyn without extra shell setup. If the central checkout moved or an older generated repo predates that metadata, repair it from the central Verlyn checkout with `python3 cli.py --target /path/to/repo install --mode governance --force`. `governance` is the only supported repo install mode; changes and work items are DB-backed Verlyn product behavior.

## Multi-Agent Coordination

- Every meaningful change uses one active branch.
- Keep DB-backed review work items current with exact review-scope files when handing work to another reviewer or agent.
- Write findings and dispositions into the change docs before summarizing them elsewhere.

## Session-End Protocol

Before stopping with incomplete work:

1. Update the DB-backed work items.
2. Record the next acceptance-bearing step.
3. Note blockers or unresolved validation failures.
4. Create a session retro.

## Work Routing

Use workstream change records when work:
- changes behavior
- affects a contract, schema, or public interface
- spans multiple components
- is architecture-significant

Use direct implementation only for:
- tightly scoped bug fixes with no contract change
- internal refactors
- documentation or workflow edits that do not change policy

## Review Tiers

- Tier 1: validation check for narrow fixes
- Tier 2: implementation review for normal feature work
- Tier 3: architecture review for multi-component or dependency changes
- Tier 4: contract/security/governance review for high-risk or canonical changes

If multiple tiers apply, use the highest.

## Completion Gates

Work is not complete until:
- acceptance criteria are satisfied
- required verification passes
- review findings and handoff state are recorded
- unresolved issues are called out explicitly
