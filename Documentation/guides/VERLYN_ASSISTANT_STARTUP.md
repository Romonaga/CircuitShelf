# Verlyn Assistant Startup and API Guide

Use this guide when you are an assistant working inside the target repo.

This is the canonical assistant-facing startup and Verlyn API guide. `AGENTS.md` remains authoritative for policy, and `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` remains the day-to-day session loop once startup is complete. This guide is part of Verlyn's system-governance contract because it defines how assistants should use Verlyn itself, including the helper and API surfaces.

Terminology note: the product UI and helper commands now say `Workstream`, `Work item`, and `Evidence`. Some internal API route names still use `task` where that name remains part of the current implementation contract.

## Read In This Order

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md`
6. This guide
7. Active change details from the helper or API when work already exists
8. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` for the working session loop

## Canonical Runtime Context

Use `.verlyn/runtime_context.json` as the compact runtime contract when you need the current repo policy in a structured form that survives session compression.

After session compaction, compressed-summary recovery, or any other resume path, reread `AGENTS.md`, `RULES.md`, `.verlyn/runtime_context.json`, `Documentation/AI_USAGE_POLICY.md`, and this guide before continuing so the assistant reloads the current system contract instead of relying on stale summarized context. The first user-facing response after the reload must explicitly say that governance was reloaded and required repo rules were reread; helper JSON, receipt files, and web-only status panels are supporting evidence, not a substitute for the visible operator notice.

- `AGENTS.md` remains authoritative for repo-wide system governance and completion policy.
- `Documentation/AI_USAGE_POLICY.md` remains part of the governed contract for how AI-assisted work is allowed to use Verlyn.
- `RULES.md` remains the editable project-level guidance layer.
- `.verlyn/runtime_context.json` is the compact assistant/runtime summary.
- This guide remains the detailed startup, API, and helper reference for using Verlyn itself.
- `python scripts/verlyn_workflow.py assistant-startup --json` is the supported repo-local startup receipt. It reloads the governed contract and records a visible receipt in `.verlyn/assistant_governance_reload.json` so both the assistant and the operator can see that startup was reloaded.

## Session-Start Baseline

Run these before suggesting or editing anything:

```bash
python scripts/verlyn_workflow.py assistant-startup --json
python scripts/verlyn_workflow.py context --json
python scripts/verlyn_workflow.py assert-edit-route
python scripts/verlyn_workflow.py status
python scripts/verlyn_workflow.py inbox
```

`assistant-startup --json` returns the governed read order, the supported helper startup contract, and the current governance reload receipt. `context --json` now includes both an `editing_route` verdict and a `governance_reload` verdict. Treat `assert-edit-route` as the hard CLI gate before code edits continue:

After compaction, compressed-summary recovery, or any resume where the operator may wonder whether the rules were reloaded, relay the `governance_reload.operator_notice` from `assistant-startup --json` or `context --json` in the first user-facing CLI/chat update. This is the human-visible confirmation that Verlyn reread the governed files before work continued, not just a hidden receipt file, helper JSON payload, or a web-only status panel. If the assistant is operating in a terminal/chat session, the notice belongs in that same conversation before normal work updates continue.

- `active_change` means repo-local helper state is tied to a tracked change
- `direct_work_allowed` means an explicit direct-work exception was recorded
- `blocked_missing_change` means do not start editing yet
- `blocked_missing_work_branch` means the change exists, but its planned work branch is not available locally yet
- `blocked_missing_governance_reload` means the assistant has not reloaded the governed contract for this session yet
- `blocked_stale_governance_reload` means one of the governed files changed after the receipt was recorded, so startup must be rerun
- when the route is blocked by missing or drifted work-branch state, the helper now tries a safe self-heal first; if it stops because work could be lost or a manual conflict is required, the payload includes the reason plus `repair_options` instead of a raw git error only
- blocked self-heal payloads may also include `ai_repair_diagnosis`; that diagnosis is advisory only, never a bypass around the deterministic git safety gate, and it resolves AI credentials from the repo execution-profile override first, then the project execution-profile default, then the entity-backed shared AI profile when no narrower override exists

Use `status` and `inbox` when the context payload is not enough to see which change or work item should be picked up next.

Task execution preflight can now surface readiness mode through the shared work-brief metadata. Treat `readiness_fleshing_mode` and `readiness_fleshing_status` as the common contract for whether execution readiness came from an existing brief (`direct`), heuristic auto-focus (`heuristic`), AI-authored packet repair (`ai_fleshed`), or a blocked AI readiness attempt (`blocked`). The same metadata now also carries `readiness_fleshing_duration_ms` and `readiness_fleshing_candidate_count` so CLI and web surfaces can show how much work the readiness pass did before batch admission continued or stopped.
Task execution, task preflight, and batch readiness should resolve their AI provider from the runtime execution-profile path, not from generic analyzer config: repo override first, then project default, then the entity-backed shared AI profile. If no runtime profile is configured or the resolved provider is missing credentials, Verlyn should halt with a clear readiness failure instead of defaulting to a generic provider.
Task execution should also fail closed when a provider request exceeds the configured `task_execution.request_timeout_seconds` budget. The same timeout budget applies to AI readiness fleshing during batch startup, so a queued entry blocks with a clear readiness error instead of hanging invisibly before the queue is marked running. Canceled batch entries or queues should expose canceled automation state instead of stale `running` metadata.
When a change contains both the generic managed wrapper tasks Verlyn seeds at change creation and more specific substantive work items, batch planning should ignore those wrapper tasks and pick the substantive work first. When multiple substantive work items are runnable at the same time, batch should choose the earliest item in normalized linked/order sequence so execution is deterministic. Wrapper tasks should only run when they are the only open work left on the change. Batch planning payloads now also expose `selection_reason` and `selection_pool_kind` so callers can explain whether Verlyn picked a substantive task, fell back to a managed wrapper, or broke a tie through normalized task order.
Shared workflow preparation now also records `execution_engine_id`, `execution_engine_surface`, `execution_engine_duration_ms`, and step telemetry under `execution_engine_steps` on prepared task briefs, while change packets record `workflow.execution_engine` metadata when shared packet-default and spec-delta preparation runs.
AI providers now also have a manifest-backed plugin lane under `plugins/ai/**/provider_manifest.json`, hosted by `runtime/providers/ai.py`. Treat execution profiles as the live runtime selection surface, while the AI plugin host owns provider discovery, adapter behavior, model defaults, capability publishing, and encrypted provider-local secret/state helpers. For plugin-backed providers such as OpenAI, Verlyn resolves the selected execution profile first and then bridges the provider credential into encrypted plugin state before the adapter uses it.
Verlyn now also injects effective repo rule context into AI execution surfaces at the host layer rather than inside individual providers. Tool-loop agents flowing through `plugins/analysis/builtin/stages/ai_agent.py` and hosted one-shot generations flowing through `analyzer/llm.generate_text_sync(...)` both receive a compact rule bundle derived from `AGENTS.md`, `RULES.md`, and `.verlyn/runtime_context.json` when a repo root is known. Treat that as a Verlyn-owned prompt contract: providers and plugins stay app-agnostic, while Verlyn remains responsible for resolving and shaping repo governance and project guidance before provider execution begins.

## Out-of-Service Mode

Global settings can place the workspace into an explicit out-of-service mode for upgrades, backfills, or other maintenance windows.

- The durable state lives in workspace runtime settings as `service_mode`.
- `GET /api/auth/session` exposes the current maintenance state so UI and assistants can explain why writes are blocked.
- `GET /api/health` stays a minimal unauthenticated liveness lane and should not leak repository or run inventory detail.
- Normal write routes fail closed with `503` and `code = "service_mode_active"` while maintenance mode is enabled.
- Admin recovery lanes such as runtime-settings updates, user-profile updates, and workspace deployment-provider inspection stay available so an operator can finish maintenance and clear the mode.
- Repo-local helper commands also respect maintenance mode: normal workflow mutations are blocked, while explicit DB/runtime repair helpers stay available when documented for the current product lane.

## Control Path Priority

Use Verlyn in this order:

1. Repo-local helper commands in `scripts/verlyn_workflow.py`
2. Verlyn API routes when the helper does not expose the exact workflow mutation you need
3. Raw `verlyn --target "$PWD" ...` only when the helper does not wrap the capability yet
4. Direct record surgery only when the product path is blocked and the change is explicitly repairing that path

Rule of thumb: use helpers for common session flow, use the API for precise change or work-item mutations, and do not patch durable workflow records by hand unless Verlyn itself is what you are fixing.

Repo-local helper mutations now load mutable change state under the per-change record lock before they rewrite the DB-backed payload. That serialization is per change record, so nearby updates on the same change should be routed through the helper or API path instead of ad hoc manual edits.

CLI change and work-item mutations now route through the normalized workstream bridge instead of side-stepping into file-backed packet helpers. Treat the returned change id and work item id as authoritative:

- `changes create` and `workflow start-change` accept a label/title hint only; Verlyn allocates the durable project-scoped change id in the DB transaction that writes the change.
- New work items and updates use one batch contract. Submit `changes work-items-batch <change-id> --create '{"title":"..."}'` for creation and `changes work-items-batch <change-id> --update '{"task_id":"..."}'` for updates, even when only one work item is changing.
- `POST /api/changes/{repo_slug}/tasks/batch` is the canonical API mutation path for work-item creates and updates.
- After a mutation, prefer the returned payload or a follow-up `changes show --json` read over reconstructing ids from naming guesses.

Workflow lookup routes are also part of the write contract now, not only the read contract. `GET /api/workflow/{repo_slug}/lookups` returns:

- lookup options for `change_types`, `work_item_types`, and `effort_bands`
- `field_definitions` for workflow-controlled change and work-item metadata
- `field_requirements` describing which fields are required on create and update, plus any default strategy metadata

Treat those required-field rules as the shared source of truth for UI and helper expectations. The mutation layer enforces the same contract so missing workflow metadata does not depend on client-only validation.

Repo-local workflow packet helpers such as `prepare-pr`, `handoff-review`, and `workflow context` resolve bound runs and standard run artifacts from the relational runtime lane when Verlyn is running in PostgreSQL-backed mode. Do not treat those commands as temp-filesystem-only helpers.
`python cli.py --target <repo> workflow context --json` should resolve project bindings through the same loaded repo config path as the rest of the helper surface, so a checked-in local/public PostgreSQL DSN in `analyzer/config.yaml` should be enough for repo-local context reads.
The helper context path now prefers live relational summary reads, a lightweight relational run-context payload, and a lean hosting-status read, so routine `context --json` calls do not need to enumerate report manifests, branch lists, open PRs, or the entire historical change backlog just to establish operator context. By default, the workspace section keeps full summary counts but bounds the included change summaries; use `--workspace-limit 0` only when you intentionally need the full workspace change list in the context payload.
When a freshly installed repo-local helper can resolve the repo itself but the runtime repository binding has not been seeded yet, `workflow context --json` should still return a repo snapshot and an empty workspace fallback instead of failing closed.
Repo-local route reconciliation and targeted change lookup should also use that checked-in repo config when they read directly from the relational store. If a helper can see the repo but cannot resolve DB-backed change payloads until it shells out to another CLI process, treat that as a helper regression to fix rather than normal behavior.
Helper and CLI change reads should prefer live relational hydration over compatibility snapshots so repaired run bindings, status updates, and closeout repairs appear immediately instead of waiting for a snapshot refresh.
The same helper now returns `helper_metrics` timing in its JSON payload so slow context assembly can be traced by stage instead of guessed from wall-clock delay alone.

Those helper responses now also expose `helper_metrics` timing for:

- run-context resolution
- artifact loading
- packet generation
- persistence
- total helper duration

`python scripts/verlyn_workflow.py changes show <change-id> --json` is now the supported machine-readable helper path for reading a single change with structured helper telemetry. The default `changes show` output remains the raw change payload for compatibility, while `--json` wraps the change with `data_source` and `helper_metrics`.
`python scripts/verlyn_workflow.py changes list --json` is now the supported machine-readable helper path for listing tracked changes with summary payloads plus helper timing. Prefer that over scraping the human-readable list output when assistants need to inspect backlog state.
For relational-backed helper reads, treat the JSON-wrapped `change` payload as DB-safe workflow metadata rather than a packet/filesystem mirror: packet-style fields such as `paths`, durable `report_paths`, `active_run_root`, `change_record_metadata.change_directory`, `change_record_metadata.record_path`, and `analysis_binding.run_root` must not be treated as part of the helper contract.

Hosted merge and closeout still record the durable `delivery_duration_ms` telemetry on the change record.

For hosted GitHub delivery and closeout, prefer Verlyn's hosted delivery routes over shell fallback tools. If the current session cannot see the repo, switch to a repo-visible owner session or fix the scope gap instead of using `gh` as a shortcut. A 403 from a hosted-delivery route means the session scope is wrong, not that it is acceptable to bypass Verlyn.

## Auth And Repo Slug Discovery

When using the local web API directly:

1. Check whether the server requires login:
   `GET /api/auth/session`
2. If the session is unauthenticated, log in with operator-provided credentials:
   `POST /api/auth/login`
3. Discover the repo slug from `GET /api/repos` by matching the repo `target_path` to the current repo root

Do not confuse the authenticated session `user` with Verlyn execution or hosting profiles. The auth user is the person or service account operating Verlyn; execution and hosting profiles are reusable runtime and source-control settings.
The checked-in repo config now defaults to the PostgreSQL-backed runtime lane with authenticated web mode for dogfooding. Durable local-password accounts and user-profile state come from the normalized PostgreSQL auth/runtime tables only; the web lane no longer falls back to workspace-local auth account files. The repo does not ship live project-store DSNs or a live authenticated session secret anymore. Project-store connection selection now uses three fixed lanes only: `developer` resolves `DATABASE_PUBLIC_URL`, `tester` resolves `VERLYN_PROJECT_STORE_TESTER_DSN`, and deployed/internal runtime resolves `DATABASE_URL`. The repo config no longer carries per-lane env-key indirection; it only records that lane selection should be automatic. The preferred secret contract is an encrypted repo-carried bundle at `.verlyn/project.secrets.enc.json` plus an out-of-band key file at `.verlyn/project.secrets.key` for local developer use or `/run/secrets/verlyn_project_secrets.key` for deployed runtime. There is no interactive prompt path in deploy.
The bundled `db_password` auth backend is now hosted through the auth provider framework in `runtime/providers/auth.py` and discovered from `plugins/auth/local_password/`, but its durable account, profile, entity, and session state still come from Verlyn's normalized PostgreSQL tables rather than a provider-owned side store.
Plugin boundary rule: authentication providers are the only plugin family allowed to be Verlyn-aware and DB-aware. Deployment and notification providers must stay on the shared framework contract only; if Verlyn needs to prepare runtime materials, lane selection, or deployment metadata, the framework does that work before the provider runs. Execution engines are first-party runtime code, not third-party deployment or notification plugins.

Project-store DSN selection is also environment-aware by default:

- local development resolves the developer lane
- deployed container or Railway runtime resolves the deployed internal lane
- relational test runs resolve the dedicated tester lane
- the checked-in repo config should keep lane selection on `auto`; override only when debugging the resolver itself

For a fresh local checkout, get `.verlyn/project.secrets.key` through the team secret handoff or secret manager and keep it out of git. The encrypted `.verlyn/project.secrets.enc.json` bundle can stay in the repo.

The web server is now DB-only by contract. `verlyn-web`, `python cli.py web`, and bind-setting validation all fail closed unless:

- the runtime mode resolves to `relational_postgresql`
- the configured PostgreSQL runtime target is reachable at startup

Verlyn now expects the durable DB lane everywhere the product runs. Do not expect the web lane or helper-driven workflow mutations to fall back to file-backed or shadow-validation runtime paths.
The web launchers now boot through the explicit `server.app:create_app` factory path. Importing `server.app` should no longer eagerly construct the FastAPI app or load runtime settings until a launcher or caller explicitly asks for the application object.

For local developer dogfooding, `python cli.py web` may bind `0.0.0.0:8010` over plain HTTP while keeping DB-backed authentication enabled; developer/local runtime keeps `session_secure=false` so browsers can send the session cookie back over HTTP. For real LAN or deployed exposure, use the explicit exposure contract instead of ad hoc host changes: set `VERLYN_WEB_EXPOSURE=lan` for LAN exposure, or run in container/runtime deployment, and keep a valid session secret, reachable PostgreSQL auth/runtime data, and secure session cookies enabled. Container/runtime deployment defaults `session_secure=true`. If LAN/deployed exposure is forced to `session_secure=false`, Verlyn fails closed. This guard applies consistently to both `verlyn-web` and `python cli.py web`, so deployed launches cannot silently bypass the exposure rule.

The built-in `db_password` backend now treats PostgreSQL as the only durable source of truth. If a user profile exists without a valid password hash in `verlyn_auth_accounts`, Verlyn cannot reconstruct the old password automatically; the operator must reset that user's password through the DB-backed password recovery path instead of expecting legacy workspace JSON to restore access.

Session invalidation contract:

- Profile status is enforced both at login time and when Verlyn rehydrates an existing session from the signed cookie. Non-`active` profiles cannot establish or keep a session.
- Auth backends may expose a backend-scoped session revision. Verlyn stamps that revision into newly issued session cookies and compares it during later requests.
- The built-in `db_password` backend derives its session revision from the durable password hash in `verlyn_auth_accounts` and reloads that state on demand, so password-hash changes can invalidate older sessions without requiring a server restart.
- Legacy cookies that predate the session-revision field remain readable until they expire, so rollout does not force a blanket logout.

Authenticated web session activity now also records the last active Verlyn operator in workspace runtime settings for audit and assistant context, but repo-local helper change creation should not silently reuse that identity as the workflow owner.
Verlyn throttles repeated writes of the same authenticated operator during normal session and activity polling, so assistants should not treat every `GET /api/auth/session` or `POST /api/auth/session/activity` as a durable workflow mutation.

The resolved auth user now includes durable profile metadata such as `user_profile_id`, `profile_status`, `visibility`, and `entitlements` in addition to backend identity and capability data.

When you need to inspect or change durable people access as an admin, use:

- `GET /api/admin/user-profiles`
- `GET /api/admin/settings-catalog`
- `POST /api/admin/user-profiles/{profile_id}`

This is the user-profile lane. Do not route those edits through execution-profile or hosting-profile helpers.

Workflow helper commands and workflow-user validation now resolve registered-user state against the configured Verlyn workspace root even when the active repo target is passed into the helper. A repo target must not create stray repo-local workspace JSON artifacts as a side effect of owner, reviewer, or approver validation; registered-user checks stay on the relational runtime lane.

`GET /api/admin/settings-catalog` is the structured-help lane for the global settings surface. It returns the catalog that explains confusing admin fields and the entitlement feature metadata used by the UI picker. Prefer that route over hard-coding new admin help copy into the client.

Admin route access and workspace visibility are separate. When you need a scoped admin, keep the profile role as `admin` but set `visibility_bypass` to `false` on `POST /api/admin/user-profiles/{profile_id}` so project and repo visibility rules still apply.

`POST /api/admin/user-profiles/{profile_id}` now accepts `source_control_identities` alongside role, visibility, and entitlements. Use that field to link provider-neutral repo identities such as local-git or GitHub accounts to a user profile. Do not overload auth backend `identities` with source-control ownership data.
When repo-hosting identity discovery returns exactly one git identity for the selected repository, Verlyn preselects it in the user-access draft so the singleton does not require extra clicking. Multiple discovered identities still require an explicit choice.
When an admin edits the currently signed-in user profile, Verlyn refreshes the session immediately but lets the heavier workspace rehydration continue asynchronously so the save action does not stay blocked on provider inspection or catalog reload work.

Session timing is now part of the admin-controlled runtime settings contract:

- `auth_timing.session_ttl_seconds` controls the absolute cookie lifetime
- `auth_timing.idle_timeout_seconds` controls idle logout
- `auth_timing.warning_seconds` controls how early Verlyn warns before the idle deadline
- `POST /api/auth/session/activity` refreshes idle activity without extending the absolute TTL

Treat background polling as non-activity. The session warning and logout logic should stay honest even when the UI is busy refreshing data.
The web client now also treats session activity as deliberate operator interaction instead of every form mutation, and hidden tabs suspend timer-driven background polling so stale dashboards do not keep hammering the browser or server while out of view.

Example:

```python
import requests
from pathlib import Path

BASE = "http://127.0.0.1:8010"
repo_root = Path.cwd().resolve()
session = requests.Session()

# If auth is required, log in first with operator-provided credentials.
repos = session.get(f"{BASE}/api/repos", timeout=30).json()["repositories"]
repo_slug = next(
    item["repo_slug"]
    for item in repos
    if Path(item.get("target_path", "")).resolve() == repo_root
)
```

Do not hard-code credentials into repo docs, scripts, or change files.
Do not treat environment variables as the normal home for provider API keys. User-managed provider credentials belong in the selected execution profile, while web auth now expects durable DB-backed accounts instead of bootstrap credentials.

## Repo Run Launch Contract

Repository and change rerun launches now accept the request before heavy run preparation finishes.

- `POST /api/repos/{repo_slug}/runs` may return a tracked `job` with `current_stage = "prepare_run"` while `job.run_id` is still empty.
- Treat `/api/run-jobs/{job_id}` and `/api/run-jobs?repo_slug=...` as the first durable queued or starting visibility lane instead of assuming the initial response already has a live run id.
- Once preparation and execution handoff progress, the job and seeded run context expose `launch_metrics` with request acceptance, first visible state, preparation, and execution timestamps plus the derived request-to-visible, request-to-preparation, and request-to-execution latencies.

Run summaries in the relational lane now also carry a durable `run_purpose` contract:

- `operator` means the run came from the normal work/run path and is eligible to become the current work anchor
- `onboarding` means the run was created by repo onboarding or kickoff-style baseline seeding
- onboarding runs still count as real runs and still serve evidence and report history
- current-work selection prefers `operator` runs first and only falls back to `onboarding` when a repository has no operator run yet

## Preferred Helper Flows

Use the helper first for these common actions:

- Inspect workflow state:
  `python scripts/verlyn_workflow.py context --json`
- Assert that implementation is tied to a tracked route before code edits:
  `python scripts/verlyn_workflow.py assert-edit-route`
- Pin the repo-local helper to the active change when you are resuming existing work:
  `python scripts/verlyn_workflow.py use-change <change-id>`
- Record an explicit direct-work exception for allowed non-change work:
  `python scripts/verlyn_workflow.py direct-work --reason "policy/doc-only maintenance"`
- Clear the helper route when the session is intentionally being reset:
  `python scripts/verlyn_workflow.py clear-route`

## Finding Promotion API

The run-level finding workflow now has two layers:

1. deterministic proposal generation
2. AI-authored draft generation and apply

Deterministic proposal generation:

- `POST /api/task-proposals/{repo_slug}/{run_id}/generate`

AI-authored draft generation:

- `POST /api/task-proposals/{repo_slug}/{run_id}/draft`
  Payload:
  - `proposal_ids`
  - `destination`: `existing_change` or `new_change`
  - `change_id` when drafting onto an existing change

Draft apply:

- `POST /api/task-proposals/{repo_slug}/{run_id}/drafts/{draft_id}/apply`
  If `owner` is omitted, Verlyn assigns the signed-in workflow user as the change owner or work item owner by default.

Use this flow when a human wants Verlyn to translate findings into a fully fleshed change packet or work items instead of only creating a thin promoted task.
- Start a change:
  `python scripts/verlyn_workflow.py start-change <label-or-title-hint> --title "..."`
  Add `--owner "<name>"` only when deliberately assigning the change to another authorized workflow user.
- Pick up work:
  `python scripts/verlyn_workflow.py pickup-work-item <change-id> <work-item-id> --owner "<name>"`
- Update a change or work item without creating a work brief:
  `python scripts/verlyn_workflow.py change <change-id> --status active`
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"...","owner":"<name>"}'` to create DB-allocated work items
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"...","owner":"<name>"}'` to update existing work items
  Task helper output now includes phase timing (`total`, `build`, `persist`) so slow DB-backed work-item mutations can be diagnosed from the helper path directly.
- Create or update a change directly through the normalized change-management lane:
  `python scripts/verlyn_workflow.py changes create <label-or-title-hint> --title "..."`
  Add `--owner "<name>"` only when deliberately assigning the change to another authorized workflow user.
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"...","owner":"<name>"}'` to create DB-allocated work items
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"...","owner":"<name>"}'` to update existing work items
- Record prerequisite change order for delivery planning:
  `python scripts/verlyn_workflow.py change <change-id> --depends-on-changes "<prerequisite-change-id>"`
  Verlyn validates missing ids and change cycles here so delivery sequencing does not drift into prose-only assumptions.
- Preview or manage autonomous batch execution:
  `python scripts/verlyn_workflow.py batch-plan <change-id> [<change-id> ...]`
  `python scripts/verlyn_workflow.py batch-enqueue <change-id> [<change-id> ...]`
  `python scripts/verlyn_workflow.py batch-status --queue-id <queue-id>`
  `python scripts/verlyn_workflow.py batch-inspect --queue-id <queue-id>`
  `python scripts/verlyn_workflow.py batch-start-next <queue-id> --execution-mode run_change --continue-queue`
  `python scripts/verlyn_workflow.py batch-cancel-entry <entry-id> --reason "..."` 
  `python scripts/verlyn_workflow.py batch-cancel-queue <queue-id> --reason "..."` 
  `python scripts/verlyn_workflow.py batch-retry-entry <entry-id>`
  `python scripts/verlyn_workflow.py batch-purge-entry <entry-id>`
  `python scripts/verlyn_workflow.py batch-purge-queue <queue-id>`
  `delivery_mode=auto` is the current full-delivery lane: after autonomous execution it continues through commit, push, pull-request creation, and merge.
  Purge semantics are intentionally strict. `batch-purge-entry` and `batch-purge-queue` only delete never-started durable queue records that can be removed without rollback. If an entry has started, failed, blocked, completed, or otherwise may have produced side effects, purge must fail instead of pretending cancel or delete rolled that work back.
  Batch execution persistence is append/update-first, not whole-state replacement. Normal saves must not delete omitted historical queue or entry rows; active reads should use the DB-scoped live queue path, and durable history should be inspected through bounded history lanes or a specific queue id. Do not reintroduce file-style "missing from payload means stale" cleanup for batch history.
- Inspect the deployment-provider framework before hard-wiring vendor logic:
  `GET /api/repos/{repo_slug}/delivery/providers`
  Query /api/repos/{repo_slug}/delivery/providers before adding or changing vendor-specific delivery code. It exposes the manifest-backed provider contract, registered adapters, provider-owned shell panel metadata, and safe fallback behavior for providers that are not implemented in the current build.
  Canonical bundled deployment plugins now live at `plugins/deployment/<plugin-id>/`, with `provider_manifest.json` plus provider-owned code in `provider.py`.
  Deployment uses Verlyn's shared provider plugin core in [`runtime/providers/plugin_core.py`](/FastDrive/Verlyn/runtime/providers/plugin_core.py), but keeps its own deployment-only adapter contract in [`runtime/providers/deployment.py`](/FastDrive/Verlyn/runtime/providers/deployment.py).
  Deployment manifests now declare `plugin_type = "deployment"` and use schema version `2` so future auth, AI, and notification frameworks can reuse the same discovery core without collapsing into one universal adapter layer.
  For plugin structure and implementation guidance, read `Documentation/guides/DEPLOYMENT_PROVIDER_PLUGIN_FRAMEWORK.md`.
  Use `POST /api/deployment/providers/{provider_id}/inspect` and `POST /api/deployment/providers/{provider_id}/actions/{capability_id}` for workspace-level provider inspection and control-plane actions that should not depend on a selected repo.
  Use `POST /api/repos/{repo_slug}/delivery/providers/{provider_id}/actions/{capability_id}` for provider actions once the repo-scoped adapter is configured.
  Railway is the first concrete provider slice and the reference manifest-backed provider. It now supports workspace-level account validation and project creation plus repo-level deploy, redeploy, deployment status, deployment logs, service inspection/creation, database provisioning, environment inspection/creation, variable management, public URL/domain actions, and project-scoped storage actions through the shared provider contract.
  Workspace deployment settings now own Railway connection profiles only: token kind, auth scope, and connection secrets. Project and repo records own the provider target bindings layered on top of that connection.
  Prefer a Railway project token for the simplest path; account/workspace tokens are control-plane connections for project creation and broad project browsing, and they require explicit `project_id` and `environment_id` target binding at the project layer before repo delivery actions can run.
  Railway CLI create actions such as `railway add` still expect local link context instead of a `--project` flag, so Verlyn now synthesizes that link state in a temporary directory for service and database provisioning instead of mutating the repo checkout.
  Railway provider inspection is capability-transport-aware. Do not treat a missing Railway CLI as a total Railway outage: `database_manage` and backup-oriented `volumes` operations can still expose GraphQL-backed behavior when token and target fields are present, while CLI-only actions report their own unavailable status.
  Railway database provisioning is now GraphQL-authoritative after create or inspect. Treat the CLI step as bootstrap only: the durable `database`, `databases`, `connection_variables`, and `connection_facts` payloads should come from Railway GraphQL reconciliation, not from CLI stdout or fallback file reads.
  Railway database payloads may now carry both `requested_service_name` and `name_reconciled` so assistants can explain provider rename drift without guessing whether Railway kept the requested logical name.
  PostgreSQL-backed Railway database payloads may also carry `bootstrap_contract` guidance. Use that contract when bootstrapping Verlyn or another application DB: connect to the maintenance database first, create the target application database there, then reconnect to the target database before creating schemas or tables.
  For control-plane project creation, Verlyn now drives Railway CLI with explicit `--name` and, for account tokens, an explicit workspace id or name so Railway does not fall back to interactive workspace prompts and silently create the wrong project name.
  Repo and provider delivery payloads now expose `deployment_context.effective_config_sources` so assistants can see whether each resolved Railway field came from the workspace connection, the project default binding, the repo override, or a legacy workspace binding default that still needs migration.
  Railway provider inspection payloads may now also carry `provider_owned_status`, which is a Railway-owned attached-context summary built from the resolved deployment context. Use that provider-owned block for Railway-specific readiness and binding posture instead of adding Railway conditionals to the shared deployment shell.
- Inspect the notification-provider framework before hard-wiring SMS or email logic:
  `GET /api/notification/providers`
  Query /api/notification/providers before adding provider-specific alert logic. It exposes the manifest-backed notification contract, registered adapters, and the active workspace notification profile lane.
  Canonical notification plugins live at `plugins/notification/<plugin-id>/`, with `provider_manifest.json` plus provider-owned code in `provider.py`.
  Notification uses the shared provider plugin core in [`runtime/providers/plugin_core.py`](/FastDrive/Verlyn/runtime/providers/plugin_core.py), but keeps its own event, dispatch, and metrics contract in [`runtime/providers/notification.py`](/FastDrive/Verlyn/runtime/providers/notification.py).
  Workspace runtime settings now include `notification_profiles`, `active_notification_profile_id`, `notification_subscriptions`, and `notification_event_catalog`, so provider credentials, reusable event policy, and UI event metadata stay separate from deployment or hosting settings.
  Repo run routes now also accept an optional `notification_requests` payload. Today that lane supports `report_ready: true` so repo and change reruns can opt into a report-ready alert without bypassing the shared notification policy layer.
  For plugin structure and implementation guidance, read `Documentation/guides/NOTIFICATION_PROVIDER_PLUGIN_FRAMEWORK.md`.
- Create or refine repo-native changes and tasks without leaving repo-local mode:
  `python scripts/verlyn_workflow.py changes create <label-or-title-hint> --title "..."`
  `python scripts/verlyn_workflow.py changes update <change-id> --status active`
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --create '{"title":"...","owner":"<name>"}'` to create DB-allocated work items
  `python scripts/verlyn_workflow.py changes work-items-batch <change-id> --update '{"task_id":"<existing-work-item-id>","title":"...","owner":"<name>"}'` to update existing work items
  `python scripts/verlyn_workflow.py changes move-work-item <source-change-id> <work-item-id> --to-change <destination-change-id>`
  `changes create` now accepts `--owner` as the repo-local alias for `--workflow-owner`, can seed the description, acceptance checklist, and managed brief or proposal sections in one create call, and should clean up partial change directories instead of leaving stale packets behind.
  When `changes create` books a follow-up packet whose branch is still only planned, the helper keeps the current active change route in place instead of hijacking the session to the new change. `use-change` may select a draft change as planning context, but it must not create, check out, or bind a work branch; activate the change before source edits.
- Prepare review or PR artifacts:
  `python scripts/verlyn_workflow.py handoff-review <change-id>`
  `python scripts/verlyn_workflow.py prepare-pr <change-id>`
  In human-readable mode, `handoff-review` and `prepare-pr` stream `[workflow:<phase>]` progress lines for context loading, run resolution, artifact loading, packet generation, and persistence. Keep `--json` output machine-clean; use the final `helper_metrics` payload for structured timing.
- Run one tracked change through hosted delivery without raw git or gh fallback:
  `python scripts/verlyn_workflow.py deliver-change <change-id>`
  `deliver-change` is the repo-local hosted delivery lane for a single tracked change. It reuses Verlyn's hosted delivery engine to prepare packet artifacts, commit tracked change files when needed, push the work branch, open or update the pull request, and merge it. In human-readable mode it now streams the current delivery step as it progresses so long-running hosted delivery does not look stalled. Use `--merge-method squash|merge|rebase` plus `--keep-local-branch` or `--keep-remote-branch` when the default cleanup posture is not what you want.
  `python scripts/verlyn_workflow.py publish-pr <change-id> --dry-run`
  `python scripts/verlyn_workflow.py publish-pr <change-id> --apply --reason "<reason>"`
  `publish-pr` is the governed PR-only lane for a tracked change that is ready for human review but must not be merged yet. Dry-run mode validates the operator, owner, route, branch, and planned scope without mutating workflow or repository state. Apply mode prepares and verifies the PR package, commits tracked change and packet paths, pushes the work branch, opens or updates the pull request, records a PR-only publish decision, and stops before merge. Use it instead of `deliver-change` when the explicit task is "open a PR, do not merge"; use `deliver-change` only for governed hosted delivery where merge is allowed.
  If hosted delivery hits a non-fast-forward push because an existing PR branch is stale, do not manual force-push. Use `python scripts/verlyn_workflow.py reconcile-pr-branch <change-id> --pr-number <number> --branch <branch> --old-remote-head <observed-sha> --new-local-head <refreshed-sha> --reason "<reason>" --dry-run` first. Only rerun with `--apply` after the dry run proves the PR branch, base branch, owner, route, clean worktree, workflow gate, observed remote head, and refreshed local head all match. The apply path uses Verlyn's governed lease-protected transport update so GitHub receives the refreshed local commit object before the PR branch ref moves, then records a change decision audit with the old head, new head, operator, PR number, timestamp, reason, result, and update method.
  Repo-local assistant edit-route writes are relational and retry bounded PostgreSQL deadlock or serialization failures before failing closed. If a helper reports `edit_route_persistence_failed`, treat the underlying Verlyn mutation as possibly completed but the local edit route as unsafe; rerun the helper or explicitly `use-change` after checking the database lock/connectivity state.
  If PR-only publish is blocked because the work branch checkout is too old to start the Web/API runtime and the runtime DB schema is newer than the checkout supports, do not park work with manual git. Use `python scripts/verlyn_workflow.py refresh-change-branch <change-id> --expected-dirty-path <path> --reason "<reason>" --dry-run` first. Only rerun with `--apply` after the dry run verifies the explicit operator, owner, route, target branch, expected dirty-file scope, developer/tester runtime schemas, and checkout schema support. Apply mode writes an out-of-repo dirty-work preservation bundle with hashes and restore notes, syncs the base branch, refreshes the change branch, restores only the allowed dirty paths, verifies the refreshed checkout supports the runtime schema, and records a change decision audit.
  Local CLI hosted delivery pins the project-store runtime lane to `developer` so it uses `DATABASE_PUBLIC_URL` even when unrelated deployment variables such as `RAILWAY_PROJECT_ID` exist in the shell. Explicit `VERLYN_PROJECT_STORE_CONNECTION_LANE`, lane-specific config, or an explicit deployed/test `VERLYN_RUNTIME_CONTEXT` still wins when that override is intentional.
  Prefer this path when you are landing one approved tracked change from the current work branch. The batch queue is a separate repo-level orchestration surface; do not reach for `batch-plan`, `batch-enqueue`, or `batch-start-next` when the job is simply "finish this one change." Use the batch lane only when you are intentionally queueing multiple changes or explicitly dogfooding the queue/automation behavior itself.
  `prepare-pr` now reconciles the default implementation and validation starter tasks for the active change before it builds the packet, so seeded workflow defaults do not linger in `todo` after the implementation work is already complete. Hosted delivery also treats the managed closeout tasks (`Review findings`, `Finalize handoff`) as post-merge closeout work rather than pre-merge blockers.
  In the relational lane, `prepare-pr` builds the closeout package in memory and applies workflow summary, PR comment, review handoff, and readiness documents through the `verlyn_apply_workflow_closeout_bundle` database function. Do not add new durable packet-file writes for this path; packet-shaped paths are compatibility labels only, and the durable documents live in the relational document tables.
  These closeout document writes are now retry-safe: if the generated review handoff or PR readiness payload only differs by a regenerated timestamp, Verlyn reuses the existing durable document rows instead of manufacturing fresh repo dirt.
  On clean committed work branches, packet generation now also reuses a stored current-review input cache keyed to the current git and run snapshot, so repeated `prepare-pr`, workflow-context, and delivery packet builds do not recompute impact, change-review, and CI-summary payloads unnecessarily.
  Repo-local helper `--json` mode is capture-first now: helper-generated failures emit structured JSON, and `deliver-change --json` no longer streams human progress text into the machine-readable payload.
- Drive repo-level batch execution from the terminal without bouncing through the API:
  `python scripts/verlyn_workflow.py batch-plan <change-id> <change-id> ...`
  `python scripts/verlyn_workflow.py batch-enqueue <change-id> <change-id> ...`
  `python scripts/verlyn_workflow.py batch-status --queue-id <queue-id>`
  `python scripts/verlyn_workflow.py batch-inspect --queue-id <queue-id>`
  `python scripts/verlyn_workflow.py batch-start-next <queue-id>`
  `python scripts/verlyn_workflow.py batch-start-next <queue-id> --execution-mode run_change --delivery-mode auto`
  `python scripts/verlyn_workflow.py batch-retry-entry <entry-id>`
  `python scripts/verlyn_workflow.py batch-cancel-entry <entry-id> --reason "..."`
  `python scripts/verlyn_workflow.py batch-cancel-queue <queue-id> --reason "..."`
  `python scripts/verlyn_workflow.py batch-purge-entry <entry-id>`
  `python scripts/verlyn_workflow.py batch-purge-queue <queue-id>`
  These repo-level batch helpers intentionally stay outside the change-route guard because they orchestrate durable queues across changes rather than editing one change packet in place. Read-only batch helpers stay available for inspection, while enqueue, start, retry, and cancel still count as normal workflow mutations for service-mode blocking.
  Batch enqueue and start use the shared readiness contract: Verlyn checks the next runnable task before it admits or starts work, auto-seeds missing brief focus from safe likely edit targets when confidence is high enough, and otherwise blocks the queue with the concrete readiness reason instead of letting a thin task fail later in automation. `batch-plan` and `POST /batch-execution/plan` are read-only deterministic previews: they must not persist work briefs, invoke provider checks, invoke AI readiness fleshing, or hydrate the full workspace just to evaluate visible changes. Heavier AI readiness, work-brief persistence, and hosted delivery belong to queue admission/start paths, not passive Workstream page loads.
  Treat batch control as a dedicated orchestration-checkout activity backed by the relational queue store. For multi-change orchestration, `batch-enqueue` and `batch-start-next` require a clean controller checkout. A single-change self-publish is allowed to start from a dirty checkout only when the live branch is exactly that change's bound work branch; wrong-branch dirt, unrelated dirt, and multi-change dirty orchestration still fail fast. Execution-engine queue state and heartbeats must stay DB-backed, not repo-local files.
  Recovery behavior is shared with the repo API and UI: queued entries persist across restart, while an entry left `running` when Verlyn stopped is reconciled to `failed` on the next batch inspection or mutation so operators do not inherit a stale active queue.
  Active batch status reads are scoped in the relational store to live queue rows. Durable terminal queue history remains auditable, but general history inspection is bounded and explicit; a specific `queue_id` lookup may retrieve that queue directly.
  The immediate `batch-start-next` response now preserves the just-started running entry inside the returned inspection snapshot so callers can trust that one response before any later restart-recovery reconciliation happens.
  `batch-start-next` now supports both queue-start-only and autonomous change execution from repo-local mode. Use `--execution-mode run_change --delivery-mode auto` when the terminal path should carry the queued change through AI work plus commit, push, pull-request creation, and merge instead of requiring a human to continue in the web UI.
  `batch-purge-entry` and `batch-purge-queue` are delete lanes, not rollback lanes. Use them only for never-started queue records that should disappear entirely. If an entry has already started, purge must fail and the operator needs a real cancel, retry, or recovery path instead.
- Record richer repo-local closeout detail when you are closing a change outside the dedicated merge routes:
  `python scripts/verlyn_workflow.py close-change <change-id> --status merged --summary "..." --review-scope-summary "..." --review-focus-reports "report-a,report-b" --reviewer-follow-up "next step A,next step B" --add-evidence "pytest=reports/pytest.txt"`
  `close-change` can now persist handoff status, independent-review notes, findings disposition, closeout review scope, reviewer follow-up, linked evidence, and optional hosted delivery metadata such as `--pull-request-number`, `--pull-request-url`, `--merge-method`, and `--delivery-mode` alongside the decision record so repo-local closeout does not collapse into status plus one summary line. It also completes the managed closeout tasks, reports which workflow packet files were mutated, and tells you when a follow-up commit is still required.
  Because `close-change` is a terminal closeout operation, the repo-local helper does not require the active edit route to match the target change's work branch before recording that closeout. Use it to normalize stale settled changes without rebinding the session away from current work.
  Retry behavior is now idempotent for the stable closeout decision id and linked evidence merge, so rerunning the same closeout should not append duplicate decision rows or duplicate evidence entries. The change-root `workflow/review_handoff.*` and `workflow/pr_readiness.*` files also count as managed closeout artifacts for hosted and local closeout cleanup.

Use `changes move-work-item` when a work item was recorded under the wrong change and needs to be rehomed without changing the work-item payload.

`start-change` now treats the freshly created change packet as the source of truth for its first seeded work item. On project-bound repos that use compact project work-item ids, that prevents helper-created duplicate ids and makes `--work-item-title` update the first seeded work item instead of appending a stray extra one.

`changes create` books branchless workflow intent. `start-change` with a new label/title hint also books a draft, branchless change; `changes activate` and `start-change <existing-change-id>` are implementation pickup paths and auto-create or check out the assigned work branch when the repo can do so safely, defaulting to the repository default branch unless an explicit validated base is provided. Creation must preserve draft lifecycle state and avoid checkout or active-route side effects until the operator explicitly starts work.
Draft change and work-item metadata updates are planning work, not source-edit work. `change` / `changes update` may repair draft ownership or planning fields without requiring a branch when the draft branch is still only planned, and `changes work-items-batch` may update existing draft work-item planning fields the same way. Direct `changes update --status active` is rejected; use `changes activate` or `start-change` so branch attachment and active status are recorded atomically. Moving a work item into execution statuses such as `in_progress`, `ready_for_review`, or `done` still requires the normal edit-route and branch guard.
If `start-change` is retried for an existing active change, the helper should reuse the existing packet instead of failing on the duplicate id. When the assigned branch already exists it should switch back to that branch first; when the branch is still only planned it should continue through the normal branch-creation path so queued work can be resumed without manual git setup.
If `start-change` fails before the packet is created, the helper should surface the real creation error directly instead of collapsing into a misleading `Change record not found` follow-on failure.
Repo-local helper installs now record the active editing route in the relational `verlyn_assistant_edit_routes` table scoped by workspace, repository root, and explicit assistant operator. `.verlyn/assistant_route.json` is legacy fallback/migration input only and is not authoritative when the DB route table is reachable. `start-change` and change-scoped helper commands refresh the DB-backed route automatically, while `use-change`, `direct-work`, `clear-route`, and `assert-edit-route` let assistants and operators make the route explicit after session recovery or compaction.
`use-change` may select a draft change as planning context, but it must not create, check out, or bind a work branch. `assert-edit-route` treats draft routes as planning-only and blocks source edits until `changes activate <change-id>` or the web Start work action attaches the governed work branch.
The DB-backed route also records the branch that was current when the route was refreshed. When a change-scoped helper targets that same change on that same branch for the same operator, the repo-local wrapper can use the recorded route instead of rehydrating the full change just to prove the obvious path; if the branch drifts, the normal DB-backed validation still runs.
For DB-backed change creation, treat the repository's `current_work_run_id` as the authoritative binding target. The API create-change route should not attach new work to a stale client-selected superseded run just because the caller still had an older run card selected; it now prefers `current_work_run_id`, then the latest successful run, and only falls back to an explicit requested run when no authoritative current-work binding exists.
Run carry-forward reconciliation should inspect the live relational change workspace when it decides which unfinished changes need to move into the newly completed run. Do not rely on a cached summary snapshot for carry-forward candidate selection, because that can miss drifted open work and leave superseded runs showing active changes.
`assert-edit-route` now auto-reconciles the session route when the current branch is uniquely bound to one editable change and the recorded route is missing or stale from a closed/deferred change. Ambiguous drift still fails closed with branch-aware guidance, and assistants should still treat any blocking `assert-edit-route` result as a workflow failure to fix before manual code edits continue.

Change lifecycle wording matters:

- `ready_for_review` means implementation is ready for review and closeout preparation
- `approved` means approved for delivery, not fully closed
- only `merged` or `archived` count as closed change states
Workflow-owned local git commit, merge, push, and closeout paths should now auto-heal a stale `.git/index.lock` once when Verlyn can prove no live `git` process is still active in the same repo. If Verlyn still sees a live git process, it must fail closed with that reason instead of deleting the lock blindly.

Use `pickup-work-item` when you want the durable work brief and active-work transition, use `work-item` when you only need to create or update work-item metadata, and use `change` when you only need to update change-level fields.
`start-change` and `change` now both support richer change-detail fields such as problem framing, success criteria, proposal summary, proposal scope, and acceptance replacement through helper flags such as `--brief-problem`, `--brief-success-criteria`, `--proposal-summary`, `--proposal-scope`, and repeated `--acceptance`. `work-item` now covers richer work-item fields such as acceptance, suggested tests, work log, blocked reason, evidence, and source proposal linkage. Use those helper paths before patching durable records directly.
Use `--depends-on-changes` on `start-change`, `change`, and `changes create/update` when one change must wait for another. Treat real prerequisite relationships as required booking or update metadata, not optional prose, for Verlyn and any product built with this system. Verlyn validates the prerequisite ids and blocks cycles so future automation can trust the dependency graph for work ordering.
Once a change has unresolved prerequisite links, implementation-start helper paths such as `pickup-work-item`, work-brief generation, AI execution, and PR-handoff preparation must fail closed until the prerequisite changes are complete. Keep read-only planning, metadata edits, and dependency authoring available while the change is blocked.

For repo-local work-item helpers, omitted list-style flags preserve existing work-item metadata. Only pass flags such as `--acceptance`, `--suggested-tests`, `--work-log`, `--depends-on`, or `--evidence` when you intend to replace that field on the work item.

If the helper still does not expose the exact mutation you need, fall back to the API instead of editing durable records directly.

## Core Verlyn API Routes

Prefer the repo-native `/api/changes/...` routes for assistant work. Treat `/api/workflow/...` routes as compatibility or UI-oriented helpers unless they expose behavior the repo-native routes do not.

API implementation layout:

- `server/app.py` is now the FastAPI bootstrap, middleware, dependency wiring, and route-registration entry point.
- Route handlers live under `server/api/` by surface area: `auth_routes.py`, `runtime_routes.py`, `hosting_routes.py`, `project_routes.py`, `repo_routes.py`, `change_routes.py`, and `run_routes.py`.
- Shared route wiring state is passed through `server/api/context.py`. When adding or moving API behavior, extend the route module that owns the surface instead of rebuilding large inline route blocks in `server/app.py`.

Core routes:

- `GET /api/repos`
  Discover repo slugs and repository metadata.
- `GET /api/repos/{repo_slug}`
  Fetch the repository detail payload. Use `payload_profile=startup` for the lighter startup contract; use the default/full profile only when you actually need the broader repo detail bundle. Startup repo detail now keeps change lists card-light and run history pill-light: change summaries expose `task_rollup` instead of eager `tasks`, and `latest_run` plus `run_history.recent_runs` omit report-path and approval-detail ballast until a run is opened directly. Repo detail keeps `latest_run` anchored to the newest attempt, but repo-level `report_paths` may bind to `evidence_run_id` with `evidence_run_source = "current_work_run"` when the latest attempt aborted or produced no durable reports. When a `run_id` is explicitly selected, `evidence_run_source` should report `selected_run` and the repo payload should stay bound to that requested run even if it has no generated docs.
- `GET /api/projects`
  Inspect project state and project-level defaults.
- `POST /api/projects`
  Create a project. Project payloads may include `repository_storage_location`, normalized to stay inside the configured Verlyn workspace root; `work_directory` remains a compatibility alias.
  Project workflow policy now derives from `workflow_mode`, and project deployment binding is a compatibility view over typed fields such as `deployment_profile_id` and `deployment_provider`.
- `POST /api/projects/{project_id}`
  Update project settings, including `repository_storage_location` when the project clone root needs to move. Responses report both `repository_storage_location` and `resolved_repository_storage_location` truthfully, plus the legacy `work_directory` fields.
  This route rejects non-empty `workflow_policy` payloads and non-empty `deployment_binding.config` payloads. Use `workflow_mode`, `deployment_profile_id`, and `deployment_provider` instead of trying to persist policy or target blobs on the project record.
- `GET /api/projects/{project_id}/hosting/repositories`
  Discover hosted repository candidates from the resolved project hosting context. GitHub is implemented first; unsupported providers return an honest unsupported status.
- `POST /api/projects/{project_id}/clone/preview`
  Validate the project clone root and destination folder and preview the clone result before any git operation runs.
- `POST /api/projects/{project_id}/clone`
  Clone the selected hosted repository into the project work directory and optionally hand it straight into the existing add-repo onboarding job.
- `POST /api/kickoff/plan`
  Preview the zero-to-app kickoff plan from a plain-language idea. Use this to infer the project, repo name, scaffold template, destination path, starter tasks, workflow mode, and a compact mechanics blueprint before anything is created on disk.
  When the idea mixes browser/gameplay intent with optional backend notes, the inferred template should stay aligned to the primary product shape and the template confirmation reason should explain that tradeoff instead of silently defaulting to a service scaffold.
  When kickoff preview returns blueprint questions, treat them as answerable workflow inputs rather than passive notes: feed `question_answers` back into preview so Verlyn can refresh the brief, confirmations, and starter task wording without forcing the operator to rewrite the original idea.
  Preview now also returns structured timing for the preview phases so dogfooding can see whether kickoff latency comes from normalization, blueprint generation, or starter-task shaping.
- `POST /api/kickoff/execute`
  Execute the approved zero-to-app kickoff plan. This creates or reuses the project, scaffolds the local repo, installs governance plus changes, seeds the starter change/tasks, prepares the first task brief, and returns the first task workbench payload. The generated brief should carry the blueprint context into the starter task notes so the first implementation slice is not abstract, kickoff-created projects must honor the selected workflow mode instead of forcing `team`, and the starter change should already have its work branch created and checked out before the kickoff flow is considered ready.
  Seeded starter tasks should reflect the primary user experience from the kickoff spec rather than generic happy-path labels whenever the blueprint captures concrete mechanics, and later kickoff tasks should explicitly show that they depend on the prior kickoff slice instead of reading like unrelated placeholders.
  Execute also returns phase timing so operators can see where kickoff spent time across scaffold creation, workflow install, seeded-run creation, work-brief preparation, and branch setup. Treat this flow as baseline-and-first-slice setup, not as proof that Verlyn has already built the entire requested app.
  The user-facing discovery path for starting new work should be a top-level `Start new` workspace tab or view. Keep the sidebar `Projects and repositories` surface available for project maintenance, editing, and repo onboarding, but do not make it the only obvious place where new work can begin or let it rehost the same full creation flow.
- `GET /api/repos/{repo_slug}/test-reporting`
  Load the repo-visible test and coverage summary for the selected repository. Treat it as three separate signals: deterministic analyzer inventory, current pytest collection status, and measured coverage artifact status. If the repo has not produced a readable coverage report, say that coverage is unavailable instead of inferring a percentage from heuristics.
- `POST /api/changes/{repo_slug}`
  Create a repo-native change record and bind it to the requested `run_id` or the repository's latest successful work run. Failed latest attempts stay visible as evidence, but they should not become the default anchor for new changes. The route now rejects creation when no applicable successful run exists. Web and CLI create flows default the workflow owner from the signed-in DB-backed user; explicit owner overrides remain available for deliberate assignment and must match an active registered Verlyn user profile that can see the selected repository or project. Requested reviewers, requested approvers, and seeded work-item owners follow the same registered-and-visible assignment rule.
- `POST /api/changes/{repo_slug}/{change_id}`
  Update change state, brief fields, reviewers, acceptance, and workflow metadata. Use `acceptance_criteria` to replace the checklist on update; acceptance entries may be plain strings or structured objects with `text`, `met`, and `evidence_refs`. `acceptance_replace` remains available as a compatibility alias. Use `depends_on_changes` to declare prerequisite changes through the API; Verlyn validates the ids and rejects self-references or cycles.
- `GET /api/workflow/{repo_slug}/changes/{change_id}`
  Fetch the full change record after an operator selects a specific change. Prefer this detail route over expanding startup change summaries.
  Use `exclude_completed_tasks=true` when the caller only needs active work-item payloads for the selected change.
- `GET /api/repos/{repo_slug}/runs/{run_id}`
  Fetch the full run snapshot after an operator selects a specific run. Prefer this detail route over inflating startup run-history summaries.
- `GET /api/workflow/{repo_slug}/owner-options`
  Load the registered workflow-owner options for the selected repo. This list is already filtered to active user profiles that are visible to that repository or its owning project. The UI should use this list for ownership, reviewer, and approver assignment controls instead of free text.
- `POST /api/changes/{repo_slug}/{change_id}/tasks`
  Create a work item. Omit `task_id` and `id`; Verlyn allocates the durable id and writes the updated change in one DB transaction.
- `POST /api/changes/{repo_slug}/{change_id}/tasks/{task_id}`
  Update an existing work item. This route returns `404` when the work-item id is not already present on the change.
  When a change-mutation response had to wait on a held change-record lock or recover a stale lock file, Verlyn now includes transient `_workflow_lock` metadata in the returned change payload. Treat that as runtime status only; it is not persisted source-of-truth workflow data.
- `POST /api/changes/{repo_slug}/tasks/batch`
  Create or update one or more work items through the canonical batch contract.
- `POST /api/changes/{repo_slug}/{change_id}/tasks/{task_id}/work`
  Generate or regenerate the durable work brief. If the task is still `todo` or `pending`, this route will normally move it into active work.
- `GET /api/changes/{repo_slug}/{change_id}/tasks/{task_id}/workbench`
  Fetch the summary-first selected-task workbench payload. Use this when the UI or an assistant needs the current task state, next action, proof source, readiness gate, and recent execution summary in one read path instead of stitching those details from separate calls.
  The selected-task workbench should explain its purpose at the top: move one task forward from intake, execution, proof, and handoff without leaving the workflow surface. It should lead with the primary next action, not with repeated status history.
- `POST /api/changes/{repo_slug}/{change_id}/tasks/{task_id}/preflight`
  Inspect whether task execution is ready before running AI execution.
- `POST /api/changes/{repo_slug}/{change_id}/tasks/{task_id}/execute`
  Run the AI execution path for a task when the work brief and gate are ready.
- `GET /api/repos/{repo_slug}/batch-execution`
  Inspect the shared batch-execution control plane. The default read is active-only and DB-scoped to live `queued` or `running` queue rows so stale terminal records do not leak into normal workstream/run surfaces. Pass `queue_id` when you want one queue-focused snapshot, and pass `include_history=true` only for an intentional bounded inspector/history read that includes failed, blocked, canceled, and completed records.
- `POST /api/repos/{repo_slug}/batch-execution/plan`
  Preview queue ordering, dependency gating, and the next runnable task for a proposed batch before anything is persisted. This route is deterministic and must not run provider checks, AI readiness fleshing, repo scans, or work-brief persistence during passive UI refresh. Queue creation and queue start still enforce the full task-execution readiness contract before actual work can run.
- `POST /api/repos/{repo_slug}/batch-execution/queues`
  Enqueue a batch of changes through the shared control plane. Use this instead of creating queue records by hand so dependency checks, safe auto-focus brief repair, and durable queue metadata stay consistent with the engine contract.
- `POST /api/repos/{repo_slug}/batch-execution/queues/{queue_id}/start-next`
  Start the next runnable entry in a durable queue. The response includes the updated queue, the started entry, and a fresh inspection snapshot so callers can refresh one screen or CLI step without issuing a second read. The shared engine rechecks task-execution readiness right before the entry starts, preserves the just-started running entry in that immediate inspection snapshot, and fails closed for queues that are already `failed`, `blocked`, `canceled`, or `completed`; callers should retry or cancel instead of continuing a terminal queue.
- `POST /api/repos/{repo_slug}/batch-execution/queues/{queue_id}/cancel`
  Cancel a queued batch and record the operator reason when supplied. Queued and running entries move into the canceled state through the shared engine instead of being silently dropped.
- `POST /api/repos/{repo_slug}/batch-execution/entries/{entry_id}/cancel`
  Cancel one queued or running entry when an operator needs to stop only part of the batch.
- `POST /api/repos/{repo_slug}/batch-execution/entries/{entry_id}/retry`
  Retry a failed, blocked, or canceled entry through the shared control plane. Retries create a fresh queue entry and preserve retry lineage metadata so restart and audit views can explain what happened instead of mutating history in place.
- `POST /api/repos/{repo_slug}/batch-execution/entries/{entry_id}/recovery-drafts`
  Generate a reviewable AI recovery draft for a failed, blocked, or canceled batch entry. Use this when an operator wants Verlyn to translate durable queue state, restart-recovery history, gate snapshots, and linked change context into a follow-up change draft or work-item draft instead of manually rewriting the failure into tracked work.
- `POST /api/repos/{repo_slug}/batch-execution/entries/{entry_id}/recovery-drafts/{draft_id}/apply`
  Apply a reviewed batch recovery draft onto a new change or an existing tracked change. The response includes the updated entry inspection plus the created or updated change so the caller can refresh the batch queue and move directly into the change workspace without a second lookup.
- `POST /api/changes/{repo_slug}/{change_id}/bind-branch`
  Bind or create a work branch without forcing a checkout change when the route supports it. The write response preserves the caller's live git snapshot for that branch update; later reads still refresh against the repo's current state.
  Verlyn now treats branch attachment as a prerequisite for implementation: work, preflight, execute, and work-starting task status changes should block until the assigned branch exists and is attached.
  Branch binding should update branch metadata only; it must not rewrite already-scoped DB-backed change or work-item content as a side effect.
- `POST /api/changes/{repo_slug}/{change_id}/local-merge`
  Use the local-git merge closeout path instead of marking a local-git change merged by hand.
  Both local and hosted merge closeout paths should also finish the managed `Review findings` and `Finalize handoff` work items so the change ledger matches the merged/handoff-complete state.
  Successful closeout now also stamps the linked change with `merged_at` plus `delivery_metrics` such as delivery mode, base/work branch, merge method, merge commit or head sha detail, branch cleanup flags, closeout timing, and whether Verlyn created the closeout commit.

Deployment provider contract note:

- Query `/api/repos/{repo_slug}/delivery/providers` before adding or changing vendor-specific delivery code. The shared delivery contract now groups provider actions by resource family such as projects, environments, services, deployments, logs, variables, domains, and lifecycle.
- The same payload now exposes the manifest-backed provider contract: autodiscovery roots, manifest schema version, shared shell surfaces Verlyn owns, and provider-owned panel metadata supplied by each plugin.
- Deterministic repository scans such as `assurance` should treat analyzer-generated output roots like `analysis_workspace/` as generated evidence, not source input for the next pass.
- Provider actions still execute through `POST /api/repos/{repo_slug}/delivery/providers/{provider_id}/actions/{capability_id}`, but the inspector and API payloads should read as grouped resource families rather than a single flat capability bucket.
  Hosted delivery behavior comes from the currently running web server process. After merging server-side workflow changes, restart the local Verlyn web server before dogfooding hosted delivery paths so you are not exercising stale merge logic.
- `POST /api/repos/{repo_slug}/settings`
  Update repo-level overrides such as execution profile, hosting profile, and workflow mode.
  Repo workflow policy now derives from `workflow_mode`, and repo deployment binding is a compatibility view over typed profile/provider fields only.
  This route rejects non-empty `workflow_policy` payloads and non-empty `deployment_binding.config` payloads. Use `workflow_mode`, `deployment_profile_id`, and `deployment_provider` instead of persisting repo-side policy or target blobs.
  Workflow mode resolution is `Repo override -> project default -> workspace default`. Project mode should be the normal source of truth; repo-level workflow mode is an intentional exception for a specific repository. When a repo workflow mode is set back to the same value as the inherited project default, Verlyn should collapse that redundant override back to inheritance instead of persisting a no-op repo override.
- `POST /api/repos/add/preview`
  Preview local repository onboarding.
- `POST /api/repos/add/job`
  Start the durable onboarding job for a local repository path.
- `GET /api/repos/{repo_slug}/hosting/pull-request/{pr_number}`
  Load hosted pull-request readiness, blocker, review, and status-check detail for the selected repo.
- `POST /api/repos/{repo_slug}/hosting/pull-request/{pr_number}/close`
  Close a stale hosted pull request from inside Verlyn. When `change_id` is supplied, Verlyn requires that the linked change is already merged and that the recorded work branch still matches the PR head branch before it will close the PR. Use this repair path when a change has already been delivered but GitHub still shows the older PR as open.
- `POST /api/repos/{repo_slug}/hosting/pull-request/{pr_number}/merge`
  Merge an eligible hosted pull request to the base branch from inside Verlyn, optionally delete the remote and local work branches, and sync linked change closeout state when `change_id` is supplied.
  Successful hosted closeout should finish the managed `Review findings` and `Finalize handoff` work items before the closeout packet is committed.
  The linked change record now also persists `merged_at` and `delivery_metrics` so later UI views and assistants can see when the merge happened, what delivery path Verlyn used, and how long the closeout attempt took without re-querying the provider.
  When `change_id` is supplied, Verlyn now verifies that the tracked change branch matches the PR head branch before it attempts the hosted merge.
  If the PR is not already merged and the local worktree is dirty, the route still fails closed with a `409` unless the dirt is limited to Verlyn-managed closeout files for the tracked change.
  Hosted merge also retries GitHub's transient `mergeable = null` window for a short bounded period before it fails, so a just-updated PR does not immediately kill the whole batch because mergeability is still being computed.
  When hosted closeout needs to switch from the work branch back to `main`, Verlyn can now temporarily stash those same managed closeout files, sync the base branch, and restore them before writing the final closeout commit.
  If the PR is already merged on a retry, Verlyn treats the merge phase as already complete, may skip base sync when only those managed closeout files are dirty, and reports any remaining sync blockage in the structured recovery payload instead of collapsing into a generic route failure.

When you need full detail, prefer either the narrower route or an explicit full repo payload instead of assuming every startup call should inline everything:

- `GET /api/repos/{repo_slug}?payload_profile=full`
- `GET /api/workflow/{repo_slug}?payload_profile=full`
- `GET /api/changes/{repo_slug}?exclude_closed=true` or `GET /api/workflow/{repo_slug}/changes?exclude_closed=true` when the caller only needs open/deferred change summaries
- `GET /api/changes/{repo_slug}/{change_id}` for the selected change
- `GET /api/changes/{repo_slug}/{change_id}?exclude_completed_tasks=true` or `GET /api/workflow/{repo_slug}/changes/{change_id}?exclude_completed_tasks=true` when the caller only needs active work items for the selected change
- `GET /api/repos/{repo_slug}/runs/{run_id}` for the selected run
- `GET /api/reports/{repo_slug}/{run_id}` for report bodies
- `POST /api/projects/{project_id}/deployment/providers/{provider_id}/targets` when a project binding needs provider-side projects or environments
- `POST /api/repos/{repo_slug}/delivery/providers/{provider_id}/targets` when a repo override needs provider-side services or a repo-scoped target refresh

For repo score, comparisons, and trends, treat analysis profiles as two distinct score lanes instead of one continuous line:

- `Deterministic posture` covers `baseline_deterministic`, `manual_prep`, and `manual_finalized`
- `Deep confidence` covers `api_deep_review`
- baseline posture is the fast operational signal
- deep confidence is the authoritative confidence lane when both exist
- do not report a numeric score delta across mixed lanes; show a profile or lane change instead
- if older evidence is missing `analysis_profile`, repair the DB-backed run or comparison summary rows instead of inferring the lane from report counts or report-profile names

Batch execution is now a shared repo-level control plane, not a UI-only convention. The engine and durable queue state live under `workflow/execution_engine.py` and `workflow/execution_control_plane.py`, and assistants now have both repo API routes and repo-local helper or raw CLI commands for the same queue lifecycle. If you are operating from the terminal, prefer `python scripts/verlyn_workflow.py batch-*` first, then fall back to the repo API only when a narrower automation or web path needs it. Queued entries are restart-safe, and interrupted `running` entries are automatically reconciled to `failed` on the next batch touch so assistants and operators see an honest queue state after a restart. Do not reintroduce ad hoc workflow-file mutations or one-off scripts while that surface is catching up.

Normal web runs now emit `verlyn.performance` log lines for hot repo and workflow routes by default. Use this repeatable dogfood check:

1. load the repo once and capture the cold `change_workspace.list` and `repository_payload.build` events
2. reload the same repo once to confirm the warm `cache_hit=true` path
3. after a process restart, confirm the relational summary path rebuilds or reuses DB-backed summary state without reading repo-local workflow files
4. compare `fingerprint_ms`, `record_load_ms`, `enrich_ms`, `summarize_ms`, `payload_bytes`, `change_summaries_ms`, `workflow_analytics_ms`, and `all_run_changes_reused`
5. if the hot path still feels slow, attach the concrete measurements to an active performance change instead of describing the issue only in prose

On the active dogfood repo, persisted summary reuse cut the cold summary path from roughly `5607 ms` to roughly `50 ms` once the change-tree fingerprint matched.

Set `VERLYN_PERFORMANCE_LOGGING=0` to suppress them or `VERLYN_PERFORMANCE_LOG_LEVEL=DEBUG` to increase detail during investigation.

Durable workflow source-of-truth state belongs to the DB-backed/project-store lane. Do not rehydrate current workflow truth from old repo-local or workspace-local flat files. Relational PostgreSQL schema changes are forward-only: upgrade an existing DB in place with `python scripts/upgrade_relational_project_store.py --json` instead of relying on reset/reseed flows. Runtime auth, user-profile, and settings state now lives in the relational schema instead of durable workspace JSON files. Generated work briefs and execution artifacts are evidence, not versioned source-of-truth records.

Workstream mutations use transient per-record lock files during writes. Those lock files are internal coordination artifacts, should now disappear after normal writes complete, are ignored from git, and may be auto-recovered when Verlyn detects a stale lock from a dead process.

For hosted repositories, keep the mental model clean:

- `Workflow -> Change workspace -> Overview -> Work branch` owns change-to-branch binding.
- `Selected repository -> Repo host -> Host connection` owns provider/auth context.
- `Selected repository -> Repo host -> Repo branch operations` owns generic checkout and later branch cleanup.
- `Selected repository -> Repo host -> Hosted delivery` owns commit, push, pull-request readiness, PR creation/update, and hosted merge.
- Deployment providers are a third lane. Use deployment profiles for vendor credentials and delivery targets instead of overloading repo-host settings with non-repo vendors such as Railway.
- Provider target browsing now follows the same split: workspace deployment profiles hold the reusable provider connection, project bindings hold default project/environment targets, and repo bindings only override the repo-specific target details such as service selection.
- For Railway, expect two browse behaviors: account or workspace control-plane tokens can enumerate projects, while project tokens only browse the currently scoped project and should be used for project-level service selection rather than account-wide project discovery.
- Railway workspace inspection should not require a selected repo. Treat account validation and project creation as workspace/control-plane actions, and keep deploy/status/log/public URL actions repo-bound so service targeting stays explicit.
- Railway provider actions now use provider-declared action fields inside the shared inspector. For Railway, that means service and environment actions can switch between inspect and create, variable actions can list/set/delete, domain actions can inspect/generate/add, and storage actions can inspect volumes, attach or detach them from services, and run backup or restore flows without introducing one-off core UI routes for each operation.

For repo-local helper usage, `python scripts/verlyn_workflow.py ...` should resolve Verlyn from the checked-out repo's own `cli.py`, then the installed `.verlyn/workflow_pack.json` metadata, then `verlyn` on `PATH`. Ambient routing env vars such as `VERLYN_BIN`, `VERLYN_HOME`, `VERLYN_CONFIG`, and `VERLYN_WORKSPACE_ROOT` should not be part of the normal helper contract.
Fresh governance installs now seed the central Verlyn checkout path and canonical `workspace_root` into `.verlyn/workflow_pack.json`, so generated repo-local wrappers should work without manual shell setup and should keep using the shared workspace even from clean worktrees. Repo-add flows also rewrite that metadata to the actual shared workspace root when a governed repo is attached to a workspace. In the DB-backed product lane, `install_mode = governance` is the only supported repo install state for the web and helper surfaces. Verlyn-managed changes and work items are native product behavior now, not a separate governance-install option. If the central checkout moves or an older generated repo predates the current metadata, repair it from the central Verlyn checkout with `python3 cli.py --target /path/to/repo install --mode governance --force`.
Repo-local helper wrappers now invoke the target `cli.py` with `python -B` so stale bytecode cannot wedge workflow commands after rapid source changes.
When you set a change lifecycle explicitly with the repo-local helper, Verlyn should preserve that requested change status instead of silently downgrading it from task heuristics alone.
When you need to process a whole batch queue from the terminal on a repo that will switch work branches during execution, prefer `python scripts/verlyn_workflow.py batch-start-next <queue-id> --execution-mode run_change --continue-queue ...`. That keeps the remaining queued entries inside one stable controller process instead of requiring a fresh helper invocation after each branch switch.

For run-centered workflow, keep the mental model clean too:

- selecting a run changes the evidence context immediately
- the run history panel should also show the selected run explicitly so the click result is obvious
- the primary workflow path should default to changes linked to that selected run
- a newer successful report-bearing run automatically becomes the current work anchor for new changes, while older runs stay available as evidence
- if the newest run failed, keep using the latest successful run as the current work anchor until a newer successful run completes
- if the newest run completed but produced no reports, do not let it displace an older report-bearing work run; keep it in run history as evidence instead
- `start-change` and run-binding paths should only attach changes to successful completed runs; an explicit `--run-id` or bind request that names a queued, running, failed, or aborted run should fail clearly instead of recording that run on the change
- if a restored selected run is still valid but has no linked changes, prefer the current work run before treating the workflow lane as empty
- app-owned repo runs now keep `run_context.json` warm with `updated_at`, `current_stage_started_at`, `current_stage_updated_at`, and `current_stage_elapsed_seconds` while a stage is active so long deterministic stages stay observable
- if an app-owned run stops reporting progress for too long, the web job store should recover it as `aborted` during normal API access instead of waiting for a server restart
- recovered stale runs should clear `current_stage` and its timing fields so the terminal run state does not keep looking live after recovery
- if a qualifying full repo run completes and becomes the current work anchor, Verlyn should automatically carry active changes forward to that new run instead of leaving them stranded on the previous anchor
- if older runs still have open changes after that, treat it as supersession drift to repair; the UI should inform the operator, not ask them whether to keep actionable work on a closed or superseded run
- use `POST /api/repos/{repo_slug}/run-supersession/carry-forward` when you need to repair or replay carry-forward for every open change from an older run to the current one in one step
- if a long-lived change should continue against fresher evidence, use `POST /api/changes/{repo_slug}/{change_id}/carry-forward` or the `Carry forward to selected run` control instead of treating run rebinding as a repair-only action
- change selection should be scoped to the selected run, so a new run does not inherit a repo-history selection
- full repo-wide change history belongs in an explicit history surface, not mixed into the main run workspace
- backlog counts should read as `visible / in scope / total`, not as a single repo-history number masquerading as the current working set
- when no active changes exist in the current scope, backlog should fall back to a non-empty history view instead of stranding the operator on an empty active-only board

For reusable demo cleanup, use the project cleanup route or the `Project portfolio -> Cleanup and reset` UI section. The cleanup path should archive local workspace artifacts, remove the project catalog entry, and remove any managed repo workspace roots that would otherwise keep the repo visible through workspace auto-discovery. It should not touch a GitHub-hosted repo that lives outside the workspace root.

Treat baseline contract specs as Verlyn-managed relational material, not repo-local files or default prompt ballast. Do not use `workstream/specs/` as durable truth; load baseline specs only through Verlyn's relational baseline-spec APIs or helpers.

## Task-Scoping Shortcut

When you are preparing work rather than implementing it:

1. Create or update the change with `/api/changes/{repo_slug}` or `/api/changes/{repo_slug}/{change_id}`
2. Create work items with `/api/changes/{repo_slug}/{change_id}/tasks`, or refine existing work items with `/api/changes/{repo_slug}/{change_id}/tasks/{task_id}`
3. Request or record reviews with `/api/changes/{repo_slug}/{change_id}/reviews/request` and `/api/changes/{repo_slug}/{change_id}/reviews/record`; those routes should keep the durable review and change records aligned
4. Generate a work brief with `/api/changes/{repo_slug}/{change_id}/tasks/{task_id}/work`
5. Load `/api/changes/{repo_slug}/{change_id}/tasks/{task_id}/workbench` when you need the unified selected-task operator view before execution or review

That combination is the supported path for turning a rough idea into a real Verlyn work item without editing durable records by hand.

For a brand-new app with no existing repo yet, the supported kickoff path is:

1. `POST /api/kickoff/plan`
2. review the inferred project, template, path, starter tasks, and blueprint questions
3. answer any open blueprint questions with `question_answers`, then preview again so Verlyn can refresh the plan instead of making the operator retype the app description
3. the generated first-task brief should seed concrete scaffold files from the selected template so a new operator does not have to infer `index.html` or `app.js` by hand
4. `POST /api/kickoff/execute` with confirmation

In the UI, the kickoff panel should default to `Start a new app`. `Use an existing project` stays available, but it should be a deliberate secondary choice so a fresh idea does not inherit another project's workspace state. New-project kickoff must expose workflow mode directly in that panel so solo vs team posture is chosen before files are created, and the implicit default should be `solo` until the product deliberately changes that policy.
Project-bound change ids should be seeded from the project id with numeric suffixes such as `verlyn-12`, and generated work item ids should use a separate compact project-seeded counter such as `verlyn-w12`.
Existing DB-backed workflow records should already carry the current project-seeded identifiers; do not normalize current workflow truth by backfilling old repo-local flat files.
`Existing projects` now lives as its own sidebar category so switching contexts is obvious instead of hidden inside setup.
Workspace-wide execution, hosting, auth/session, and user-access administration now lives in the dedicated `Global settings` surface instead of the left sidebar workflow rail.

Use Global settings -> Deployment provider settings to create or switch deployment connection profiles, store provider-specific connection config or secrets, and inspect the provider contract before attaching it to projects or repos. Delivery settings should now follow the same inheritance pattern as the other provider lanes: workspace connection, project target defaults, then repo target override.
Provider-specific setup guidance in that surface should come from the selected provider descriptor itself. Do not hard-code Railway-or-any-other-provider help text into the shared field editor; plugin-owned guidance cards and field help metadata are the contract.
Railway field help should make the first path explicit in-product: choose `project` token kind in the workspace connection, then set the target service in the repo binding and leave `project_id` / `environment_id` blank unless the operator deliberately uses an account/workspace control-plane token. When a control-plane token is selected, the same workspace surface should be able to validate the Railway account and create a Railway project before the project/repo binding lane is filled in.
Local Docker should stay in the same deployment shell instead of inventing a sidecar UI: workspace connection holds optional `docker_host` or `docker_context`, repo binding holds `image_name`, `container_name`, ports, `root_directory`, and the provider actions should cover daemon validation, local container browse, build/run, lifecycle control, status/logs, and truthful URL reporting through the generic inspector. Workspace-level inspect should report connection readiness without pretending repo delivery is blocked by a missing `Dockerfile` until a repo target is actually selected. Local containers now follow the same authenticated DB-backed contract as the main web lane, so repo binding only needs an explicit `session_secret` before deploy or redeploy proceeds. That secret must now come from `VERLYN_WEB_AUTH_SESSION_SECRET` in direct env or the encrypted project secret bundle Verlyn resolves at runtime; checked-in `web.auth.session_secret` config is no longer an approved source. Redeploy should build first, preserve the previous container as rollback state, and restore it automatically if the replacement container fails.
The web API now also exposes authenticated in-process service timing at `GET /api/admin/service-metrics`. Treat it as an admin-only diagnostics surface for request counts, inflight traffic, and latency totals; it is not a plugin-owned metrics contract.
Railway resource actions should stay safe by default: `Public URL` and `Domains` should inspect current Railway status unless the operator explicitly switches the domain action to `generate` or `add`, so merely checking provider state does not create side effects.
Railway storage actions should keep project and service ownership explicit: volumes are project-scoped resources, service attachment and mount-path state belong to volume instances, and backup or restore actions should require an explicit volume selection rather than pretending storage is a workspace-global mount.
The root `Dockerfile` is now the reference deployment contract for Railway-style providers and future products built with Verlyn. It builds `ui/dist` in a Node stage, installs Verlyn into a Python runtime stage, persists workspace data at `/data/analysis_workspace`, and launches the app by mapping provider `PORT` into `VERLYN_WEB_PORT=${PORT:-8010}` before `verlyn-web` starts.
Hosted container deployments should not depend on committed config accounts or bootstrap credentials. The reference contract now expects the encrypted project secret bundle plus a mounted key file and durable DB-backed auth rows instead of baked credentials or auto-generated session material.
Built-in `db_password` authentication is exact-case for both usernames and passwords, so `AdminUser` and `adminuser` remain distinct durable user profiles instead of collapsing into one operator record.
If a provider or assistant proposes a different build/start command while the repo already has this root Docker contract, treat that as drift to justify explicitly rather than the new default path.
For a brand-new app, kickoff now seeds a baseline run with zero reports and binds the starter change to it so run-linked workflow starts immediately. Kickoff should also create and check out the first work branch so the starter change does not fall back to planned-branch repair before implementation can begin. The first prepared task should remain execution-ready when the work brief is refreshed against that kickoff baseline run. If a kickoff change still shows no run link, treat that as a fallback condition and bind a run from `Runs` before continuing.
Kickoff phase language should be operator-legible: the first work item should clearly be the starting slice, later kickoff tasks should say what prior work they depend on, and open blueprint questions should be answerable in-product instead of forcing operators to guess whether `Refresh brief` is the next step.
After kickoff, continue in `/api/changes/{repo_slug}/{change_id}/tasks/{task_id}/workbench`.
Inside the work-item workbench, the operator should be able to answer three questions immediately: what this surface is for, what to do next, and which supporting sections matter right now. If the UI requires the operator to infer that from repeated cards or lifecycle controls, treat that as a workflow clarity regression.
The inspector reviewer inbox should also be actionable: reviewer and approver items should open the selected change in Review, while work-item owner items should open the assigned work item in Work items. If the inbox only reports waiting work without a direct route into the workflow surface, treat that as an inspector workflow regression.
The inspector should stay high-signal and viewport-safe. Keep `Run` focused on what matters now plus review and handoff posture, keep `Docs` limited to durable reports and workstream-health signals, keep `Activity` centered on alerts, reviewer inbox, workflow pressure, and trend watch, and do not let the rail duplicate broad main-surface content or fall out of the viewport instead of scrolling inside the rail.
Run history should speak in workstream terms, not only analyzer-engine terms. Keep execution status visible, but each run card should also report whether it is the `Current work run`, still has `Open work remains`, is `Closed out`, or has `No tracked work`, alongside change, work-item, and remaining-work counts.
Do not show the same workstream counts twice on the active run cards. Use a single summary line for counts, then spend the secondary line on a real differentiator such as current stage progress or superseded lineage.
The `Workstream -> Backlog` surface should also expose search as a first-class board view, not a buried filter-only affordance. Search results should jump back into the existing change or work-item workflow instead of creating a parallel backlog experience.

Phase 1 kickoff is intentionally local and template-driven. Do not promise hosted repo creation, container orchestration, or deployment automation from this path yet.

If verification or dogfooding reveals a new regression, stop and create or attach a change/task before committing or merging the fix. Do not leave a discovered bug as an untracked working-tree patch just because the reproduction happened late.

Use subagents selectively. They are a good fit for narrow, bounded, low-coupling parallel work such as isolated inventories, focused tests, or clearly separated write scopes. Avoid delegating tightly coupled workflow logic, central orchestration, or state-heavy UI changes unless there is a strong reason the speedup outweighs reintegration cost. The lead agent still owns critical-path integration and should not hand the immediate blocker to a subagent by reflex.

## Local-Git Dogfooding Realities

- Local-git mode does not have hosted pull requests.
- Verlyn can still bind branches, commit, merge to `main`, and delete merged local branches through the local-git routes.
- Do not mark a local-git change `merged` manually if its branch is not actually on `main`.
- Prefer the branch-binding route when scoping multiple changes so you do not switch the current checkout unnecessarily.
- Expect the immediate bind or update response to reflect the snapshot captured for that workflow write, but treat later `GET /api/changes/...` reads as the current source of truth for the repo's live dirty state.
- If a change only has a planned branch name and that branch does not exist yet, the next workflow step should tell you to create or bind the branch first. Verlyn should only tell you to switch back or rebind when a real assigned branch already exists and the current checkout diverges from it.
- Treat a planned branch as planning metadata, not implementation readiness. A change is not truly ready to start until its assigned branch exists and Verlyn can attach work to it.
- Expect merge or branch-delete operations to reject dirty or unsafe states rather than silently forcing them.

## When To Fall Back

Fallback to lower-level paths only when one of these is true:

- the helper does not expose the route yet
- the API does not expose the needed mutation yet
- the change is explicitly fixing Verlyn workflow behavior
- you are debugging the Verlyn engine itself

If you do fall back, record why in the change or task notes so the gap can become product work instead of tribal knowledge.

## Exit Criteria

Before you call assistant work complete:

- acceptance criteria are satisfied
- verification is recorded
- task and change ledgers are updated
- remaining risks are written down
- the repo-native workflow state matches what you claim in chat
