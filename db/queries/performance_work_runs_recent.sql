SELECT wr.id,
       wt.code AS work_type,
       wt.display_name AS work_type_label,
       wr.entity_id,
       e.name AS entity_name,
       wr.user_id,
       u.username,
       wr.label,
       wr.trigger_reason,
       wr.status,
       wr.source_path,
       wr.started_at,
       wr.finished_at,
       wr.duration_ms,
       wr.chunks,
       wr.images,
       wr.dropped_chunks,
       wr.details,
       wr.error_message
FROM performance_work_runs wr
LEFT JOIN performance_work_types wt ON wt.id = wr.work_type_id
LEFT JOIN entities e ON e.id = wr.entity_id
LEFT JOIN users u ON u.id = wr.user_id
WHERE wr.started_at >= now() - (%s::integer * interval '1 hour')
ORDER BY wr.started_at DESC
LIMIT %s;
