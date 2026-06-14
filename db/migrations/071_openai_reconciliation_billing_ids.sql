BEGIN;

ALTER TABLE system_ai_provider_settings
    ADD COLUMN IF NOT EXISTS provider_project_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS provider_api_key_id text NOT NULL DEFAULT '';

ALTER TABLE entity_ai_provider_settings
    ADD COLUMN IF NOT EXISTS provider_project_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS provider_api_key_id text NOT NULL DEFAULT '';

ALTER TABLE user_ai_provider_settings
    ADD COLUMN IF NOT EXISTS provider_project_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS provider_api_key_id text NOT NULL DEFAULT '';

ALTER TABLE ai_assist_events
    ADD COLUMN IF NOT EXISTS provider_project_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS provider_api_key_id text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ai_assist_events_provider_billing_ids_idx
    ON ai_assist_events (provider_type_id, provider_project_id, provider_api_key_id, created_at DESC);

UPDATE ai_model_pricing pricing
   SET input_per_million = 5.00,
       cached_input_per_million = 0.50,
       output_per_million = 30.00,
       updated_at = now()
  FROM ai_provider_types provider
 WHERE pricing.provider_type_id = provider.id
   AND provider.code = 'openai'
   AND pricing.model_name = 'gpt-5-chat-latest';

UPDATE ai_assist_events ev
   SET provider_project_id = coalesce(nullif(s.provider_project_id, ''), ev.provider_project_id),
       provider_api_key_id = coalesce(nullif(s.provider_api_key_id, ''), ev.provider_api_key_id)
  FROM system_ai_provider_settings s
  JOIN ai_provider_types provider ON provider.id = s.provider_type_id
 WHERE ev.provider_type_id = provider.id
   AND provider.code = 'openai'
   AND ev.paid_by = 'system';

UPDATE ai_assist_events ev
   SET provider_project_id = coalesce(nullif(s.provider_project_id, ''), ev.provider_project_id),
       provider_api_key_id = coalesce(nullif(s.provider_api_key_id, ''), ev.provider_api_key_id)
  FROM entity_ai_provider_settings s
  JOIN ai_provider_types provider ON provider.id = s.provider_type_id
 WHERE ev.provider_type_id = provider.id
   AND provider.code = 'openai'
   AND ev.paid_by = 'entity'
   AND ev.entity_id = s.entity_id;

UPDATE ai_assist_events ev
   SET provider_project_id = coalesce(nullif(s.provider_project_id, ''), ev.provider_project_id),
       provider_api_key_id = coalesce(nullif(s.provider_api_key_id, ''), ev.provider_api_key_id)
  FROM user_ai_provider_settings s
  JOIN ai_provider_types provider ON provider.id = s.provider_type_id
 WHERE ev.provider_type_id = provider.id
   AND provider.code = 'openai'
   AND ev.paid_by = 'user'
   AND ev.provider_key_owner_user_id = s.user_id;

DROP VIEW IF EXISTS ai_assist_events_expanded;

CREATE VIEW ai_assist_events_expanded AS
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
       ev.provider_project_id,
       ev.provider_api_key_id,
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
       ev.final_cost,
       ev.cost_status,
       ev.cost_discrepancy,
       ev.reconciliation_run_id,
       ev.allocation_method,
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
VALUES (71, 'openai_reconciliation_billing_ids')
ON CONFLICT (version) DO NOTHING;

COMMIT;
