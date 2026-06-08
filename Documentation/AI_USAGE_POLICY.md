# AI Usage Policy

This repository allows AI-assisted planning, implementation, review, and documentation work only when the workflow remains auditable and a human owner stays accountable for the result.

## Approved tools

- AI tools that defer to `AGENTS.md`
- Tool-specific wrappers that do not override repo policy

Any other AI tool requires explicit human-owner approval.

## Autonomy levels

### Level 1: Drafts and analysis

Allowed without step-by-step approval:
- documentation drafts
- review findings
- triage notes
- cleanup inventories

### Level 2: Implementation with human review

Default for most code work:
- features
- bug fixes
- refactors
- test creation

Requirements:
- named human owner
- normal verification runs
- AI disclosure in the PR

### Level 3: Human approval before merge

Required for:
- new dependencies
- security-sensitive code or config
- schema or contract changes
- destructive cleanup batches
- canonical instruction or spec changes

## Dependency-intake controls

- Do not install or merge a dependency solely because an AI suggested it.
- Verify the package identity and why an existing dependency cannot solve the need.
- Require human review before install or merge.

## Quality gates

- Run normal repo checks.
- Require manual security review for security-sensitive work.
- Record accepted risks or deferrals explicitly.

## Incident learning

If an AI-assisted change causes a regression:
- capture the incident in `Documentation/guides/AI_INCIDENT_TEMPLATE.md`
- attach it to the relevant change or handoff trail
- add at least one durable improvement: rule, test, check, or tooling change
