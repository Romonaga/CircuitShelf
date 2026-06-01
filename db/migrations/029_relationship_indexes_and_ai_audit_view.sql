BEGIN;

-- The old UUID user primary key was kept as users.uuid_id during the
-- numeric-user-id migration. Runtime code now uses users.id everywhere.
DROP INDEX IF EXISTS users_uuid_id_key;
ALTER TABLE users
    DROP COLUMN IF EXISTS uuid_id;

-- Relationship/index hygiene for high-traffic audit, reporting, and cleanup
-- paths. PostgreSQL does not automatically index the referencing side of a
-- foreign key, so add the ones we depend on for joins, deletes, and reports.
CREATE INDEX IF NOT EXISTS ai_assist_events_provider_owner_created_idx
    ON ai_assist_events (provider_key_owner_user_id, created_at DESC)
    WHERE provider_key_owner_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ai_assist_events_provider_created_idx
    ON ai_assist_events (provider_type_id, created_at DESC)
    WHERE provider_type_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ai_assist_events_paid_by_created_idx
    ON ai_assist_events (paid_by, created_at DESC);

CREATE INDEX IF NOT EXISTS ai_assist_events_context_idx
    ON ai_assist_events (context_type, context_id)
    WHERE context_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ai_model_pricing_overrides_updated_by_idx
    ON ai_model_pricing_overrides (updated_by)
    WHERE updated_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS assembly_photo_checks_user_idx
    ON assembly_photo_checks (user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS assembly_plans_created_by_idx
    ON assembly_plans (created_by)
    WHERE created_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_images_page_idx
    ON document_images (page_id)
    WHERE page_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_ingest_ai_reviews_provider_idx
    ON document_ingest_ai_reviews (provider_type_id)
    WHERE provider_type_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_ingest_scope_overrides_created_by_idx
    ON document_ingest_scope_overrides (created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_scope_audit_previous_entity_idx
    ON document_scope_audit (previous_entity_id)
    WHERE previous_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_scope_audit_new_entity_idx
    ON document_scope_audit (new_entity_id)
    WHERE new_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS documents_created_by_idx
    ON documents (created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS documents_reviewed_by_idx
    ON documents (reviewed_by)
    WHERE reviewed_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS entity_ai_provider_settings_updated_by_idx
    ON entity_ai_provider_settings (updated_by)
    WHERE updated_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS password_policies_updated_by_idx
    ON password_policies (updated_by)
    WHERE updated_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS performance_work_runs_entity_time_idx
    ON performance_work_runs (entity_id, started_at DESC)
    WHERE entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS performance_work_runs_user_time_idx
    ON performance_work_runs (user_id, started_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS query_log_sources_chunk_idx
    ON query_log_sources (chunk_id)
    WHERE chunk_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS query_log_sources_document_idx
    ON query_log_sources (document_id)
    WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS response_cache_sources_chunk_idx
    ON response_cache_sources (chunk_id)
    WHERE chunk_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS response_cache_sources_document_idx
    ON response_cache_sources (document_id)
    WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS system_ai_provider_settings_updated_by_idx
    ON system_ai_provider_settings (updated_by)
    WHERE updated_by IS NOT NULL;

-- Friendly DB-audit view for tools like DBeaver. The base table keeps proper
-- numeric FKs; this view exposes labels without duplicating application logic.
CREATE OR REPLACE VIEW ai_assist_events_expanded AS
SELECT ev.id,
       ev.created_at,
       ev.entity_id,
       en.name AS entity_name,
       ev.user_id,
       u.username,
       coalesce(nullif(u.display_name, ''), nullif(u.nickname, ''), u.username::text) AS user_label,
       ev.provider_key_owner_user_id,
       key_owner.username AS provider_key_owner_username,
       coalesce(nullif(key_owner.display_name, ''), nullif(key_owner.nickname, ''), key_owner.username::text) AS provider_key_owner_label,
       ev.provider_type_id,
       provider.code AS provider_code,
       provider.display_name AS provider_name,
       ev.task_type_id,
       task.code AS task_code,
       task.display_name AS task_name,
       ev.model_name,
       ev.context_type,
       ev.context_id,
       ev.round_number,
       ev.round_count,
       ev.input_tokens,
       ev.cached_input_tokens,
       ev.output_tokens,
       ev.estimated_cost,
       ev.paid_by,
       ev.success,
       ev.error_message
FROM ai_assist_events ev
LEFT JOIN entities en ON en.id = ev.entity_id
LEFT JOIN users u ON u.id = ev.user_id
LEFT JOIN users key_owner ON key_owner.id = ev.provider_key_owner_user_id
LEFT JOIN ai_provider_types provider ON provider.id = ev.provider_type_id
LEFT JOIN ai_task_types task ON task.id = ev.task_type_id;

INSERT INTO schema_migrations (version, name)
VALUES (29, 'relationship_indexes_and_ai_audit_view')
ON CONFLICT (version) DO NOTHING;

COMMIT;
