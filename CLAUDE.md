# CLAUDE.md

This file is a tool-specific wrapper.

- Follow `CONTRIBUTING.md` for commit and branch protocol.
- Follow `AGENTS.md` for repo-wide routing, verification, and completion policy.
- Read `.verlyn/runtime_context.json` when present for the compact assistant/runtime contract.
- Read `RULES.md` for editable project-level guidance before starting work.
- After session compaction, compressed-summary recovery, or any other context-compressed resume, reread the governed files and make the first user-facing response explicitly say: "Governance was reloaded and required repo rules were reread."
- Use `workspace mode` from Verlyn root only for control-plane work.
- Use `repo-local mode` via `Documentation/guides/REPO_COLLABORATION_WORKFLOW.md` for human work inside the target repo.
- Use `assistant mode` via `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` for assistant-driven sessions inside the target repo.
- Do not override repo policy from this file.
