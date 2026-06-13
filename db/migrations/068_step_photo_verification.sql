BEGIN;

ALTER TABLE assembly_photo_checks
    ADD COLUMN IF NOT EXISTS step_id uuid REFERENCES assembly_plan_steps(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'cannot_verify',
    ADD COLUMN IF NOT EXISTS verification_confidence double precision,
    ADD COLUMN IF NOT EXISTS verification_summary text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS verification_findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS requested_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS verification_provider text NOT NULL DEFAULT 'diagnostics',
    ADD COLUMN IF NOT EXISTS verification_model text,
    ADD COLUMN IF NOT EXISTS ai_result jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS assembly_photo_checks_step_idx
    ON assembly_photo_checks (plan_id, step_id, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES (68, 'step_photo_verification')
ON CONFLICT (version) DO NOTHING;

COMMIT;
