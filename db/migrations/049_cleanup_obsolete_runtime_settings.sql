BEGIN;

INSERT INTO app_settings (key, value_type, text_value, integer_value, numeric_value, boolean_value, description, updated_at)
SELECT
    'RESPONSE_CACHE_CAPACITY',
    'integer',
    NULL,
    integer_value,
    NULL,
    NULL,
    'Maximum number of cached query responses kept by the Postgres-backed response cache.',
    now()
FROM app_settings
WHERE key = 'LRU_CACHE_SIZE'
  AND integer_value IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM app_settings existing
      WHERE existing.key = 'RESPONSE_CACHE_CAPACITY'
  )
ON CONFLICT (key) DO NOTHING;

DELETE FROM app_settings
WHERE key IN (
    'API_HOST',
    'API_PORT',
    'BYPASS_NLTK_DOWNLOAD',
    'LRU_CACHE_SIZE',
    'NLTK_DATA_DIR'
);

INSERT INTO schema_migrations (version, name)
VALUES (49, 'cleanup_obsolete_runtime_settings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
