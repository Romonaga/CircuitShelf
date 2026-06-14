UPDATE ai_assist_events ev
   SET final_cost = NULL,
       cost_status = 'estimated',
       cost_discrepancy = 0,
       reconciliation_run_id = NULL,
       allocation_method = ''
  FROM ai_provider_types provider
 WHERE ev.provider_type_id = provider.id
   AND provider.code = 'openai'
   AND ev.success = true
   AND ev.created_at >= %s
   AND ev.created_at < %s
   AND (%s::text[] IS NULL OR ev.provider_project_id = '' OR ev.provider_project_id = ANY(%s::text[]))
   AND (%s::text[] IS NULL OR ev.provider_api_key_id = '' OR ev.provider_api_key_id = ANY(%s::text[]));
