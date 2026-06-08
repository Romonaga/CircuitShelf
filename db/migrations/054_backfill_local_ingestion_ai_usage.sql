BEGIN;

UPDATE document_ingest_ai_reviews r
   SET paid_by = CASE
       WHEN coalesce(d.is_global, true) THEN 'system'
       WHEN d.entity_id IS NOT NULL THEN 'entity'
       ELSE 'unknown'
   END
  FROM documents d
 WHERE r.paid_by = 'local'
   AND d.source_path = r.source_path;

UPDATE document_ingest_ai_reviews
   SET paid_by = 'system'
 WHERE paid_by = 'local';

INSERT INTO ai_assist_events (
    entity_id,
    user_id,
    provider_type_id,
    task_type_id,
    model_name,
    context_type,
    context_id,
    round_number,
    round_count,
    input_tokens,
    cached_input_tokens,
    output_tokens,
    estimated_cost,
    paid_by,
    provider_key_owner_user_id,
    success,
    error_message,
    decision_reason,
    latency_ms,
    created_at
)
SELECT
    CASE WHEN coalesce(d.is_global, true) THEN NULL ELSE d.entity_id END,
    NULL,
    r.provider_type_id,
    task.id,
    r.model_name,
    'document_ingest',
    NULL,
    1,
    1,
    CASE
        WHEN r.review_json ->> '_inputTokenEstimate' ~ '^[0-9]+$'
        THEN (r.review_json ->> '_inputTokenEstimate')::integer
        ELSE 0
    END,
    0,
    CASE
        WHEN r.review_json ->> '_outputTokenEstimate' ~ '^[0-9]+$'
        THEN (r.review_json ->> '_outputTokenEstimate')::integer
        ELSE 0
    END,
    r.estimated_cost,
    r.paid_by,
    NULL,
    true,
    NULL,
    'Backfilled local ingestion review for ' || r.source_path || ': ' || coalesce(nullif(r.review_json ->> 'reason', ''), 'local ingestion review ran'),
    CASE
        WHEN r.review_json ->> '_latencyMs' ~ '^[0-9]+$'
        THEN (r.review_json ->> '_latencyMs')::integer
        ELSE 0
    END,
    r.created_at
FROM document_ingest_ai_reviews r
LEFT JOIN documents d ON d.source_path = r.source_path
JOIN ai_task_types task ON task.code = 'ingestion_assist'
WHERE NOT EXISTS (
    SELECT 1
      FROM ai_assist_events ev
     WHERE ev.task_type_id = task.id
       AND ev.provider_type_id = r.provider_type_id
       AND ev.model_name = r.model_name
       AND ev.context_type = 'document_ingest'
       AND ev.created_at = r.created_at
);

INSERT INTO schema_migrations (version, name)
VALUES (54, 'backfill_local_ingestion_ai_usage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
