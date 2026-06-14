SELECT ev.id,
       ev.created_at,
       ev.entity_id,
       ev.user_id,
       provider.code AS provider,
       ev.model_name,
       ev.provider_project_id,
       ev.provider_api_key_id,
       ev.input_tokens,
       ev.cached_input_tokens,
       ev.output_tokens,
       ev.estimated_cost,
       ev.final_cost,
       ev.cost_status,
       ev.paid_by,
       ev.provider_key_owner_user_id
FROM ai_assist_events ev
JOIN ai_provider_types provider ON provider.id = ev.provider_type_id
WHERE provider.code = 'openai'
  AND ev.success = true
  AND ev.created_at >= %s
  AND ev.created_at < %s
  AND (%s::text[] IS NULL OR ev.provider_project_id = '' OR ev.provider_project_id = ANY(%s::text[]))
  AND (%s::text[] IS NULL OR ev.provider_api_key_id = '' OR ev.provider_api_key_id = ANY(%s::text[]))
ORDER BY ev.created_at ASC, ev.id ASC;
