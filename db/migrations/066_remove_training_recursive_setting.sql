BEGIN;

DELETE FROM app_settings
WHERE key = 'TRAINING_RECURSIVE';

INSERT INTO schema_migrations (version, name)
VALUES (66, 'remove_training_recursive_setting')
ON CONFLICT (version) DO NOTHING;

COMMIT;
