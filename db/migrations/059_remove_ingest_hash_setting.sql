BEGIN;

DELETE FROM app_settings
WHERE key = 'INGEST_HASH_FILES';

INSERT INTO schema_migrations (version, name)
VALUES (59, 'remove_ingest_hash_setting')
ON CONFLICT (version) DO NOTHING;

COMMIT;
