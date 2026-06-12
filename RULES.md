# Project Rules

This is the user-editable workflow guidance file for this repo.

It exists to hold project-specific operating rules without making contributors learn Verlyn internals.

## Precedence

- `CONTRIBUTING.md` is authoritative for commit and branch protocol.
- `AGENTS.md` is authoritative for repo-wide routing, verification, and completion policy.
- `.verlyn/runtime_context.json` is the compact assistant/runtime summary for compressed sessions.
- `RULES.md` is the editable project-level guidance layer for this repo.
- Tool-specific wrappers such as `CLAUDE.md` must defer to the files above.

If a rule in this file conflicts with `AGENTS.md` or `CONTRIBUTING.md`, the higher-priority file wins.

## Starter Rules

- Follow the resolved Verlyn workflow posture for the active project or repo instead of inventing side paths.
- Before behavior-changing or workflow-changing code, create or use an active change and work through its work items.
- Run `verlyn auth status` and `verlyn target show --json` at session start so the local CLI identity and repo binding are visible before editing.
- Inspect the current run, change, and work-item state with installed `verlyn` CLI/API commands before editing.
- Prefer installed Verlyn CLI/API commands over retyping workflow steps from memory.
- For hosted GitHub closeout, use Verlyn's hosted delivery routes first. If a session cannot see the repo, fix the scope or switch to a repo-visible owner session instead of falling back to shell tools like `gh`.
- Once a Verlyn change is active, do not use raw `git` commands for branch repair, PR delivery, merge, or workflow state changes. Use the installed Verlyn CLI/API path first. If the Verlyn path fails or is missing needed behavior, stop and report the blocker so a Verlyn change can be created to fix Verlyn instead of bypassing it.
- Use `verlyn changes deliver <change-id>` for full hosted closeout. `verlyn changes publish-pr` is PR-only and must not be treated as merge or Verlyn closeout.
- Keep change, task, review, and handoff records current while work is in progress.
- Treat workflow friction as real product work: if the process is confusing, log it as a change or task instead of bypassing it.
- Prefer component-first design when the same UI or workflow pattern appears in multiple places or is likely to drift: extract a reusable component early instead of duplicating code. This keeps tests narrower, reduces code bloat, and lowers drift risk.
- When workflow, API, startup order, or installed CLI behavior changes, update `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md` in the same change so fresh assistants do not have to infer the new path from source.
- Do not commit or merge without explicit human approval.

## Editing Guidance

- Use this file for project-specific workflow guidance that humans and assistants should read every session.
- Use `.verlyn/runtime_context.json` for compact assistant/runtime context that should survive session compression.
- Use Verlyn's structured project rules for machine-resolved workflow behavior and defaults.
- Keep this file concise, durable, and readable by a human at the start of a session.
