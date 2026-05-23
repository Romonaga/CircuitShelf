BEGIN;

ALTER TABLE assembly_photo_checks
    ADD COLUMN IF NOT EXISTS diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb;

INSERT INTO schema_migrations (version, name)
VALUES (19, 'photo_check_diagnostics')
ON CONFLICT (version) DO NOTHING;

COMMIT;
