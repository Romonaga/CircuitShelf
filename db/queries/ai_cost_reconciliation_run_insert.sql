INSERT INTO ai_cost_reconciliation_runs (
    provider_type_id,
    status,
    source,
    start_time,
    end_time,
    bucket_width,
    allocation_method,
    created_by,
    raw_provider_payload
)
VALUES (
    (SELECT id FROM ai_provider_types WHERE code = %s),
    'running',
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    '{}'::jsonb
)
RETURNING id;
