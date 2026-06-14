# Contributing to [REPO]

These rules apply to all contributors, human and AI.

## Commit Protocol

### Never commit without explicit approval

After completing work:
1. Show the summary of changes.
2. Ask whether the changes should be committed.
3. Wait for an explicit yes.
4. Only then commit.

Responses like "continue", "next", or "looks good" are not commit approval.

### Commit checkpoint

Before `git commit`, print a short checkpoint with the files being committed.

### One branch per concern

- `main` stays protected.
- Use one branch per change or logically distinct work item.
- Do not mix unrelated work on one branch.

## Pre-Commit Checklist

### For code changes
- Build passes
- Tests pass
- Any configured architecture or workflow guard passes

### Engineering standards
- Keep code organized by domain, feature, or clearly owned module; avoid dumping unrelated behavior into shared utility files.
- Follow the best practices, naming conventions, formatting, and idioms of the language and framework already used in the repository.
- Follow the recommended source-code folder structure for the programming language, framework, and package manager in use; do not invent flat or ad hoc layouts when the ecosystem has an accepted project structure.
- Prefer small, cohesive functions and components with clear inputs and outputs.
- Preserve existing public contracts unless the change explicitly updates the contract and documents the migration.
- Avoid broad refactors, dependency changes, generated-code churn, and formatting-only edits unless they are part of the approved scope.
- Keep secrets, credentials, tokens, local paths, and private environment details out of source, logs, tests, PR text, and generated artifacts.

### Testing expectations
- Add or update tests for critical paths, bug fixes, security-sensitive behavior, data migrations, public APIs, and user-facing workflows.
- Use focused tests for narrow changes and broader integration or end-to-end checks when behavior crosses module, service, or UI boundaries.
- If a meaningful test cannot be run, document the reason, the risk, and the manual verification that was performed.
- Do not claim code is ready only because it compiles; verify the behavior that changed.

### For documentation or workflow changes
- Markdown renders
- Links work
- Canonical policy is not restated incorrectly in a non-authoritative file

### Always
- A human explicitly approved the commit

## Pull Request Process

1. Push a branch.
2. Create a PR using the repository PR template.
3. Fill in all required sections, especially AI disclosure, independent review, rollback, and handoff.
4. Address feedback in new commits.

## AI-Assisted Work

- Record AI assistance in the PR body.
- Name an accountable human owner.
- Keep verification, review findings, and dispositions visible in the repo workflow files.
- AI agents should use Verlyn as the source of truth for repo binding, active changes, work items, reviews, delivery state, and evidence when that information is needed.
- AI agents must inspect the existing code structure before editing and should follow local patterns instead of inventing new architecture.
- AI agents should keep edits scoped to the active change, preserve user work, and avoid unrelated cleanup.
- AI agents should explain remaining risks, skipped checks, and assumptions before handoff.
- Humans working inside the target repo should follow `Documentation/guides/REPO_COLLABORATION_WORKFLOW.md`.
- Assistants should start with `Documentation/guides/VERLYN_AGENT_WORKFLOW.md`.
- Do not use `--no-verify` or force-push without explicit instruction.
