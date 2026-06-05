SELECT ev.id,
       ev.created_at,
       ev.entity_id,
       en.name AS entity_name,
       ev.user_id,
       u.username,
       t.code AS task_type,
       t.display_name AS task_label,
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
       ev.latency_ms
FROM ai_assist_events ev
LEFT JOIN entities en ON en.id = ev.entity_id
LEFT JOIN users u ON u.id = ev.user_id
LEFT JOIN ai_task_types t ON t.id = ev.task_type_id
WHERE ev.created_at >= now() - (%s::integer * interval '1 hour')
  AND (%s::bigint IS NULL OR ev.entity_id = %s::bigint)
ORDER BY ev.created_at DESC
LIMIT %s;
