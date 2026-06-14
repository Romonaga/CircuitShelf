BEGIN;

CREATE TABLE IF NOT EXISTS ai_cost_reconciliation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_type_id smallint REFERENCES ai_provider_types(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    source text NOT NULL DEFAULT 'openai_organization_costs',
    start_time timestamptz NOT NULL,
    end_time timestamptz NOT NULL,
    bucket_width text NOT NULL DEFAULT '1d',
    verified_cost numeric(14, 8) NOT NULL DEFAULT 0,
    estimated_cost numeric(14, 8) NOT NULL DEFAULT 0,
    cost_discrepancy numeric(14, 8) NOT NULL DEFAULT 0,
    event_count integer NOT NULL DEFAULT 0 CHECK (event_count >= 0),
    allocation_method text NOT NULL DEFAULT 'estimated_cost_proportional',
    raw_provider_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    created_by bigint REFERENCES users(id) ON DELETE SET NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS ai_cost_reconciliation_runs_provider_time_idx
    ON ai_cost_reconciliation_runs (provider_type_id, start_time DESC, end_time DESC);

ALTER TABLE ai_assist_events
    ADD COLUMN IF NOT EXISTS final_cost numeric(14, 8),
    ADD COLUMN IF NOT EXISTS cost_status text NOT NULL DEFAULT 'estimated',
    ADD COLUMN IF NOT EXISTS cost_discrepancy numeric(14, 8) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reconciliation_run_id uuid REFERENCES ai_cost_reconciliation_runs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS allocation_method text NOT NULL DEFAULT '';

ALTER TABLE ai_assist_events
    DROP CONSTRAINT IF EXISTS ai_assist_events_cost_status_check;

ALTER TABLE ai_assist_events
    ADD CONSTRAINT ai_assist_events_cost_status_check
    CHECK (cost_status IN ('estimated', 'verified', 'adjusted', 'needs_review', 'not_billable'));

UPDATE ai_assist_events ev
   SET cost_status = 'not_billable',
       cost_discrepancy = 0,
       allocation_method = ''
  FROM ai_provider_types provider
 WHERE ev.provider_type_id = provider.id
   AND provider.code <> 'openai'
   AND ev.cost_status = 'estimated';

CREATE INDEX IF NOT EXISTS ai_assist_events_reconciliation_run_idx
    ON ai_assist_events (reconciliation_run_id)
    WHERE reconciliation_run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ai_assist_events_cost_status_created_idx
    ON ai_assist_events (cost_status, created_at DESC);

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
VALUES (69, 'ai_cost_reconciliation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
