SELECT ev.id,
       ev.created_at,
       provider.code AS provider,
       ev.model_name,
       ev.input_tokens,
       ev.cached_input_tokens,
       ev.output_tokens,
       ev.estimated_cost,
       ev.final_cost,
       ev.cost_status
FROM ai_assist_events ev
JOIN ai_provider_types provider ON provider.id = ev.provider_type_id
WHERE provider.code = 'openai'
  AND ev.success = true
  AND ev.created_at >= %s
  AND ev.created_at < %s
ORDER BY ev.created_at ASC, ev.id ASC;
