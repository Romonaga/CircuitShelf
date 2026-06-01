# CircuitShelf Roadmap

## Completed MVPs

- Parts Inventory + Project Finder
  - Store the user's real lab parts in Postgres.
  - Match inventory against indexed books, datasheets, and extracted component intelligence.
  - Show buildable project candidates, missing parts, substitutions when available, and source evidence.
  - Allow promising candidates to become Bench plans.

- Photo-based bench check
  - Let a user upload a breadboard or wiring photo.
  - Save the photo with a Bench plan and generate a plan-specific manual inspection checklist.
  - Analyze photo quality, edge density, dominant colors, and wire-like color pixels.
  - Future work: real visual wire tracing and mistake detection.

- Source-to-bench traceability
  - Every Bench step should link back to exact document pages, chunks, images, and pinout evidence.
  - Useful for trust, debugging, and learning why a step exists.

- Circuit simulator export
  - Generate Bench markdown, LTspice starter notes, and Falstad/CircuitJS drawing notes from a Bench plan.
  - Generate starter SPICE/CircuitJS topologies for recognized LED/resistor and 555 timer plans.
  - Future work: infer broader node-level schematics for op-amp, transistor, sensor, and microcontroller circuits.

- Learning mode
  - Turn Bench plans into guided lessons.
  - Walk through plan steps with learning prompts before moving to the next step.
  - Explain why each power, ground, resistor, capacitor, and signal connection exists.

## Future Deepening

- Recovery work after FastDrive loss
  - Done: Rebuild the entity model: entities, memberships, owner/admin/user roles, and system-admin privileges.
  - Done: Restore entity and user settings, including password policy controls and account profile fields.
  - Done: Restore global corpus versus entity-private document read scope, plus DB-backed upload ingest scope.
  - Done: Restore AI provider configuration, BYOK user keys, system/entity keys, usage auditing, pricing, and budgets.
  - Done: Extend AI pricing beyond the standard short-context rates: long-context, batch/flex, and priority variants.
  - Done: Add live OpenAI model discovery/refresh so admins and users can select from models available to the configured key.
  - Done: Enforce AI budgets, not just report them, with clear payer scope rules for system, entity, and user keys.
  - Done: Restore richer AI usage reporting and export for personal, entity-admin, owner, and system-admin scopes.
  - Done: Restore and harden Project Finder: deduplicate candidates, reject non-project fragments, and use inventory aliases/substitutions correctly.
  - Done: Polish inventory management: row edit, rename by stable part ID, alias editing, location persistence, and right-click delete.
  - Done: Finish account/admin workflows: user creation, password reset, unlock, force-password-change gating, and role management.
  - Done: Add optional OpenAI ingestion review with audited usage. Corpus uses system billing; entity-private documents use entity billing with user-key fallback.
  - Done: Harden AI key encryption operations with environment-based secret handling, encrypted backup/restore tooling, and key-rotation support.
  - Done: Split `circuitshelf.py` into modular backend domains. App factory, route registration, auth dependencies, API routers, stores, server startup helpers, settings/environment bootstrap, source metadata, document intelligence, document management, prompt building, Ollama chat, image retrieval, image state persistence, retrieval helpers, RAG orchestration, ingest statistics, ingest progress, ingest housekeeping, ingest context/scope, document processing, incremental ingest orchestration, index lifecycle/watch startup, runtime status reporting, and runtime service-container wiring are separated.
  - Done/ongoing: Continue moving frontend logic into focused components, hooks, and shared libs so `App.tsx` stays orchestration-only. Review now uses a dedicated queue hook and focused list/detail/scope components.
  - Done: Build a stronger global corpus workflow with corpus/private labels in review, system-admin promotion/demotion controls, scope audit history, and clear global/entity-private visibility.
  - Keep the Kotlin/backend conversion separate until the Python baseline is feature-stable again.

- Real photo-based wire tracing and component recognition.
- Wider simulator netlist generation for common circuit families.
- KiCad schematic export once node-level circuit inference exists.
- Learning-mode answer grading using the local model.
