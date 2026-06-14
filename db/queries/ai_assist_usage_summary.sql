SELECT count(*) AS calls,
       count(*) FILTER (WHERE ev.success) AS successful_calls,
       coalesce(sum(ev.input_tokens), 0) AS input_tokens,
       coalesce(sum(ev.cached_input_tokens), 0) AS cached_input_tokens,
       coalesce(sum(ev.output_tokens), 0) AS output_tokens,
       coalesce(sum(ev.estimated_cost), 0) AS estimated_cost,
       coalesce(sum(coalesce(ev.final_cost, ev.estimated_cost)), 0) AS actual_cost,
       coalesce(sum(coalesce(ev.final_cost, 0)), 0) AS verified_cost,
       count(*) FILTER (WHERE ev.final_cost IS NOT NULL) AS reconciled_calls
FROM ai_assist_events ev
WHERE (
      %s = 'system'
      OR (%s = 'entity' AND ev.entity_id = %s::bigint)
      OR (%s = 'user' AND (ev.user_id = %s::bigint OR ev.provider_key_owner_user_id = %s::bigint))
  )
  AND ev.created_at >= now() - (%s::integer * interval '1 day');
