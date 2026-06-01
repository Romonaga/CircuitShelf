SELECT coalesce(sum(estimated_cost), 0) AS estimated_cost
FROM ai_assist_events
WHERE created_at >= date_trunc('month', now())
  AND paid_by = %s
  AND (
    %s = 'system'
    OR (%s = 'entity' AND entity_id = %s::bigint)
    OR (%s = 'user' AND provider_key_owner_user_id = %s::bigint)
  );
