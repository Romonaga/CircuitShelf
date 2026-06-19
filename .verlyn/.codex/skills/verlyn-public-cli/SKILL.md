---
name: verlyn-public-cli
description: Use when Codex is working in a Verlyn-governed repository or needs to inspect, plan, implement, validate, review, deliver, or deploy work through the installed public `verlyn` CLI. Triggers include Verlyn workflow startup, repo binding, edit-route checks, changes, work items, reviews, gates, hosted delivery, deployment, governance pack installs, and avoiding private Verlyn maintenance paths.
---

# Verlyn Public CLI

Read `.verlyn/agent-skills/verlyn-public-cli.md` before working with Verlyn-governed repo workflow. That file is the tool-neutral source for this adapter.

If `.verlyn/agent-skills/verlyn-public-cli.md` is missing, fall back to the repo governance files and installed public CLI docs:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md` when present
6. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` when present
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md` when present

Required Codex behavior:

- Use the installed public `verlyn` CLI first.
- Run `verlyn auth status`, `verlyn workflow assistant-startup --json`,
  `verlyn workflow assert-edit-route --json`, and `verlyn target show --json`
  before edits.
- Inspect active changes and work items through `verlyn changes show --json`
  and `verlyn work-items list`.
- Record changed-file review evidence before delivery when real files changed.
- Use `verlyn changes deliver <change-id>` for source-control closeout and
  `verlyn changes deploy <change-id>` for closeout plus provider deployment.

Optional overrides such as `--profile`, `--server`, `--repo-slug`, `--target`,
`--source-ref`, and `--commit-sha` are diagnostics, bootstrap, or recovery
controls. Do not use them as routine workflow requirements.

Do not use direct PostgreSQL access, private Verlyn helper scripts, provider
secret handling, raw provider tools, or gate bypasses as substitutes for the
public CLI workflow.
