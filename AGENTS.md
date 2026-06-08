# [REPO] - Agent Operating Rules

Auto-read by all agents. This is the authoritative source for routing, verification, and completion policy. Project-specific guidance in `RULES.md` and tool-specific files such as `CLAUDE.md` must defer to this file for policy. Use `.verlyn/runtime_context.json` as the compact runtime summary when you need the current repo contract in compressed form.

## Directive Hierarchy

| Priority | File | Role |
|---|---|---|
| 1 | `CONTRIBUTING.md` | Authoritative human workflow and commit protocol |
| 2 | `AGENTS.md` | Repo-wide routing, verification, and completion policy |
| 3 | `RULES.md` | Editable project-level guidance; it defers to `AGENTS.md` and `CONTRIBUTING.md` |
| 4 | `CLAUDE.md` | Tool-specific notes; they defer to higher-priority files |
| 5 | Workflow guides and verified command docs | Command reference only after repo-local commands are checked |

Rule: if a policy appears in both `AGENTS.md` and a tool-specific file, `AGENTS.md` wins.

## Operator Routing

Before starting a session, read the guide that matches how you are working:
- `workspace mode`: use Verlyn-root docs and commands from the central Verlyn install
- `repo-local mode`: `Documentation/guides/REPO_COLLABORATION_WORKFLOW.md`
- `assistant mode`: `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md`, then `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`

Always read `Documentation/AI_USAGE_POLICY.md` before using AI-assisted paths.

## Default Orders

1. Read `CONTRIBUTING.md` before touching commits or branches.
2. Read `RULES.md` before starting work so project-level guidance is in view.
3. Read `.verlyn/runtime_context.json` when it exists so the compact assistant/runtime contract is in view.
4. Run `python scripts/verlyn_workflow.py context --json` to inspect the active workflow state before editing.
5. Run `python scripts/verlyn_workflow.py assert-edit-route` before manual code edits; if it fails, set the route with `python scripts/verlyn_workflow.py use-change <change-id>` or record an explicit direct-work exception.
6. Decide whether the work needs an active Verlyn change record.
7. For feature or behavior-changing work, inspect the active change details through Verlyn before implementation.
8. Run the session-start baseline before editing.
9. Do not call work complete until its acceptance criteria are satisfied and recorded.
10. Do not commit without explicit human approval.

After session compaction, summary recovery, or any other context-compressed resume, reread `AGENTS.md`, `RULES.md`, `.verlyn/runtime_context.json`, `Documentation/AI_USAGE_POLICY.md`, and `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md` before continuing so the assistant relearns the current system contract instead of relying on stale summarized context. The first user-facing response after that reload must explicitly say that governance was reloaded and required repo rules were reread; do not leave this only in helper JSON, hidden receipt files, or internal tool output.

## Work Routing

| Trigger | Route |
|---|---|
| New feature, behavior change, API change | Create or use an active change record and inspect its current details through Verlyn before implementation |
| Bug fix, regression | Nearest change/spec plus targeted regression validation |
| Refactor | Direct if no contract change; use a change record if behavior or contracts move |
| Documentation or workflow files | Direct unless the policy itself changes |
| Architecture-significant change | Run architecture review before implementation |
| Canonical policy/spec change | Require independent review before merge |

## Operating Rules

- Record review findings and dispositions in Verlyn-managed workflow records before summarizing them in chat.
- For Review Tier 2+ work, keep DB-backed work items and `proposal.md` current.
- Prefer archive/cancel over destructive deletion for durable workflow items.
- Generated analyzer artifacts are external evidence, not committed source of truth.
- Prefer repo-local helper commands such as `python scripts/verlyn_workflow.py start-change ...` over retyping raw workflow commands from memory.
- Treat `python scripts/verlyn_workflow.py assert-edit-route` as the helper-side enforcement gate before manual code edits; a missing active change route or explicit direct-work route is a workflow failure to fix, not a suggestion to proceed from memory.
- When a workflow mutation or delivery action exists in Verlyn, use Verlyn's helper/API path before shell fallbacks such as `gh`.
- For hosted PR closeout, prefer the Verlyn hosted delivery path from a repo-visible owner session. If the current session cannot see the repo, treat that as a scope/access gap to fix or switch sessions for, not as permission to bypass Verlyn's hosted workflow or fall back to `gh`.
- When workflow, API, auth/session, startup order, or helper-command behavior changes, update `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md` in the same change.
- Use subagents only for narrow, bounded, low-coupling parallel work. Avoid delegating tightly coupled workflow logic, central orchestration, or state-heavy UI changes unless there is a strong reason the speedup outweighs reintegration cost.
- The lead agent remains responsible for critical-path integration and should not delegate the immediate blocker blindly.

## Completion Policy

Work is not complete until:
- acceptance criteria are checked off
- applicable verification passes
- task and review ledgers are updated
- remaining risks or pre-existing failures are recorded
- a session retro exists when the workflow learning loop is in use
