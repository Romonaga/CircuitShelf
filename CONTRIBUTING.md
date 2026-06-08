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
- Humans working inside the target repo should follow `Documentation/guides/REPO_COLLABORATION_WORKFLOW.md`.
- Assistants should start with `Documentation/guides/VERLYN_ASSISTANT_STARTUP.md`, then use `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` for the working session loop.
- Do not use `--no-verify` or force-push without explicit instruction.
