BEGIN;

CREATE TABLE IF NOT EXISTS assembly_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    objective text NOT NULL,
    component_name text NOT NULL DEFAULT '',
    component_type text NOT NULL DEFAULT '',
    summary text NOT NULL DEFAULT '',
    confidence numeric(6, 4),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
    created_by citext REFERENCES users(username) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assembly_plan_parts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    name text NOT NULL,
    detail text NOT NULL DEFAULT '',
    UNIQUE (plan_id, ordinal)
);

CREATE TABLE IF NOT EXISTS assembly_plan_power_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    note text NOT NULL,
    UNIQUE (plan_id, ordinal)
);

CREATE TABLE IF NOT EXISTS assembly_plan_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    step_type text NOT NULL CHECK (step_type IN ('wiring', 'check', 'warning')),
    title text NOT NULL,
    instruction text NOT NULL,
    note text NOT NULL DEFAULT '',
    source_path text,
    page_number integer,
    completed_at timestamptz,
    UNIQUE (plan_id, ordinal)
);

CREATE TABLE IF NOT EXISTS assembly_plan_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    source_path text NOT NULL,
    display_name text NOT NULL,
    pages integer[] NOT NULL DEFAULT ARRAY[]::integer[],
    chunk_count integer NOT NULL DEFAULT 0,
    UNIQUE (plan_id, source_path)
);

CREATE TABLE IF NOT EXISTS assembly_plan_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    message text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS assembly_plans_updated_idx
    ON assembly_plans (updated_at DESC);

CREATE INDEX IF NOT EXISTS assembly_plan_steps_plan_idx
    ON assembly_plan_steps (plan_id, ordinal);

CREATE INDEX IF NOT EXISTS assembly_plan_notes_plan_idx
    ON assembly_plan_notes (plan_id, created_at);

INSERT INTO schema_migrations (version, name)
VALUES (13, 'assembly_plans')
ON CONFLICT (version) DO NOTHING;

COMMIT;
