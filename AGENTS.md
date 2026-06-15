# [REPO] - Agent Operating Rules

Auto-read by all agents. This is the authoritative source for routing, verification, and completion policy. Project-specific guidance in `RULES.md` and tool-specific files such as `CLAUDE.md` must defer to this file for policy. Use `.verlyn/runtime_context.json` as the compact runtime summary when you need the current repo contract in compressed form.

## Directive Hierarchy

| Priority | File | Role |
|---|---|---|
| 1 | `CONTRIBUTING.md` | Authoritative human workflow and commit protocol |
| 2 | `AGENTS.md` | Repo-wide routing, verification, and completion policy |
| 3 | `RULES.md` | Editable project-level guidance; it defers to `AGENTS.md` and `CONTRIBUTING.md` |
| 4 | `CLAUDE.md` | Tool-specific notes; they defer to higher-priority files |
| 5 | Workflow guides and verified command docs | Command reference only after installed public `verlyn` CLI commands are checked |

Rule: if a policy appears in both `AGENTS.md` and a tool-specific file, `AGENTS.md` wins.

## Operator Routing

Before starting a session, read the guide that matches how you are working:
- `repo contributor mode`: use the installed public `verlyn` CLI from this checkout
- `assistant mode`: `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`

Use `Documentation/guides/VERLYN_PUBLIC_CLI.md` as the installed public CLI
command reference before guessing command behavior or optional flags.

Always read `Documentation/AI_USAGE_POLICY.md` before using AI-assisted paths.

## Default Orders

1. Read `CONTRIBUTING.md` before touching commits or branches.
2. Read `RULES.md` before starting work so project-level guidance is in view.
3. Read `.verlyn/runtime_context.json` when it exists so the compact assistant/runtime contract is in view.
4. Run `verlyn auth status`, `verlyn workflow assistant-startup --json`, and `verlyn target show --json` to confirm the installed public CLI is authenticated, routed, and bound to this repo.
5. Inspect active workflow state with installed public CLI commands such as `verlyn changes list`, `verlyn changes list --owner-scope all --status-scope all` for all-visible diagnostics, `verlyn runs --limit 3 --json`, and `verlyn work-items list <change-id>`.
6. Decide whether the work needs an active Verlyn change record.
7. For feature or behavior-changing work, inspect the active change details through Verlyn before implementation.
8. Run this repository's normal test, lint, or health baseline before editing when one is documented.
9. Do not call work complete until its acceptance criteria are satisfied and recorded.
10. Do not commit without explicit human approval.

After session compaction, summary recovery, or any other context-compressed resume, reread `AGENTS.md`, `RULES.md`, `.verlyn/runtime_context.json`, `Documentation/AI_USAGE_POLICY.md`, and `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` before continuing so the assistant relearns the current system contract instead of relying on stale summarized context. The first user-facing response after that reload must explicitly say that governance was reloaded and required repo rules were reread; do not leave this only in hidden command output, receipt files, or web-only indicators.

## Work Routing

| Trigger | Route |
|---|---|
| New feature, behavior change, API change | Create or use an active change record and inspect its current details through Verlyn before implementation |
| Bug fix, regression | Create or use the nearest active change plus targeted regression validation |
| Refactor | Direct if no contract change; use a change record if behavior or contracts move |
| Documentation or workflow files | Direct unless the policy itself changes |
| Architecture-significant change | Run architecture review before implementation |
| Canonical policy/spec change | Require independent review before merge |

## Operating Rules

- Record review findings and dispositions in Verlyn reviews or work items before summarizing them in chat.
- Keep Verlyn work items current while implementation is in progress.
- Prefer archive/cancel over destructive deletion for durable workflow items.
- Generated analyzer artifacts are external evidence, not committed source of truth.
- Prefer installed public `verlyn` CLI commands over retyping workflow steps from memory.
- Treat a missing active Verlyn change or unauthorized repo binding as a workflow failure to fix before editing, not a suggestion to proceed from memory.
- Once a Verlyn change is active, use the installed public `verlyn` CLI path first for branch repair, PR delivery, merge, and workflow state changes. If the product path is missing or blocked, record the blocker as Verlyn workflow feedback instead of bypassing it.
- When a workflow mutation or delivery action exists in Verlyn, use the installed public CLI path before shell fallbacks such as `gh`.
- For hosted PR closeout, prefer the Verlyn hosted delivery path from a repo-visible owner session. If the current session cannot see the repo, treat that as a scope/access gap to fix or switch sessions for, not as permission to bypass Verlyn's hosted workflow or fall back to `gh`.
- Use `verlyn changes deliver <change-id>` for hosted source-control closeout when a change is ready to land; use `verlyn changes deploy <change-id>` when the same closeout should also deploy to the configured provider.
- Keep change, work-item, review, and handoff records current while work is in progress.
- Treat workflow friction as product feedback: if the process is confusing or blocked, record it as a change or work item instead of bypassing it.
- Use subagents only for narrow, bounded, low-coupling parallel work. Avoid delegating tightly coupled workflow logic, central orchestration, or state-heavy UI changes unless there is a strong reason the speedup outweighs reintegration cost.
- The lead agent remains responsible for critical-path integration and should not delegate the immediate blocker blindly.

## Completion Policy

Work is not complete until:
- acceptance criteria are checked off
- applicable verification passes
- work items and review records are updated when the change uses them
- remaining risks or pre-existing failures are recorded
- a session retro exists when this repository's project policy requires one
