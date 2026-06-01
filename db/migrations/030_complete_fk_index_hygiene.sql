BEGIN;

-- Finish indexing the referencing side of remaining foreign keys. Most of
-- these point to small lookup tables, but keeping them indexed makes FK checks,
-- deletes, and database tooling predictable.
CREATE INDEX IF NOT EXISTS entity_ai_provider_settings_assist_mode_idx
    ON entity_ai_provider_settings (assist_mode_id);

CREATE INDEX IF NOT EXISTS entity_ai_provider_settings_key_policy_idx
    ON entity_ai_provider_settings (key_policy_id);

CREATE INDEX IF NOT EXISTS ingest_run_documents_document_idx
    ON ingest_run_documents (document_id)
    WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS query_logs_username_idx
    ON query_logs (username)
    WHERE username IS NOT NULL;

CREATE INDEX IF NOT EXISTS system_ai_provider_settings_assist_mode_idx
    ON system_ai_provider_settings (assist_mode_id);

CREATE INDEX IF NOT EXISTS user_ai_provider_settings_assist_mode_idx
    ON user_ai_provider_settings (assist_mode_id);

CREATE INDEX IF NOT EXISTS user_ai_provider_settings_key_policy_idx
    ON user_ai_provider_settings (key_policy_id);

INSERT INTO schema_migrations (version, name)
VALUES (30, 'complete_fk_index_hygiene')
ON CONFLICT (version) DO NOTHING;

COMMIT;
