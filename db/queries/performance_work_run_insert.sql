INSERT INTO performance_work_runs (
    work_type_id,
    entity_id,
    user_id,
    label,
    trigger_reason,
    status_id,
    source_path,
    started_at,
    finished_at,
    duration_ms,
    chunks,
    images,
    dropped_chunks,
    details,
    error_message
)
VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s::jsonb, %s
)
RETURNING id;
