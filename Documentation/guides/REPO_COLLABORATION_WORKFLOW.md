# Repo Collaboration Workflow

Use this when you are a person working inside the target repo.
If you are an assistant, switch to `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`.

## Session-Start Checklist

Before editing anything on an in-progress branch:

1. Identify the applicable Verlyn-managed change, or state explicitly that none applies.
2. Read `RULES.md`.
3. For feature or behavior-changing work, read the change details and proposal through the installed Verlyn CLI or UI first.
4. Read the Verlyn-managed work items for the change and note what is next.
5. Run the codebase health baseline for your stack.
6. Identify the next incomplete acceptance-bearing work item before making edits.

Use Verlyn-managed changes and work items as the live workflow source of truth.
When `verlyn changes create` creates a change, it also creates required starter
work items. These are placeholders for implementation, validation, review, and
handoff; read them, flesh them out for the concrete change, and keep them
current as the work progresses. The seeded `Review findings` item is the
required code/task review ticket when no separate mandatory human review
applies; use it to check for hallucinated behavior, scope drift, unrelated
edits, and mismatches between the implementation and the assigned work.

## Installed CLI Mode

When you are working inside the target repo, use the installed `verlyn` CLI instead of inventing workflow steps by hand:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn target show --json
verlyn changes list
verlyn changes list --owner-scope all --status-scope all
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes activate <change-id>
verlyn work-items list <change-id>
verlyn work-items update <change-id> --creates-json '[{"title":"New work item title"}]'
verlyn work-items update <change-id> --updates-json '[{"task_id":"<existing-work-item-id>","title":"Updated work item title"}]'
verlyn changes deliver <change-id> --merge-method squash
```

Those commands resolve the current repo through Verlyn and keep change, work-item, review, and PR artifacts aligned with Verlyn workflow state. Durable workflow truth is managed by Verlyn; repo-local files are source, governance docs, templates, or temporary scratch artifacts rather than the work-item/change source of truth.

For command intent and optional argument meanings, read
`Documentation/guides/VERLYN_PUBLIC_CLI.md`. Most logged-in repo work should not
need `--profile`, `--server`, `--repo-slug`, or `--target`; those are
bootstrap, diagnostic, or override arguments.

## Installed Public CLI Commands

When working from a terminal or agent session, prefer the installed CLI:

- `verlyn auth status`
- `verlyn workflow assistant-startup --json`
- `verlyn target show --json`
- `verlyn changes list`
- `verlyn changes list --owner-scope all --status-scope all`
- `verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>`
- `verlyn changes activate <change-id>`
- `verlyn changes refresh-branch <change-id>`
- `verlyn work-items list <change-id>`
- `verlyn work-items update <change-id> --creates-json '[{"title":"..."}]'`
- `verlyn work-items update <change-id> --updates-json '[{"task_id":"<existing-work-item-id>","title":"..."}]'`
- `verlyn changes deliver <change-id> --merge-method squash`

The CLI keeps repo identity and backend authorization explicit. Use `--target` only when you need to make local checkout selection explicit.

## Preparing Multiple Changes

When you need to prep several changes before starting code:

1. Create or update each change in Verlyn first.
2. Use Verlyn branch binding to create a work branch without switching away from the branch you are actively using.
3. Reorder prep work items through Verlyn work-item updates instead of editing workflow JSON by hand.
4. Switch branches only when you are ready to start implementation on that specific change.

Manual git branching and direct workflow-file edits are not the normal operating model. If the installed Verlyn product path is blocked, record a Verlyn workflow blocker instead of bypassing it.

## Local-Git Closeout

When Verlyn is running in `local_git` mode, use the app closeout flow instead of treating the change as merged by hand:

1. Use `Workflow -> Change workspace -> Overview -> Local-git closeout`.
2. Let Verlyn checkpoint the work branch first if the branch is still dirty.
3. Merge the assigned work branch into `main`.
4. Choose whether to delete the merged branch immediately or keep it for later cleanup.
5. If you keep it, use `Repo host -> Delete merged branch` later.

Verlyn blocks branch deletion when the branch is current, is the base branch, or is not yet merged into `main`.

Fresh governance installs use the standalone `verlyn` CLI for auth, workflow, clone, review, and delivery commands. `governance` is the only supported repo install mode; changes and work items are managed Verlyn product behavior.

## Multi-Agent Coordination

- Every meaningful change uses one active branch.
- Keep Verlyn-managed review work items current with exact review-scope files when handing work to another reviewer or agent.
- Write findings and dispositions into the change docs before summarizing them elsewhere.

## Session-End Protocol

Before stopping with incomplete work:

1. Update the Verlyn-managed work items.
2. Record the next acceptance-bearing step.
3. Note blockers or unresolved validation failures.
4. Create a session retro.

## Work Routing

Use Verlyn-managed change records when work:
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
