BEGIN;

ALTER TABLE ai_assist_events
    ADD COLUMN IF NOT EXISTS decision_reason text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS latency_ms integer NOT NULL DEFAULT 0;

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
       ev.error_message,
       ev.decision_reason,
       ev.latency_ms
FROM ai_assist_events ev
LEFT JOIN entities en ON en.id = ev.entity_id
LEFT JOIN users u ON u.id = ev.user_id
LEFT JOIN users key_owner ON key_owner.id = ev.provider_key_owner_user_id
LEFT JOIN ai_provider_types provider ON provider.id = ev.provider_type_id
LEFT JOIN ai_task_types task ON task.id = ev.task_type_id;

INSERT INTO schema_migrations (version, name)
VALUES (38, 'ai_assist_decision_audit')
ON CONFLICT (version) DO NOTHING;

COMMIT;
