SELECT ev.id,
       ev.created_at,
       ev.entity_id,
       en.name AS entity_name,
       ev.user_id,
       u.username,
       p.code AS provider,
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
       ev.final_cost,
       ev.cost_status,
       ev.cost_discrepancy,
       ev.reconciliation_run_id,
       ev.allocation_method,
       ev.paid_by,
       ev.provider_key_owner_user_id,
       key_owner.username AS provider_key_owner_username,
       ev.provider_project_id,
       ev.provider_api_key_id,
       ev.success,
       ev.error_message,
       ev.decision_reason,
       ev.latency_ms
FROM ai_assist_events ev
LEFT JOIN entities en ON en.id = ev.entity_id
LEFT JOIN users u ON u.id = ev.user_id
LEFT JOIN users key_owner ON key_owner.id = ev.provider_key_owner_user_id
LEFT JOIN ai_provider_types p ON p.id = ev.provider_type_id
LEFT JOIN ai_task_types t ON t.id = ev.task_type_id
WHERE (
      %s = 'system'
      OR (%s = 'entity' AND ev.entity_id = %s::bigint)
      OR (%s = 'user' AND (ev.user_id = %s::bigint OR ev.provider_key_owner_user_id = %s::bigint))
  )
  AND ev.created_at >= now() - (%s::integer * interval '1 day')
ORDER BY ev.created_at DESC
LIMIT %s;
