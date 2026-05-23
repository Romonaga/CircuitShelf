BEGIN;

CREATE TABLE IF NOT EXISTS assembly_learning_sessions (
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_ordinal integer NOT NULL DEFAULT 1 CHECK (current_ordinal >= 1),
    mode_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (plan_id, user_id)
);

CREATE TABLE IF NOT EXISTS assembly_photo_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id uuid NOT NULL REFERENCES assembly_plans(id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_mime_type text NOT NULL,
    image_base64 text NOT NULL,
    note text NOT NULL DEFAULT '',
    checklist text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS assembly_photo_checks_plan_idx
    ON assembly_photo_checks (plan_id, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES (18, 'bench_enhancements')
ON CONFLICT (version) DO NOTHING;

COMMIT;
