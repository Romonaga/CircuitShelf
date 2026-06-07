BEGIN;

INSERT INTO app_settings (key, value_type, text_value, integer_value, numeric_value, boolean_value, description, updated_at)
VALUES (
    'INGEST_LOCAL_AI_MAX_PENDING',
    'integer',
    NULL,
    1,
    NULL,
    NULL,
    'Maximum live local LLM ingestion-review jobs allowed at once, including one running job. Keeps large ingests from flooding the GPU queue.',
    now()
)
ON CONFLICT (key) DO UPDATE
SET value_type = EXCLUDED.value_type,
    text_value = NULL,
    integer_value = EXCLUDED.integer_value,
    numeric_value = NULL,
    boolean_value = NULL,
    description = EXCLUDED.description,
    updated_at = now();

INSERT INTO app_settings (key, value_type, text_value, integer_value, numeric_value, boolean_value, description, updated_at)
VALUES (
    'INGEST_LOCAL_AI_ADMISSION_TIMEOUT_SECONDS',
    'integer',
    NULL,
    1800,
    NULL,
    NULL,
    'Seconds an ingestion review may wait before entering the local LLM queue when the local GPU lane is busy.',
    now()
)
ON CONFLICT (key) DO UPDATE
SET value_type = EXCLUDED.value_type,
    text_value = NULL,
    integer_value = EXCLUDED.integer_value,
    numeric_value = NULL,
    boolean_value = NULL,
    description = EXCLUDED.description,
    updated_at = now();

INSERT INTO schema_migrations (version, name)
VALUES (48, 'local_ingestion_ai_backpressure')
ON CONFLICT (version) DO NOTHING;

COMMIT;
