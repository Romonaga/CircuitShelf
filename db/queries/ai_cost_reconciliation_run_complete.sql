UPDATE ai_cost_reconciliation_runs
   SET status = 'completed',
       verified_cost = %s,
       estimated_cost = %s,
       cost_discrepancy = %s,
       event_count = %s,
       raw_provider_payload = %s::jsonb,
       completed_at = now(),
       error_message = NULL
 WHERE id = %s::uuid;
