BEGIN;

DELETE FROM app_settings
WHERE key = 'AI_KEY_ENCRYPTION_SECRET';

INSERT INTO schema_migrations (version, name)
VALUES (28, 'remove_ai_key_secret_setting')
ON CONFLICT (version) DO NOTHING;

COMMIT;
