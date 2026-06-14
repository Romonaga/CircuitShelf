BEGIN;

ALTER TABLE system_ai_provider_settings
    ADD COLUMN IF NOT EXISTS encrypted_admin_api_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS admin_key_preview text NOT NULL DEFAULT '';

INSERT INTO schema_migrations (version, name)
VALUES (70, 'openai_admin_key_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
